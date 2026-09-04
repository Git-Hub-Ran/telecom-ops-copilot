"""Session state models for multi-turn conversation persistence.

This module provides Pydantic models for tracking conversation state across
multiple turns in Streamlit session_state. SessionState holds the complete
conversation context including history, account information, and emotion tracking.

Per FR-054, SessionState must include: account_id, conversation_history,
tools_called_this_session, session_id, and created_at.

Per FR-055, conversation_history maintains a rolling window of the last 10 turns
(prevents unbounded growth). Each ConversationTurn is one message (customer OR
agent), so the window holds at most 10 individual messages in any combination
of roles.
"""

from typing import Literal, Optional

from pydantic import BaseModel, Field


class ConversationTurn(BaseModel):
    """A single turn in the conversation (customer message or agent response).

    Each turn represents one message in the conversation, tagged with the role
    (customer or agent) and a timestamp for ordering and analytics.
    """

    role: Literal["customer", "agent"] = Field(
        description="Who sent this message (customer or agent)"
    )
    content: str = Field(
        description="Message content text"
    )
    timestamp: str = Field(
        description="ISO 8601 timestamp when this turn occurred (e.g., 2026-06-17T14:30:00Z)"
    )


class SessionState(BaseModel):
    """Multi-turn session state persisted across conversation turns.

    This model holds all state for a single customer conversation session,
    including conversation history, extracted account information, and detected
    customer emotion. The session state is persisted in Streamlit session_state
    and updated after each turn.

    Per FR-055, conversation_history maintains a rolling window of the last 10
    turns. Older turns are evicted when the window size is exceeded.
    """

    session_id: str = Field(
        description="Unique session identifier (format: SESS-*, enforced by caller)"
    )
    correlation_id: str = Field(
        description="Unique correlation ID for the current turn (used for tracing/logging)"
    )
    account_id: Optional[str] = Field(
        default=None,
        description="Customer account ID extracted from conversation (format: ACC-* if present)"
    )
    detected_emotion: Optional[str] = Field(
        default=None,
        description="Detected customer emotion (e.g., neutral, mildly_frustrated, frustrated, angry)"
    )
    conversation_history: list[ConversationTurn] = Field(
        default_factory=list,
        description="Last 10 conversation turns (rolling window, each turn is one message), oldest first"
    )
    channel: Literal["chat", "voice", "email"] = Field(
        default="chat",
        description="Communication channel for this session"
    )
    started_at: str = Field(
        description="Session start timestamp in ISO 8601 format (e.g., 2026-06-17T14:30:00Z)"
    )
    last_updated: str = Field(
        description="Last activity timestamp in ISO 8601 format (updated on every turn)"
    )
