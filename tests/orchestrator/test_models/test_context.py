"""Tests for StateContext Pydantic model."""

import copy

import pytest
from pydantic import ValidationError

from src.orchestrator.models.act import ActOutput
from src.orchestrator.models.classify import ClassifyOutput
from src.orchestrator.models.context import StateContext
from src.orchestrator.models.route import RoutingDecision
from src.orchestrator.models.session import ConversationTurn, SessionState
from src.tools.escalation import CreateEscalationTicketResult


class TestStateContext:
    """Test suite for StateContext model."""

    def test_instantiation_with_only_required_fields(self) -> None:
        """Test that StateContext accepts only required fields (session_state, customer_message)."""
        session = SessionState(
            session_id="SESS-001",
            correlation_id="corr-123",
            started_at="2026-06-17T14:00:00Z",
            last_updated="2026-06-17T14:30:00Z"
        )

        context = StateContext(
            session_state=session,
            customer_message="What is my current bill?"
        )

        assert context.session_state.session_id == "SESS-001"
        assert context.customer_message == "What is my current bill?"

    def test_optional_fields_default_to_none(self) -> None:
        """Test that classify_output, routing_decision, act_output default to None."""
        session = SessionState(
            session_id="SESS-001",
            correlation_id="corr-123",
            started_at="2026-06-17T14:00:00Z",
            last_updated="2026-06-17T14:30:00Z"
        )

        context = StateContext(
            session_state=session,
            customer_message="What is my current bill?"
        )

        assert context.classify_output is None
        assert context.routing_decision is None
        assert context.act_output is None
        assert context.escalate_output is None

    def test_progressive_population_of_optional_fields(self) -> None:
        """Test progressive population (classify_output set, then routing_decision, then act_output)."""
        session = SessionState(
            session_id="SESS-001",
            correlation_id="corr-123",
            started_at="2026-06-17T14:00:00Z",
            last_updated="2026-06-17T14:30:00Z"
        )

        # Initial context
        context = StateContext(
            session_state=session,
            customer_message="What is my current bill?"
        )

        # After ClassifyState runs
        context.classify_output = ClassifyOutput(
            intent="billing",
            confidence=0.92,
            off_topic=False
        )
        assert context.classify_output.intent == "billing"
        assert context.routing_decision is None

        # After RouteState runs
        context.routing_decision = RoutingDecision.BILLING_PATH
        assert context.routing_decision == RoutingDecision.BILLING_PATH
        assert context.act_output is None

        # After ActState runs
        context.act_output = ActOutput(
            resolution_status="resolved",
            tools_called=[],
            kb_citations=[]
        )
        assert context.act_output.resolution_status == "resolved"

    def test_serialization_round_trip(self) -> None:
        """Test serialization round-trip (model_dump -> model_validate)."""
        session = SessionState(
            session_id="SESS-001",
            correlation_id="corr-123",
            started_at="2026-06-17T14:00:00Z",
            last_updated="2026-06-17T14:30:00Z"
        )

        original = StateContext(
            session_state=session,
            customer_message="What is my current bill?",
            classify_output=ClassifyOutput(
                intent="billing",
                confidence=0.92,
                off_topic=False
            ),
            routing_decision=RoutingDecision.BILLING_PATH
        )

        # Serialize to dict
        data = original.model_dump()
        assert isinstance(data, dict)
        assert data["customer_message"] == "What is my current bill?"
        assert data["classify_output"]["intent"] == "billing"

        # Deserialize back to model
        restored = StateContext.model_validate(data)
        assert restored.customer_message == original.customer_message
        assert restored.classify_output.intent == original.classify_output.intent
        assert restored.routing_decision == original.routing_decision

    def test_validation_rejects_missing_required_fields(self) -> None:
        """Test validation rejects missing required fields."""
        # Missing session_state
        with pytest.raises(ValidationError) as exc_info:
            StateContext(
                customer_message="What is my current bill?"
            )

        error_str = str(exc_info.value)
        assert "session_state" in error_str.lower()

        # Missing customer_message
        session = SessionState(
            session_id="SESS-001",
            correlation_id="corr-123",
            started_at="2026-06-17T14:00:00Z",
            last_updated="2026-06-17T14:30:00Z"
        )

        with pytest.raises(ValidationError) as exc_info:
            StateContext(
                session_state=session
            )

        error_str = str(exc_info.value)
        assert "customer_message" in error_str.lower()

    def test_nested_session_state_fields_are_accessible(self) -> None:
        """Test that nested SessionState fields are accessible via context.session_state.correlation_id."""
        turns = [
            ConversationTurn(
                role="customer",
                content="What is my bill?",
                timestamp="2026-06-17T14:30:00Z"
            )
        ]

        session = SessionState(
            session_id="SESS-001",
            correlation_id="corr-abc-123",
            account_id="ACC-10001",
            detected_emotion="neutral",
            conversation_history=turns,
            started_at="2026-06-17T14:00:00Z",
            last_updated="2026-06-17T14:30:00Z"
        )

        context = StateContext(
            session_state=session,
            customer_message="What is my current bill?"
        )

        # Verify nested field access
        assert context.session_state.correlation_id == "corr-abc-123"
        assert context.session_state.account_id == "ACC-10001"
        assert context.session_state.detected_emotion == "neutral"
        assert len(context.session_state.conversation_history) == 1
        assert context.session_state.conversation_history[0].role == "customer"

    def test_escalate_output_field_exists_and_defaults_to_none(self) -> None:
        """Test that escalate_output field exists and defaults to None."""
        session = SessionState(
            session_id="SESS-001",
            correlation_id="corr-123",
            started_at="2026-06-17T14:00:00Z",
            last_updated="2026-06-17T14:30:00Z"
        )

        context = StateContext(
            session_state=session,
            customer_message="I need to speak to a supervisor"
        )

        # escalate_output should exist and be None initially
        assert hasattr(context, "escalate_output")
        assert context.escalate_output is None

    def test_escalate_output_accepts_valid_result(self) -> None:
        """Test that escalate_output accepts a valid CreateEscalationTicketResult."""
        session = SessionState(
            session_id="SESS-001",
            correlation_id="corr-123",
            started_at="2026-06-17T14:00:00Z",
            last_updated="2026-06-17T14:30:00Z"
        )

        # Create a valid escalation result (success case)
        escalation_result = CreateEscalationTicketResult(
            success=True,
            ticket=None,  # Simplified for test
            error_code=None,
            error_message=None
        )

        context = StateContext(
            session_state=session,
            customer_message="I need help",
            escalate_output=escalation_result
        )

        assert context.escalate_output is not None
        assert context.escalate_output.success is True

    def test_mutation_contract_with_escalate_output(self) -> None:
        """Test that StateContext is not mutated when escalate_output is read (mutation contract).

        This test verifies that reading escalate_output does not mutate the context
        object. Uses the same deep-copy pattern as test_route_integration.py to
        ensure immutability.
        """
        session = SessionState(
            session_id="SESS-001",
            correlation_id="corr-123",
            started_at="2026-06-17T14:00:00Z",
            last_updated="2026-06-17T14:30:00Z"
        )

        escalation_result = CreateEscalationTicketResult(
            success=False,
            ticket=None,
            error_code="validation_failed",
            error_message="Missing required fields"
        )

        context = StateContext(
            session_state=session,
            customer_message="Escalate this",
            escalate_output=escalation_result
        )

        # Take deep copy before reading (simulating what a state would do)
        context_before = copy.deepcopy(context)

        # Simulate what EscalateState would do: read escalate_output
        _ = context.escalate_output

        # Verify the original context equals the deep copy (no mutation occurred)
        assert context.model_dump() == context_before.model_dump()
        assert context.escalate_output.success == context_before.escalate_output.success
        assert context.escalate_output.error_code == context_before.escalate_output.error_code
