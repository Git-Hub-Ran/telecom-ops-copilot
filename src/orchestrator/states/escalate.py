"""EscalateState implementation for human handoff ticket generation.

Assembles a structured escalation payload from StateContext, invokes the
EscalateAgent to generate a free-text summary and suggested next action,
then persists the ticket via create_escalation_ticket.

Per FR-052, an escalation_triggered event is logged on every invocation.
Escalation never drops silently: if the agent fails, hardcoded fallback
text is used and create_escalation_ticket is still called.
"""

import asyncio
import json
from typing import Any

from azure.ai.agents.models import MessageRole

from src.orchestrator.agents.factory import AgentFactory
from src.orchestrator.models import (
    ActOutput,
    ClassifyOutput,
    RoutingDecision,
    StateContext,
)
from src.orchestrator.observability.structured import StructuredLogger
from src.orchestrator.states.base import BaseState
from src.tools.escalation import CreateEscalationTicketResult, create_escalation_ticket

_AGENT_FALLBACK_SUMMARY = "Agent unavailable - manual review required."
_AGENT_FALLBACK_ACTION = "Agent unavailable - manual review required."

_HIGH_FRUSTRATION: frozenset[str] = frozenset({"frustrated", "angry"})


def _priority_from_context(
    detected_emotion: str | None, act_output: ActOutput | None
) -> str:
    """Derive escalation priority from detected emotion and act_output state.

    Args:
        detected_emotion: Emotion string from session_state, or None.
        act_output: ActOutput from the preceding Act state, or None.

    Returns:
        One of "urgent", "high", "medium", or "low".
    """
    if detected_emotion == "angry":
        return "urgent"
    if detected_emotion == "frustrated":
        return "high"
    if act_output is not None and act_output.resolution_status == "unresolved":
        return "medium"
    return "low"


class EscalateState(BaseState[StateContext, CreateEscalationTicketResult]):
    """Escalation state that assembles and persists a human handoff ticket.

    Handles two trigger paths:
    - SKIP_TO_ESCALATE: routing bypassed ActState; act_output is None.
    - Post-Act unresolved: ActState ran but returned resolution_status="unresolved".

    Sequence:
    1. Select reason_code from context signals.
    2. Build a structured text prompt for the EscalateAgent.
    3. Invoke EscalateAgent (Foundry thread/run) to get summary and
       suggested_next_action. On failure, use hardcoded fallback strings.
    4. Assemble the full EscalationPayload dict from context fields and
       agent output.
    5. Call create_escalation_ticket(payload) to validate and persist.
    6. Log escalation_triggered event (FR-052).
    7. Return CreateEscalationTicketResult without mutating context.
    """

    def __init__(self, agent_factory: AgentFactory) -> None:
        """Initialize with an agent factory.

        Args:
            agent_factory: AgentFactory for retrieving the escalate agent and
                          its underlying AgentsClient.
        """
        self.factory = agent_factory
        self._logger = StructuredLogger()

    async def run(self, context: StateContext) -> CreateEscalationTicketResult:
        """Execute the escalation flow and return the ticket creation result.

        Reads classify_output, act_output, session_state, and customer_message
        from context. Returns CreateEscalationTicketResult without mutating
        context. The StateMachine sets context.escalate_output after this
        method returns.

        Args:
            context: StateContext with session_state and customer_message
                     populated. classify_output and act_output may be None.

        Returns:
            CreateEscalationTicketResult with success=True and the created
            ticket, or success=False with error_code if ticket creation failed.
        """
        correlation_id = context.session_state.correlation_id
        reason_code = self._select_reason_code(context)
        content = self._build_agent_prompt(context)

        raw_json = ""
        try:
            raw_json = await asyncio.to_thread(self._invoke_agent, content)
            data = json.loads(raw_json)
            summary: str = data["summary"]
            suggested_next_action: str = data["suggested_next_action"]
        except Exception as exc:
            self._logger.log_event(
                event_type="escalate_agent_error",
                state_name="escalate",
                correlation_id=correlation_id,
                level="error",
                error=str(exc),
                error_type=type(exc).__name__,
                raw_response_snippet=raw_json[:200],
            )
            summary = _AGENT_FALLBACK_SUMMARY
            suggested_next_action = _AGENT_FALLBACK_ACTION

        payload = self._build_payload(context, summary, suggested_next_action, reason_code)
        result = await asyncio.to_thread(create_escalation_ticket, payload)

        self._logger.log_event(
            event_type="escalation_triggered",
            state_name="escalate",
            correlation_id=correlation_id,
            level="info",
            reason_code=reason_code,
            ticket_success=result.success,
        )

        return result

    def _select_reason_code(self, context: StateContext) -> str:
        """Select the machine-readable escalation reason code from context signals.

        Priority order:
        1. tool_failure: ActState ran but returned unresolved.
        2. customer_frustration: detected_emotion is "frustrated" or "angry".
        3. out_of_scope: SKIP_TO_ESCALATE routing with intent "escalate" or "unknown".
        4. unresolved_ambiguity: default fallback.

        Args:
            context: StateContext with routing_decision, classify_output,
                     act_output, and session_state.detected_emotion.

        Returns:
            One of "tool_failure", "customer_frustration", "out_of_scope",
            or "unresolved_ambiguity".
        """
        act_output = context.act_output
        classify_output = context.classify_output
        routing_decision = context.routing_decision
        detected_emotion = context.session_state.detected_emotion

        if act_output is not None and act_output.resolution_status == "unresolved":
            return "tool_failure"
        if detected_emotion in _HIGH_FRUSTRATION:
            return "customer_frustration"
        if (
            routing_decision == RoutingDecision.SKIP_TO_ESCALATE
            and classify_output is not None
            and classify_output.intent in ("escalate", "unknown")
        ):
            return "out_of_scope"
        return "unresolved_ambiguity"

    def _build_agent_prompt(self, context: StateContext) -> str:
        """Build the structured text prompt sent to the EscalateAgent.

        Formats intent, resolution status, tools attempted, detected emotion,
        and conversation history into a single prompt string. Instructs the
        agent to return only summary and suggested_next_action as JSON.

        Args:
            context: StateContext with session_state, classify_output,
                     act_output, and customer_message.

        Returns:
            Formatted prompt string for the EscalateAgent user message.
        """
        lines: list[str] = ["Escalation context for TelSano support handoff:", ""]

        classify_output = context.classify_output
        act_output = context.act_output

        if classify_output is not None:
            lines.append(
                f"Intent: {classify_output.intent} "
                f"(confidence {classify_output.confidence:.2f})"
            )
        else:
            lines.append("Intent: unknown (no classification available)")

        if act_output is not None:
            lines.append(f"Resolution status: {act_output.resolution_status}")
            if act_output.tools_called:
                tool_names = ", ".join(r.tool_name for r in act_output.tools_called)
                lines.append(f"Tools attempted: {tool_names}")
            if act_output.error_details:
                lines.append(f"Error details: {act_output.error_details}")
        else:
            lines.append("Resolution status: not attempted (direct escalation)")

        emotion = context.session_state.detected_emotion
        if emotion:
            lines.append(f"Customer emotion: {emotion}")

        lines.append("")
        lines.append("Conversation history:")
        for turn in context.session_state.conversation_history:
            lines.append(f"  [{turn.role}]: {turn.content}")
        lines.append(f"  [customer]: {context.customer_message}")

        lines.append("")
        lines.append(
            'Return JSON with exactly two fields: "summary" (1-3 sentences '
            'describing the situation) and "suggested_next_action" (one sentence '
            "recommending what the human agent should do first)."
        )

        return "\n".join(lines)

    def _invoke_agent(self, content: str) -> str:
        """Invoke the escalate agent synchronously and return its JSON response text.

        Designed to run inside asyncio.to_thread. Uses the escalate agent
        configured in AgentFactory with ESCALATE_SYSTEM_PROMPT (FR-037 guard
        included).

        Args:
            content: Formatted prompt string from _build_agent_prompt.

        Returns:
            Raw JSON string from the escalate agent response.

        Raises:
            RuntimeError: If no assistant text response is found in the thread.
            azure.core.exceptions.HttpResponseError: If a Foundry API call fails.
        """
        client = self.factory.agents_client
        agent = self.factory.get_escalate_agent()
        thread = client.threads.create()
        client.messages.create(thread_id=thread.id, role="user", content=content)
        client.runs.create_and_process(thread_id=thread.id, agent_id=agent.id)
        msg = client.messages.get_last_message_text_by_role(
            thread_id=thread.id, role=MessageRole.AGENT
        )
        if msg is None:
            raise RuntimeError("No assistant text response found in escalate agent thread.")
        text = msg.text.value.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1]
            text = text.rsplit("```", 1)[0].strip()
        return text

    def _build_payload(
        self,
        context: StateContext,
        summary: str,
        suggested_next_action: str,
        reason_code: str,
    ) -> dict[str, Any]:
        """Assemble the full EscalationPayload dict from context and agent output.

        Maps all StateContext fields to the EscalationPayload schema expected
        by create_escalation_ticket. escalation_id and created_at are omitted
        so create_escalation_ticket auto-generates them.

        Args:
            context: StateContext with session_state, classify_output,
                     act_output, and customer_message.
            summary: Free-text situation summary from the EscalateAgent (or
                     fallback).
            suggested_next_action: Recommended first step for the human agent
                     (or fallback).
            reason_code: Machine-readable escalation reason from
                     _select_reason_code.

        Returns:
            Dict matching the EscalationPayload schema, ready for
            create_escalation_ticket.
        """
        session = context.session_state
        classify_output = context.classify_output
        act_output = context.act_output

        # Intent: "escalate" is not valid for EscalationPayload.intent.primary
        if classify_output is not None:
            primary = classify_output.intent if classify_output.intent != "escalate" else "unknown"
            intent: dict[str, Any] = {
                "primary": primary,
                "secondary": [],
                "confidence": classify_output.confidence,
            }
        else:
            intent = {"primary": "unknown", "secondary": [], "confidence": 0.0}

        # Customer emotion: map detected_emotion string to valid sentiment literal
        emotion_str = session.detected_emotion
        valid_sentiments = {"neutral", "mildly_frustrated", "frustrated", "angry"}
        sentiment = emotion_str if emotion_str in valid_sentiments else "neutral"
        customer_emotion: dict[str, Any] = {
            "sentiment": sentiment,
            "indicators": [f"detected_emotion={emotion_str}"] if emotion_str else [],
        }

        # Transcript: conversation history turns + current customer message
        transcript: list[dict[str, str]] = [
            {"role": turn.role, "content": turn.content, "at": turn.timestamp}
            for turn in session.conversation_history
        ]
        transcript.append({
            "role": "customer",
            "content": context.customer_message,
            "at": session.last_updated,
        })

        # Tools called and KB citations from act_output (empty if act_output is None)
        tools_called: list[dict[str, Any]] = []
        kb_citations: list[dict[str, str]] = []
        agent_attempts: list[str] = []

        if act_output is not None:
            for record in act_output.tools_called:
                tools_called.append({
                    "tool_name": record.tool_name,
                    "input": record.input,
                    "result_summary": record.result_summary,
                    "called_at": record.called_at,
                })
                status = "succeeded" if record.success else f"failed ({record.error_code})"
                agent_attempts.append(f"Called {record.tool_name}: {status}")
            for citation in act_output.kb_citations:
                kb_citations.append({
                    "doc_id": citation.doc_id,
                    "section": citation.section,
                    "relevance": citation.relevance,
                })

        if not agent_attempts:
            agent_attempts = ["No tools called before escalation"]

        return {
            "reason_code": reason_code,
            "priority": _priority_from_context(session.detected_emotion, act_output),
            "customer": {
                "account_id": session.account_id,
                "phone_contact": None,
                "name_on_file": None,
                "verified": session.account_id is not None,
            },
            "session": {
                "session_id": session.session_id,
                "started_at": session.started_at,
                "channel": session.channel,
                "language": "en",
            },
            "intent": intent,
            "summary": summary,
            "tools_called": tools_called,
            "kb_citations": kb_citations,
            "customer_emotion": customer_emotion,
            "transcript": transcript,
            "agent_attempts": agent_attempts,
            "suggested_next_action": suggested_next_action,
        }
