"""RouteState implementation for deterministic routing logic.

This module implements the Route state, which maps classification results to
routing decisions using pure Python logic (no LLM dependency). The routing
logic enforces priority rules to ensure correct state machine flow.

Per FR-010, Route input includes ClassifyOutput from the Classify state.
Per FR-011, Route output is a RoutingDecision enum value.
"""

from src.config import get_config
from src.orchestrator.models import ClassifyOutput, RoutingDecision, StateContext
from src.orchestrator.states.base import BaseState


class RouteState(BaseState[StateContext, RoutingDecision]):
    """Deterministic routing state using pure Python logic.

    RouteState maps ClassifyOutput to RoutingDecision based on priority rules:
    1. Off-topic queries are refused (highest priority)
    2. Explicit escalation intent skips to escalation
    3. Unknown intent asks for clarification
    4. Low confidence triggers clarification
    5. Known intents map to their corresponding paths

    This state has no LLM dependency - all decisions are made using if/else logic
    on the classification result fields.

    Priority order ensures correct behavior when multiple conditions are true:
    - off_topic=True always wins (even if confidence is also low)
    - intent="escalate" routes to escalation before the confidence gate
    - intent="unknown" routes to clarification; genuine injections are labelled
      "escalate" by the classifier, and off-topic content is caught by Priority 1
    - confidence < 0.6 beats intent routing for known intents

    Routing Decision Table:
    | Condition                  | Decision                    |
    |----------------------------|-----------------------------|
    | off_topic=True             | REFUSE_OFF_TOPIC            |
    | intent="escalate"          | SKIP_TO_ESCALATE            |
    | intent="unknown"           | ASK_CLARIFYING_QUESTION     |
    | confidence < 0.6           | ASK_CLARIFYING_QUESTION     |
    | intent="billing"           | BILLING_PATH                |
    | intent="technical"         | TECHNICAL_PATH              |
    | intent="account"           | ACCOUNT_PATH                |
    | intent="info"              | INFO_PATH                   |
    """

    async def run(self, context: StateContext) -> RoutingDecision:
        """Execute routing logic to determine next state machine step.

        This method applies priority-based routing rules to map ClassifyOutput
        to the appropriate RoutingDecision. The logic is pure Python (no I/O or
        LLM calls), but the method is async to satisfy the BaseState contract.

        Args:
            context: StateContext containing classify_output from ClassifyState.
                    The classify_output field must be populated (not None).

        Returns:
            RoutingDecision enum value indicating which path the state machine
            should follow next.

        Raises:
            ValueError: If classify_output is None (indicates ClassifyState was
                       skipped or failed to populate its output).
        """
        # Defensive validation: classify_output should always be present
        # because Route runs after Classify, but catch bugs early
        if context.classify_output is None:
            raise ValueError(
                "RouteState requires classify_output, but it was None. "
                "Ensure ClassifyState runs before RouteState."
            )

        classify_output = context.classify_output

        # Priority 1: Refuse off-topic queries (highest priority)
        # Off-topic detection always wins, even if confidence is also low
        if classify_output.off_topic:
            return RoutingDecision.REFUSE_OFF_TOPIC

        # Priority 2: Escalate on explicit escalation intent.
        if classify_output.intent == "escalate":
            return RoutingDecision.SKIP_TO_ESCALATE

        # Priority 3: Ask for clarification on unknown intent.
        # Unknown means the classifier could not determine what the customer wants.
        # Genuine injection attempts are labelled "escalate" by the classifier;
        # off-topic content is already caught by Priority 1.
        if classify_output.intent == "unknown":
            return RoutingDecision.ASK_CLARIFYING_QUESTION

        # Priority 4: Ask for clarification on low confidence (known intents only).
        # At this point intent is one of {billing, technical, account, info}.
        threshold = get_config().CLASSIFICATION_CONFIDENCE_THRESHOLD
        if classify_output.confidence < threshold:
            return RoutingDecision.ASK_CLARIFYING_QUESTION

        # Priority 5-8: Map known intents to their paths
        # At this point: off_topic=False, intent not escalate/unknown, confidence >= threshold
        intent_to_path = {
            "billing": RoutingDecision.BILLING_PATH,
            "technical": RoutingDecision.TECHNICAL_PATH,
            "account": RoutingDecision.ACCOUNT_PATH,
            "info": RoutingDecision.INFO_PATH,
        }

        return intent_to_path[classify_output.intent]
