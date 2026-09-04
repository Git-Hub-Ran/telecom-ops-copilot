"""Pydantic data contracts for state machine orchestrator.

This module provides clean public API for importing orchestrator Pydantic models.
All models defined in this package represent state inputs, outputs, and internal
data carriers.

Usage:
    from src.orchestrator.models import (
        SessionState,
        ClassifyOutput,
        RoutingDecision,
        ActOutput,
        RespondOutput,
        StateContext
    )

Note: EscalationPayload is NOT re-exported here. It lives in src.tools.escalation
and should be imported directly from there to maintain clear separation between
orchestrator models and tool contracts.
"""

from .act import ActOutput, KBCitation, ToolCallRecord
from .classify import ClassifyOutput
from .context import StateContext
from .respond import RespondOutput
from .route import RoutingDecision
from .session import ConversationTurn, SessionState

__all__ = [
    # Session models
    "ConversationTurn",
    "SessionState",
    # Classification models
    "ClassifyOutput",
    # Routing models
    "RoutingDecision",
    # Act state models
    "ToolCallRecord",
    "KBCitation",
    "ActOutput",
    # Response models
    "RespondOutput",
    # State context
    "StateContext",
]
