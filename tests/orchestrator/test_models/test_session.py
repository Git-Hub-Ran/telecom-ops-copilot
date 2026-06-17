"""Tests for session state Pydantic models."""

import pytest
from pydantic import ValidationError

from src.orchestrator.models.session import ConversationTurn, SessionState


class TestConversationTurn:
    """Test suite for ConversationTurn model."""

    def test_accepts_valid_role_customer(self) -> None:
        """Test that ConversationTurn accepts valid role 'customer'."""
        turn = ConversationTurn(
            role="customer",
            content="What is my current balance?",
            timestamp="2026-06-17T14:30:00Z"
        )
        assert turn.role == "customer"
        assert turn.content == "What is my current balance?"
        assert turn.timestamp == "2026-06-17T14:30:00Z"

    def test_accepts_valid_role_agent(self) -> None:
        """Test that ConversationTurn accepts valid role 'agent'."""
        turn = ConversationTurn(
            role="agent",
            content="Your current balance is $125.50.",
            timestamp="2026-06-17T14:30:15Z"
        )
        assert turn.role == "agent"
        assert turn.content == "Your current balance is $125.50."

    def test_rejects_invalid_role_value(self) -> None:
        """Test that ConversationTurn rejects invalid role value."""
        with pytest.raises(ValidationError) as exc_info:
            ConversationTurn(
                role="system",  # Invalid: only "customer" or "agent" allowed
                content="System message",
                timestamp="2026-06-17T14:30:00Z"
            )

        # Verify error mentions the role field
        error_str = str(exc_info.value)
        assert "role" in error_str.lower()


class TestSessionState:
    """Test suite for SessionState model."""

    def test_accepts_all_required_fields(self) -> None:
        """Test that SessionState accepts all required fields."""
        state = SessionState(
            session_id="SESS-20260617-001",
            correlation_id="corr-abc123",
            started_at="2026-06-17T14:00:00Z",
            last_updated="2026-06-17T14:30:00Z"
        )
        assert state.session_id == "SESS-20260617-001"
        assert state.correlation_id == "corr-abc123"
        assert state.started_at == "2026-06-17T14:00:00Z"
        assert state.last_updated == "2026-06-17T14:30:00Z"

    def test_missing_session_id_raises_validation_error(self) -> None:
        """Test that SessionState raises ValidationError when session_id is missing."""
        with pytest.raises(ValidationError) as exc_info:
            SessionState(
                correlation_id="corr-abc123",
                started_at="2026-06-17T14:00:00Z",
                last_updated="2026-06-17T14:30:00Z"
            )

        # Verify error mentions session_id
        error_str = str(exc_info.value)
        assert "session_id" in error_str.lower()

    def test_account_id_can_be_none(self) -> None:
        """Test that SessionState account_id can be None (optional field)."""
        state = SessionState(
            session_id="SESS-20260617-001",
            correlation_id="corr-abc123",
            account_id=None,
            started_at="2026-06-17T14:00:00Z",
            last_updated="2026-06-17T14:30:00Z"
        )
        assert state.account_id is None

    def test_conversation_history_defaults_to_empty_list(self) -> None:
        """Test that SessionState conversation_history defaults to empty list."""
        state = SessionState(
            session_id="SESS-20260617-001",
            correlation_id="corr-abc123",
            started_at="2026-06-17T14:00:00Z",
            last_updated="2026-06-17T14:30:00Z"
        )
        assert state.conversation_history == []
        assert isinstance(state.conversation_history, list)

    def test_accepts_list_of_conversation_turn_objects(self) -> None:
        """Test that SessionState accepts list of ConversationTurn objects."""
        turns = [
            ConversationTurn(
                role="customer",
                content="What is my balance?",
                timestamp="2026-06-17T14:30:00Z"
            ),
            ConversationTurn(
                role="agent",
                content="Your balance is $125.50.",
                timestamp="2026-06-17T14:30:15Z"
            )
        ]

        state = SessionState(
            session_id="SESS-20260617-001",
            correlation_id="corr-abc123",
            conversation_history=turns,
            started_at="2026-06-17T14:00:00Z",
            last_updated="2026-06-17T14:30:15Z"
        )

        assert len(state.conversation_history) == 2
        assert state.conversation_history[0].role == "customer"
        assert state.conversation_history[1].role == "agent"
        assert state.conversation_history[0].content == "What is my balance?"
