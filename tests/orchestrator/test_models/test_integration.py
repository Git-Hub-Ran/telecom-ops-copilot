"""Integration tests for orchestrator Pydantic models working together.

These tests verify that models interact correctly when used in combination,
catching issues that unit tests on individual models might miss.
"""

import pytest
from pydantic import ValidationError

from src.orchestrator.models import (
    ActOutput,
    ClassifyOutput,
    ConversationTurn,
    KBCitation,
    RespondOutput,
    RoutingDecision,
    SessionState,
    StateContext,
    ToolCallRecord,
)


class TestModelsIntegration:
    """Integration tests for orchestrator models."""

    def test_end_to_end_session_state_lifecycle(self) -> None:
        """Test SessionState lifecycle with conversation history accumulation and serialization."""
        # Create SessionState with empty history
        session = SessionState(
            session_id="SESS-20260617-001",
            correlation_id="corr-initial",
            started_at="2026-06-17T14:00:00Z",
            last_updated="2026-06-17T14:00:00Z"
        )
        assert len(session.conversation_history) == 0

        # Simulate adding 12 conversation turns (6 customer + 6 agent pairs)
        turns = []
        for i in range(12):
            turn = ConversationTurn(
                role="customer" if i % 2 == 0 else "agent",
                content=f"Message {i + 1}",
                timestamp=f"2026-06-17T14:{i:02d}:00Z"
            )
            turns.append(turn)

        session.conversation_history = turns

        # Verify all 12 turns are present (trimming happens in orchestrator logic, not model)
        assert len(session.conversation_history) == 12
        assert session.conversation_history[0].content == "Message 1"
        assert session.conversation_history[11].content == "Message 12"

        # Verify that if we trimmed to last 10, we'd keep messages 3-12
        # (This exercises the model; actual trimming logic is in the orchestrator)
        last_10_turns = session.conversation_history[-10:]
        assert len(last_10_turns) == 10
        assert last_10_turns[0].content == "Message 3"
        assert last_10_turns[9].content == "Message 12"

        # Round-trip serialize the full SessionState
        serialized = session.model_dump()
        assert serialized["session_id"] == "SESS-20260617-001"
        assert len(serialized["conversation_history"]) == 12

        restored = SessionState.model_validate(serialized)
        assert restored.session_id == session.session_id
        assert len(restored.conversation_history) == 12
        assert restored.conversation_history[0].content == "Message 1"

    def test_progressive_state_context_population(self) -> None:
        """Test StateContext progressive population through simulated state machine flow."""
        # Initial context (what StateMachine creates)
        session = SessionState(
            session_id="SESS-001",
            correlation_id="corr-flow-test",
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

        # After ClassifyState runs
        context.classify_output = ClassifyOutput(
            intent="billing",
            confidence=0.92,
            detected_emotion="neutral",
            off_topic=False
        )
        assert context.classify_output.intent == "billing"
        assert context.classify_output.confidence == 0.92

        # After RouteState runs
        context.routing_decision = RoutingDecision.BILLING_PATH
        assert context.routing_decision == RoutingDecision.BILLING_PATH
        assert context.routing_decision.value == "billing_path"

        # After ActState runs (with ToolCallRecord and KBCitation)
        tool_call = ToolCallRecord(
            tool_name="get_billing_info",
            input={"account_id": "ACC-10001", "months": 3},
            result_summary="Retrieved 3 months of billing history",
            called_at="2026-06-17T14:30:00Z",
            success=True
        )

        kb_citation = KBCitation(
            doc_id="kb/policies/02-late-fees.md",
            section="Grace Period",
            relevance="Explains grace period for late payments"
        )

        context.act_output = ActOutput(
            resolution_status="resolved",
            tools_called=[tool_call],
            kb_citations=[kb_citation]
        )
        assert context.act_output.resolution_status == "resolved"
        assert len(context.act_output.tools_called) == 1
        assert len(context.act_output.kb_citations) == 1
        assert context.act_output.tools_called[0].tool_name == "get_billing_info"
        assert context.act_output.kb_citations[0].doc_id == "kb/policies/02-late-fees.md"

        # Round-trip serialize the fully populated context
        serialized = context.model_dump()
        assert serialized["customer_message"] == "What is my current bill?"
        assert serialized["classify_output"]["intent"] == "billing"
        assert serialized["routing_decision"] == "billing_path"
        assert serialized["act_output"]["resolution_status"] == "resolved"
        assert len(serialized["act_output"]["tools_called"]) == 1

        restored = StateContext.model_validate(serialized)
        assert restored.customer_message == context.customer_message
        assert restored.classify_output.intent == context.classify_output.intent
        assert restored.routing_decision == context.routing_decision
        assert restored.act_output.resolution_status == context.act_output.resolution_status

    def test_nested_model_validation_cascade(self) -> None:
        """Test that nested model validation errors surface correctly, not silently swallowed."""
        # Create an ActOutput with invalid ToolCallRecord (missing required field)
        with pytest.raises(ValidationError) as exc_info:
            ActOutput(
                resolution_status="resolved",
                tools_called=[
                    {
                        # Missing 'tool_name' - required field
                        "input": {"account_id": "ACC-10001"},
                        "result_summary": "Retrieved info",
                        "called_at": "2026-06-17T14:30:00Z",
                        "success": True
                    }
                ],
                kb_citations=[]
            )

        # Verify the error identifies the nested field that failed
        error_str = str(exc_info.value)
        assert "tool_name" in error_str.lower()
        assert "tools_called" in error_str.lower() or "field required" in error_str.lower()

        # Verify the error is a ValidationError, not swallowed
        assert isinstance(exc_info.value, ValidationError)

    def test_full_state_machine_output_bundle(self) -> None:
        """Test RespondOutput with citations through full serialization round-trip."""
        # Build a RespondOutput with citations
        response = RespondOutput(
            message="According to our late payment policy, the grace period is 5 business days.",
            citations=["kb/policies/02-late-fees.md", "kb/policies/01-billing.md"],
            metadata={
                "kb_docs_used": 2,
                "tools_called": 0,
                "escalation_offered": False
            }
        )

        # Serialize to JSON-compatible dict
        serialized = response.model_dump()
        assert serialized["message"] == "According to our late payment policy, the grace period is 5 business days."
        assert len(serialized["citations"]) == 2
        assert serialized["citations"][0] == "kb/policies/02-late-fees.md"
        assert serialized["metadata"]["kb_docs_used"] == 2

        # Parse JSON back into RespondOutput
        restored = RespondOutput.model_validate(serialized)

        # Verify all fields including citations list survived round-trip
        assert restored.message == response.message
        assert restored.citations == response.citations
        assert len(restored.citations) == 2
        assert restored.citations[0] == "kb/policies/02-late-fees.md"
        assert restored.citations[1] == "kb/policies/01-billing.md"
        assert restored.metadata == response.metadata
        assert restored.metadata["kb_docs_used"] == 2
        assert restored.metadata["escalation_offered"] is False

    def test_cross_model_field_consistency(self) -> None:
        """Test correlation_id consistency across SessionState and StateContext."""
        # Use the same correlation_id in SessionState
        correlation_id = "corr-consistency-test-abc123"

        session = SessionState(
            session_id="SESS-001",
            correlation_id=correlation_id,
            account_id="ACC-10001",
            detected_emotion="neutral",
            started_at="2026-06-17T14:00:00Z",
            last_updated="2026-06-17T14:30:00Z"
        )

        # Create a StateContext referencing that SessionState
        context = StateContext(
            session_state=session,
            customer_message="Test message"
        )

        # Verify context.session_state.correlation_id matches what was set
        assert context.session_state.correlation_id == correlation_id
        assert context.session_state.correlation_id == "corr-consistency-test-abc123"

        # Verify no copy-loss through model_dump/model_validate
        serialized = context.model_dump()
        assert serialized["session_state"]["correlation_id"] == correlation_id

        restored = StateContext.model_validate(serialized)
        assert restored.session_state.correlation_id == correlation_id
        assert restored.session_state.correlation_id == session.correlation_id

        # Verify nested field access still works after round-trip
        assert restored.session_state.account_id == "ACC-10001"
        assert restored.session_state.detected_emotion == "neutral"
