"""Routing decision models from RouteState.

This module defines the routing decision enum that determines which path the
state machine follows after classification. The RouteState uses classification
confidence, intent, and off_topic flag to select the appropriate routing decision.

Per FR-011, RouteState output must include a routing_decision enum with 7
possible values representing the different paths through the state machine.
"""

from enum import Enum


class RoutingDecision(str, Enum):
    """Routing decision enumeration for state machine flow control.

    This enum defines all possible routing paths after the Classify state.
    Each value maps to a specific state machine behavior, from intent-based
    routing to special cases like clarification and off-topic refusal.

    Per FR-011, the seven routing decisions are: billing_path, technical_path,
    account_path, info_path, skip_to_escalate, ask_clarifying_question, and
    refuse_off_topic.

    Routing logic (implemented in RouteState):

    | Condition                 | Decision                   |
    |---------------------------|----------------------------|
    | off_topic=True            | REFUSE_OFF_TOPIC           |
    | confidence < 0.6          | ASK_CLARIFYING_QUESTION    |
    | intent="escalate"         | SKIP_TO_ESCALATE           |
    | intent="billing"          | BILLING_PATH               |
    | intent="technical"        | TECHNICAL_PATH             |
    | intent="account"          | ACCOUNT_PATH               |
    | intent="info"             | INFO_PATH                  |
    | intent="unknown"          | SKIP_TO_ESCALATE           |
    """

    BILLING_PATH = "billing_path"
    TECHNICAL_PATH = "technical_path"
    ACCOUNT_PATH = "account_path"
    INFO_PATH = "info_path"
    SKIP_TO_ESCALATE = "skip_to_escalate"
    ASK_CLARIFYING_QUESTION = "ask_clarifying_question"
    REFUSE_OFF_TOPIC = "refuse_off_topic"
