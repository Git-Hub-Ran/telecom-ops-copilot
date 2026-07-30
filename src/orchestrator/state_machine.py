"""StateMachine orchestrator for the TelSano customer service flow.

Coordinates the 5-state pipeline (Classify -> Route -> Act -> Escalate -> Respond)
for a single conversation turn. Manages StateContext accumulation, session state
mutation, and exception handling across states.

Per FR-047, every state transition is logged with from_state, to_state,
decision_reason, duration_ms, and session_id.
Per FR-051, correlation_id from session_state propagates through all states
via StateContext and is refreshed after each turn completes.
Per FR-053, session state is persisted in Streamlit st.session_state by the
caller. process_turn always works with SessionState; the UI layer owns
dict serialization per FR-056.
Per FR-055, conversation_history is limited to the last 10 turns (rolling
window enforced after RespondState returns).
"""

import re
import time
from datetime import datetime, timezone
from uuid import uuid4

from src.orchestrator.agents.factory import AgentFactory
from src.orchestrator.models import (
    ConversationTurn,
    RespondOutput,
    RoutingDecision,
    SessionState,
    StateContext,
)
from src.orchestrator.observability.structured import (
    StructuredLogger,
    log_state_transition,
)
from src.orchestrator.states.act import ActState
from src.orchestrator.states.classify import ClassifyState
from src.orchestrator.states.escalate import EscalateState
from src.orchestrator.states.respond import RespondState
from src.orchestrator.states.respond import _FALLBACK_MESSAGE
from src.orchestrator.states.route import RouteState

_ACT_DECISIONS: frozenset[RoutingDecision] = frozenset({
    RoutingDecision.BILLING_PATH,
    RoutingDecision.TECHNICAL_PATH,
    RoutingDecision.ACCOUNT_PATH,
    RoutingDecision.INFO_PATH,
})


class StateMachine:
    """Orchestrates the 5-state customer service pipeline for a single turn.

    Receives an AgentFactory and instantiates all five states internally.
    The single public entry point is process_turn(), which sequences states,
    accumulates context via model_copy, handles exceptions, and applies
    post-respond session mutations before returning RespondOutput to the caller.

    StateContext is an internal data carrier and is never returned to the caller.
    The Streamlit UI layer owns SessionState <-> dict serialization (FR-056).

    Example:
        factory = AgentFactory(get_config())
        machine = StateMachine(factory)
        result = await machine.process_turn(
            message="What is my current bill?",
            session=session_state,
        )
        print(result.message)
    """

    def __init__(self, agent_factory: AgentFactory) -> None:
        """Initialize StateMachine with all five states.

        Args:
            agent_factory: AgentFactory used to retrieve or create the four
                Foundry agents (Classifier, Act, Escalate, Respond). RouteState
                is pure Python and takes no factory argument.
        """
        self._classify = ClassifyState(agent_factory)
        self._route = RouteState()
        self._act = ActState(agent_factory)
        self._escalate = EscalateState(agent_factory)
        self._respond = RespondState(agent_factory)
        self._logger = StructuredLogger()

    async def process_turn(
        self,
        message: str,
        session: SessionState,
    ) -> RespondOutput:
        """Process one conversation turn through the 5-state pipeline.

        Builds an initial StateContext, sequences states conditionally based on
        the routing decision, and returns the final RespondOutput. Mutates session
        in place: detected_emotion after ClassifyState, and conversation_history,
        last_updated, correlation_id after RespondState.

        State sequence:
            Always: Classify -> Route -> Respond
            BILLING_PATH | TECHNICAL_PATH | ACCOUNT_PATH | INFO_PATH:
                also runs Act; then Escalate if Act result is unresolved
            SKIP_TO_ESCALATE: skips Act, runs Escalate
            REFUSE_OFF_TOPIC | ASK_CLARIFYING_QUESTION: skips Act and Escalate

        Exception handling:
            ClassifyState raises: returns fallback RespondOutput immediately
                without mutating session state.
            ActState raises: logs error, proceeds to EscalateState with
                act_output slot remaining None on context.

        Post-respond session mutation:
            Appends one customer ConversationTurn and one agent ConversationTurn,
            slices conversation_history to the last 10 turns (FR-055), updates
            last_updated, and refreshes correlation_id for the next turn (FR-051).

        Args:
            message: The current customer message text.
            session: SessionState for this conversation. Mutated in place after
                the turn completes (detected_emotion, conversation_history,
                last_updated, correlation_id).

        Returns:
            RespondOutput with the final customer-facing message, citations,
            and metadata.

        Raises:
            No exceptions are propagated. All state-level exceptions are caught
            and result in either a fallback RespondOutput (ClassifyState) or
            escalation routing (ActState).
        """
        correlation_id = session.correlation_id

        context = StateContext(
            session_state=session,
            customer_message=message,
        )

        match = re.search(r'\bACC-\d{5}\b', message, re.IGNORECASE)
        if match:
            last_agent_content = ""
            for turn in reversed(session.conversation_history):
                if turn.role == "agent":
                    last_agent_content = turn.content.lower()
                    break
            agent_solicited_id = any(
                phrase in last_agent_content
                for phrase in ("account id", "account number", "your account")
            )
            explicit_ownership = any(
                phrase in message.lower()
                for phrase in ("my account is", "account number is", "account id is", "my account number")
            )

            remainder = message[:match.start()] + message[match.end():]
            if explicit_ownership or agent_solicited_id:
                session.account_id = match.group(0).upper()
            elif session.account_id is None and len(message.strip()) > 15 and remainder.strip():
                session.account_id = match.group(0).upper()

        # --- ClassifyState ---
        t0 = time.monotonic()
        try:
            classify_output = await self._classify.run(context)
        except Exception as exc:
            self._logger.log_event(
                event_type="classify_error",
                state_name="classify",
                correlation_id=correlation_id,
                level="error",
                error=str(exc),
                error_type=type(exc).__name__,
            )
            return RespondOutput(
                message=_FALLBACK_MESSAGE,
                citations=[],
                metadata={"escalation_offered": True},
            )
        classify_ms = int((time.monotonic() - t0) * 1000)
        context = context.model_copy(update={"classify_output": classify_output})
        session.detected_emotion = classify_output.detected_emotion
        log_state_transition(
            logger=self._logger,
            from_state="classify",
            to_state="route",
            correlation_id=correlation_id,
            duration_ms=classify_ms,
            decision_reason=(
                f"intent={classify_output.intent}, "
                f"confidence={classify_output.confidence}"
            ),
        )

        # --- RouteState ---
        t0 = time.monotonic()
        routing_decision = await self._route.run(context)
        route_ms = int((time.monotonic() - t0) * 1000)
        context = context.model_copy(update={"routing_decision": routing_decision})

        if routing_decision in _ACT_DECISIONS:
            route_next = "act"
        elif routing_decision == RoutingDecision.SKIP_TO_ESCALATE:
            route_next = "escalate"
        else:
            route_next = "respond"
        log_state_transition(
            logger=self._logger,
            from_state="route",
            to_state=route_next,
            correlation_id=correlation_id,
            duration_ms=route_ms,
            decision_reason=f"routing_decision={routing_decision.value}",
        )

        # --- ActState (content paths only) ---
        act_failed = False
        if routing_decision in _ACT_DECISIONS:
            t0 = time.monotonic()
            try:
                act_output = await self._act.run(context)
                act_ms = int((time.monotonic() - t0) * 1000)
                context = context.model_copy(update={"act_output": act_output})
                log_state_transition(
                    logger=self._logger,
                    from_state="act",
                    to_state=(
                        "escalate"
                        if act_output.resolution_status == "unresolved"
                        else "respond"
                    ),
                    correlation_id=correlation_id,
                    duration_ms=act_ms,
                    decision_reason=f"resolution_status={act_output.resolution_status}",
                )
            except Exception as exc:
                act_ms = int((time.monotonic() - t0) * 1000)
                act_failed = True
                self._logger.log_event(
                    event_type="act_error",
                    state_name="act",
                    correlation_id=correlation_id,
                    level="error",
                    error=str(exc),
                    error_type=type(exc).__name__,
                )
                log_state_transition(
                    logger=self._logger,
                    from_state="act",
                    to_state="escalate",
                    correlation_id=correlation_id,
                    duration_ms=act_ms,
                    decision_reason="act_exception",
                )

        # --- EscalateState ---
        run_escalate = (
            routing_decision == RoutingDecision.SKIP_TO_ESCALATE
            or act_failed
            or (
                context.act_output is not None
                and context.act_output.resolution_status == "unresolved"
            )
        )
        if run_escalate:
            t0 = time.monotonic()
            escalate_output = await self._escalate.run(context)
            escalate_ms = int((time.monotonic() - t0) * 1000)
            context = context.model_copy(update={"escalate_output": escalate_output})
            log_state_transition(
                logger=self._logger,
                from_state="escalate",
                to_state="respond",
                correlation_id=correlation_id,
                duration_ms=escalate_ms,
                decision_reason="escalation_complete",
            )

        # --- RespondState ---
        t0 = time.monotonic()
        if context.act_output and context.act_output.prepared_response:
            respond_output = RespondOutput(
                message=context.act_output.prepared_response,
                citations=[],
                metadata={"escalation_offered": False},
            )
        else:
            respond_output = await self._respond.run(context)
        respond_ms = int((time.monotonic() - t0) * 1000)
        log_state_transition(
            logger=self._logger,
            from_state="respond",
            to_state="done",
            correlation_id=correlation_id,
            duration_ms=respond_ms,
            decision_reason="respond_complete",
        )

        # --- Post-respond session mutation ---
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        session.conversation_history = (
            session.conversation_history
            + [
                ConversationTurn(role="customer", content=message, timestamp=now),
                ConversationTurn(role="agent", content=respond_output.message, timestamp=now),
            ]
        )[-10:]
        session.last_updated = now
        session.correlation_id = str(uuid4())

        return respond_output
