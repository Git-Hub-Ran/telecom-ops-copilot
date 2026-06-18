"""Integration tests for RouteState priority and state mutation verification.

These tests verify that RouteState correctly enforces priority rules when multiple
conditions are simultaneously true, and that the state does not mutate the input
context (pure function behavior).
"""

import copy

import pytest

from src.config import get_config
from src.orchestrator.models import (
    ClassifyOutput,
    ConversationTurn,
    RoutingDecision,
    SessionState,
    StateContext,
)
from src.orchestrator.states.route import RouteState


@pytest.fixture(autouse=True)
def setup_test_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Setup required environment variables for all tests."""
    # Set required Config env vars
    monkeypatch.setenv("AZURE_FOUNDRY_PROJECT_ENDPOINT", "https://test.ai.azure.com/api/projects/test")
    monkeypatch.setenv("AZURE_TENANT_ID", "12345678-1234-1234-1234-123456789abc")
    monkeypatch.setenv("VECTOR_STORE_ID", "vs_test")
    monkeypatch.setenv("CLASSIFICATION_CONFIDENCE_THRESHOLD", "0.6")
    # Clear cache so new env vars take effect
    get_config.cache_clear()


class TestRouteStatePriority:
    """Integration tests verifying priority rules and state immutability."""

    @pytest.mark.asyncio
    async def test_priority_off_topic_beats_low_confidence(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that off_topic (priority 1) beats low confidence (priority 2).

        When both off_topic=True AND confidence < threshold are true, the result
        should be REFUSE_OFF_TOPIC, not ASK_CLARIFYING_QUESTION. This proves the
        priority order is enforced correctly in the code.
        """
        monkeypatch.setenv("CLASSIFICATION_CONFIDENCE_THRESHOLD", "0.6")
        get_config.cache_clear()

        session = SessionState(
            session_id="SESS-INT-001",
            correlation_id="corr-int-001",
            started_at="2026-06-17T14:00:00Z",
            last_updated="2026-06-17T14:00:00Z"
        )

        # Both conditions are true: off_topic AND confidence below threshold
        classify_output = ClassifyOutput(
            intent="info",
            confidence=0.3,  # Below 0.6 threshold
            off_topic=True,  # Priority 1 condition
            detected_emotion="neutral"
        )

        context = StateContext(
            session_state=session,
            customer_message="What is the weather in Paris?",
            classify_output=classify_output
        )

        route_state = RouteState()
        decision = await route_state.run(context)

        # Priority 1 (off_topic) should win over priority 2 (low confidence)
        assert decision == RoutingDecision.REFUSE_OFF_TOPIC

    @pytest.mark.asyncio
    async def test_priority_low_confidence_beats_intent_routing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that low confidence (priority 2) beats intent routing (priority 5-8).

        When both confidence < threshold AND a valid intent are present, the result
        should be ASK_CLARIFYING_QUESTION, not the intent-based path. This ensures
        ambiguous queries are clarified before action.
        """
        monkeypatch.setenv("CLASSIFICATION_CONFIDENCE_THRESHOLD", "0.6")
        get_config.cache_clear()

        session = SessionState(
            session_id="SESS-INT-002",
            correlation_id="corr-int-002",
            started_at="2026-06-17T14:00:00Z",
            last_updated="2026-06-17T14:00:00Z"
        )

        # Both conditions are true: low confidence AND billing intent
        classify_output = ClassifyOutput(
            intent="billing",  # Would normally route to BILLING_PATH (priority 5)
            confidence=0.4,    # Below 0.6 threshold (priority 2)
            off_topic=False,
            detected_emotion="neutral"
        )

        context = StateContext(
            session_state=session,
            customer_message="bill",
            classify_output=classify_output
        )

        route_state = RouteState()
        decision = await route_state.run(context)

        # Priority 2 (low confidence) should win over priority 5 (billing intent)
        assert decision == RoutingDecision.ASK_CLARIFYING_QUESTION

    @pytest.mark.asyncio
    async def test_end_to_end_realistic_flow_with_mutation_check(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test realistic end-to-end flow and verify RouteState does not mutate context.

        This test uses a complete SessionState with conversation history and all
        fields populated. It verifies:
        1. Correct routing for a high-confidence technical intent
        2. StateContext is not mutated by RouteState (pure function behavior)
        3. routing_decision field remains None (state returns decision, does not set it)

        The mutation check is critical: future states (Act, Escalate, Respond) must
        also preserve immutability.
        """
        monkeypatch.setenv("CLASSIFICATION_CONFIDENCE_THRESHOLD", "0.6")
        get_config.cache_clear()

        # Build realistic SessionState with full context
        session = SessionState(
            session_id="SESS-INT-003",
            correlation_id="corr-int-003",
            account_id="ACC-789012",
            detected_emotion="frustrated",
            conversation_history=[
                ConversationTurn(
                    role="customer",
                    content="My internet has been down for 2 hours",
                    timestamp="2026-06-17T14:00:00Z"
                ),
                ConversationTurn(
                    role="agent",
                    content="I understand that is frustrating. Let me help you troubleshoot.",
                    timestamp="2026-06-17T14:00:30Z"
                )
            ],
            started_at="2026-06-17T14:00:00Z",
            last_updated="2026-06-17T14:01:00Z"
        )

        classify_output = ClassifyOutput(
            intent="technical",
            confidence=0.92,
            detected_emotion="frustrated",
            off_topic=False
        )

        context = StateContext(
            session_state=session,
            customer_message="Still not working after reboot",
            classify_output=classify_output
        )

        # Capture deep copy of session_state BEFORE running RouteState
        session_state_before = copy.deepcopy(context.session_state)
        classify_output_before = copy.deepcopy(context.classify_output)

        route_state = RouteState()
        decision = await route_state.run(context)

        # Verify correct routing decision
        assert decision == RoutingDecision.TECHNICAL_PATH

        # CRITICAL: Verify RouteState did not mutate the context
        # 1. session_state unchanged
        assert context.session_state == session_state_before
        assert context.session_state.account_id == "ACC-789012"
        assert context.session_state.detected_emotion == "frustrated"
        assert len(context.session_state.conversation_history) == 2
        assert context.session_state.conversation_history[0].content == "My internet has been down for 2 hours"

        # 2. classify_output unchanged
        assert context.classify_output == classify_output_before
        assert context.classify_output.intent == "technical"
        assert context.classify_output.confidence == 0.92

        # 3. routing_decision still None (RouteState returns the decision, does not set it)
        assert context.routing_decision is None
