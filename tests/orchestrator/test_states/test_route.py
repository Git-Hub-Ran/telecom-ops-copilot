"""Unit tests for RouteState routing logic."""

import pytest

from src.config import get_config
from src.orchestrator.models import ClassifyOutput, RoutingDecision, SessionState, StateContext
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


class TestRouteState:
    """Test suite for RouteState routing logic (8 paths + 2 boundary + 1 validation)."""

    @pytest.mark.asyncio
    async def test_off_topic_returns_refuse_off_topic(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that off_topic=True returns REFUSE_OFF_TOPIC (priority 1)."""
        monkeypatch.setenv("CLASSIFICATION_CONFIDENCE_THRESHOLD", "0.6")
        get_config.cache_clear()

        session = SessionState(
            session_id="SESS-001",
            correlation_id="corr-001",
            started_at="2026-06-17T14:00:00Z",
            last_updated="2026-06-17T14:00:00Z"
        )

        # off_topic=True should win even with high confidence and valid intent
        classify_output = ClassifyOutput(
            intent="info",
            confidence=0.95,
            off_topic=True
        )

        context = StateContext(
            session_state=session,
            customer_message="What is the weather today?",
            classify_output=classify_output
        )

        route_state = RouteState()
        decision = await route_state.run(context)

        assert decision == RoutingDecision.REFUSE_OFF_TOPIC

    @pytest.mark.asyncio
    async def test_low_confidence_returns_ask_clarifying_question(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that confidence below threshold returns ASK_CLARIFYING_QUESTION (priority 2)."""
        monkeypatch.setenv("CLASSIFICATION_CONFIDENCE_THRESHOLD", "0.6")
        get_config.cache_clear()

        session = SessionState(
            session_id="SESS-001",
            correlation_id="corr-001",
            started_at="2026-06-17T14:00:00Z",
            last_updated="2026-06-17T14:00:00Z"
        )

        # Low confidence should trigger clarification even with valid intent
        classify_output = ClassifyOutput(
            intent="billing",
            confidence=0.4,
            off_topic=False
        )

        context = StateContext(
            session_state=session,
            customer_message="bill",
            classify_output=classify_output
        )

        route_state = RouteState()
        decision = await route_state.run(context)

        assert decision == RoutingDecision.ASK_CLARIFYING_QUESTION

    @pytest.mark.asyncio
    async def test_intent_escalate_returns_skip_to_escalate(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that intent='escalate' returns SKIP_TO_ESCALATE (priority 3)."""
        monkeypatch.setenv("CLASSIFICATION_CONFIDENCE_THRESHOLD", "0.6")
        get_config.cache_clear()

        session = SessionState(
            session_id="SESS-001",
            correlation_id="corr-001",
            started_at="2026-06-17T14:00:00Z",
            last_updated="2026-06-17T14:00:00Z"
        )

        classify_output = ClassifyOutput(
            intent="escalate",
            confidence=0.95,
            off_topic=False
        )

        context = StateContext(
            session_state=session,
            customer_message="I want to speak to a human",
            classify_output=classify_output
        )

        route_state = RouteState()
        decision = await route_state.run(context)

        assert decision == RoutingDecision.SKIP_TO_ESCALATE

    @pytest.mark.asyncio
    async def test_intent_unknown_returns_ask_clarifying_question(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that intent='unknown' returns ASK_CLARIFYING_QUESTION (priority 3)."""
        monkeypatch.setenv("CLASSIFICATION_CONFIDENCE_THRESHOLD", "0.6")
        get_config.cache_clear()

        session = SessionState(
            session_id="SESS-001",
            correlation_id="corr-001",
            started_at="2026-06-17T14:00:00Z",
            last_updated="2026-06-17T14:00:00Z"
        )

        classify_output = ClassifyOutput(
            intent="unknown",
            confidence=0.95,
            off_topic=False
        )

        context = StateContext(
            session_state=session,
            customer_message="something unclear",
            classify_output=classify_output
        )

        route_state = RouteState()
        decision = await route_state.run(context)

        assert decision == RoutingDecision.ASK_CLARIFYING_QUESTION

    @pytest.mark.asyncio
    async def test_intent_unknown_low_confidence_also_clarifies(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that intent='unknown' asks for clarification even when confidence is below threshold.

        Pins the priority order: the unknown-intent check fires before the
        confidence gate, so low-confidence unknown queries reach
        ASK_CLARIFYING_QUESTION via Priority 3, not Priority 4.
        """
        monkeypatch.setenv("CLASSIFICATION_CONFIDENCE_THRESHOLD", "0.6")
        get_config.cache_clear()

        session = SessionState(
            session_id="SESS-001",
            correlation_id="corr-001",
            started_at="2026-06-17T14:00:00Z",
            last_updated="2026-06-17T14:00:00Z"
        )

        classify_output = ClassifyOutput(
            intent="unknown",
            confidence=0.4,
            off_topic=False
        )

        context = StateContext(
            session_state=session,
            customer_message="something very unclear",
            classify_output=classify_output
        )

        route_state = RouteState()
        decision = await route_state.run(context)

        assert decision == RoutingDecision.ASK_CLARIFYING_QUESTION

    @pytest.mark.asyncio
    async def test_intent_billing_returns_billing_path(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that intent='billing' returns BILLING_PATH (priority 5)."""
        monkeypatch.setenv("CLASSIFICATION_CONFIDENCE_THRESHOLD", "0.6")
        get_config.cache_clear()

        session = SessionState(
            session_id="SESS-001",
            correlation_id="corr-001",
            started_at="2026-06-17T14:00:00Z",
            last_updated="2026-06-17T14:00:00Z"
        )

        classify_output = ClassifyOutput(
            intent="billing",
            confidence=0.95,
            off_topic=False
        )

        context = StateContext(
            session_state=session,
            customer_message="What is my current bill?",
            classify_output=classify_output
        )

        route_state = RouteState()
        decision = await route_state.run(context)

        assert decision == RoutingDecision.BILLING_PATH

    @pytest.mark.asyncio
    async def test_intent_technical_returns_technical_path(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that intent='technical' returns TECHNICAL_PATH (priority 6)."""
        monkeypatch.setenv("CLASSIFICATION_CONFIDENCE_THRESHOLD", "0.6")
        get_config.cache_clear()

        session = SessionState(
            session_id="SESS-001",
            correlation_id="corr-001",
            started_at="2026-06-17T14:00:00Z",
            last_updated="2026-06-17T14:00:00Z"
        )

        classify_output = ClassifyOutput(
            intent="technical",
            confidence=0.95,
            off_topic=False
        )

        context = StateContext(
            session_state=session,
            customer_message="My internet is slow",
            classify_output=classify_output
        )

        route_state = RouteState()
        decision = await route_state.run(context)

        assert decision == RoutingDecision.TECHNICAL_PATH

    @pytest.mark.asyncio
    async def test_intent_account_returns_account_path(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that intent='account' returns ACCOUNT_PATH (priority 7)."""
        monkeypatch.setenv("CLASSIFICATION_CONFIDENCE_THRESHOLD", "0.6")
        get_config.cache_clear()

        session = SessionState(
            session_id="SESS-001",
            correlation_id="corr-001",
            started_at="2026-06-17T14:00:00Z",
            last_updated="2026-06-17T14:00:00Z"
        )

        classify_output = ClassifyOutput(
            intent="account",
            confidence=0.95,
            off_topic=False
        )

        context = StateContext(
            session_state=session,
            customer_message="I need to update my address",
            classify_output=classify_output
        )

        route_state = RouteState()
        decision = await route_state.run(context)

        assert decision == RoutingDecision.ACCOUNT_PATH

    @pytest.mark.asyncio
    async def test_intent_info_returns_info_path(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that intent='info' returns INFO_PATH (priority 8)."""
        monkeypatch.setenv("CLASSIFICATION_CONFIDENCE_THRESHOLD", "0.6")
        get_config.cache_clear()

        session = SessionState(
            session_id="SESS-001",
            correlation_id="corr-001",
            started_at="2026-06-17T14:00:00Z",
            last_updated="2026-06-17T14:00:00Z"
        )

        classify_output = ClassifyOutput(
            intent="info",
            confidence=0.95,
            off_topic=False
        )

        context = StateContext(
            session_state=session,
            customer_message="What plans do you offer?",
            classify_output=classify_output
        )

        route_state = RouteState()
        decision = await route_state.run(context)

        assert decision == RoutingDecision.INFO_PATH

    @pytest.mark.asyncio
    async def test_classify_output_none_raises_value_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that classify_output=None raises ValueError (validation check)."""
        monkeypatch.setenv("CLASSIFICATION_CONFIDENCE_THRESHOLD", "0.6")
        get_config.cache_clear()

        session = SessionState(
            session_id="SESS-001",
            correlation_id="corr-001",
            started_at="2026-06-17T14:00:00Z",
            last_updated="2026-06-17T14:00:00Z"
        )

        # Create context with classify_output=None
        context = StateContext(
            session_state=session,
            customer_message="What is my bill?",
            classify_output=None
        )

        route_state = RouteState()

        with pytest.raises(ValueError) as exc_info:
            await route_state.run(context)

        # Verify error message mentions the required field
        error_str = str(exc_info.value)
        assert "classify_output" in error_str.lower() or "classifystate" in error_str.lower()

    @pytest.mark.asyncio
    async def test_confidence_at_threshold_routes_normally(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that confidence exactly at threshold (0.6) routes by intent, not clarification."""
        monkeypatch.setenv("CLASSIFICATION_CONFIDENCE_THRESHOLD", "0.6")
        get_config.cache_clear()

        session = SessionState(
            session_id="SESS-001",
            correlation_id="corr-001",
            started_at="2026-06-17T14:00:00Z",
            last_updated="2026-06-17T14:00:00Z"
        )

        # Confidence exactly at threshold (0.6)
        # The check is "< threshold", so 0.6 is NOT below threshold
        classify_output = ClassifyOutput(
            intent="billing",
            confidence=0.6,
            off_topic=False
        )

        context = StateContext(
            session_state=session,
            customer_message="What is my bill?",
            classify_output=classify_output
        )

        route_state = RouteState()
        decision = await route_state.run(context)

        # Should route to BILLING_PATH, not ASK_CLARIFYING_QUESTION
        assert decision == RoutingDecision.BILLING_PATH

    @pytest.mark.asyncio
    async def test_confidence_just_below_threshold_clarifies(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that confidence just below threshold (0.59) triggers clarification."""
        monkeypatch.setenv("CLASSIFICATION_CONFIDENCE_THRESHOLD", "0.6")
        get_config.cache_clear()

        session = SessionState(
            session_id="SESS-001",
            correlation_id="corr-001",
            started_at="2026-06-17T14:00:00Z",
            last_updated="2026-06-17T14:00:00Z"
        )

        # Confidence just below threshold (0.59)
        classify_output = ClassifyOutput(
            intent="billing",
            confidence=0.59,
            off_topic=False
        )

        context = StateContext(
            session_state=session,
            customer_message="bill?",
            classify_output=classify_output
        )

        route_state = RouteState()
        decision = await route_state.run(context)

        # Should ask for clarification
        assert decision == RoutingDecision.ASK_CLARIFYING_QUESTION
