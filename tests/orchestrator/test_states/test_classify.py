"""Unit tests for ClassifyState intent classification."""

import copy
import json
from unittest.mock import MagicMock, patch

import pytest

from src.config import get_config
from src.orchestrator.agents.factory import AgentFactory
from src.orchestrator.models import (
    ClassifyOutput,
    ConversationTurn,
    SessionState,
    StateContext,
)
from src.orchestrator.states.classify import (
    ClassifyState,
    _build_prompt_content,
    _extract_assistant_text,
    _fallback_output,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def setup_test_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set required environment variables for Config singleton."""
    monkeypatch.setenv(
        "AZURE_FOUNDRY_PROJECT_ENDPOINT", "https://test.ai.azure.com/api/projects/test"
    )
    monkeypatch.setenv("AZURE_TENANT_ID", "12345678-1234-1234-1234-123456789abc")
    monkeypatch.setenv("VECTOR_STORE_ID", "vs_test")
    get_config.cache_clear()


@pytest.fixture
def mock_factory() -> MagicMock:
    """AgentFactory mock with a pre-configured classifier agent."""
    factory = MagicMock(spec=AgentFactory)
    factory.get_classifier_agent.return_value = MagicMock(id="agent-classifier-001")
    return factory


@pytest.fixture
def state(mock_factory: MagicMock) -> ClassifyState:
    """ClassifyState under test with mocked factory."""
    return ClassifyState(mock_factory)


@pytest.fixture
def session() -> SessionState:
    """Minimal SessionState with no conversation history."""
    return SessionState(
        session_id="SESS-001",
        correlation_id="corr-001",
        account_id="ACC-001",
        conversation_history=[],
        started_at="2026-06-23T10:00:00Z",
        last_updated="2026-06-23T10:00:00Z",
    )


@pytest.fixture
def context(session: SessionState) -> StateContext:
    """StateContext with a simple billing question."""
    return StateContext(
        session_state=session,
        customer_message="What is my current bill?",
    )


def _json_response(
    intent: str = "billing",
    confidence: float = 0.92,
    emotion: str | None = "neutral",
    off_topic: bool = False,
) -> str:
    """Build a valid classifier JSON response string."""
    return json.dumps({
        "intent": intent,
        "confidence": confidence,
        "detected_emotion": emotion,
        "off_topic": off_topic,
    })


# ---------------------------------------------------------------------------
# Helper function unit tests
# ---------------------------------------------------------------------------


class TestBuildPromptContent:
    """Tests for _build_prompt_content helper."""

    def test_no_history_returns_just_message(self) -> None:
        """Content with empty history contains only the current message."""
        content = _build_prompt_content("What is my bill?", [])
        assert "Current customer message: What is my bill?" in content
        assert "Conversation history" not in content

    def test_history_included_before_message(self) -> None:
        """Content with history lists turns before the current message."""
        history = [
            ConversationTurn(role="customer", content="Hello", timestamp="2026-06-23T10:00:00Z"),
            ConversationTurn(role="agent", content="Hi!", timestamp="2026-06-23T10:00:05Z"),
        ]
        content = _build_prompt_content("My bill is wrong", history)
        assert "Conversation history" in content
        assert "[customer]: Hello" in content
        assert "[agent]: Hi!" in content
        assert "Current customer message: My bill is wrong" in content
        # History must appear before current message
        assert content.index("Conversation history") < content.index("Current customer message")

    def test_all_history_turns_included(self) -> None:
        """All turns in history appear in the content."""
        history = [
            ConversationTurn(role="customer", content=f"msg{i}", timestamp="2026-06-23T10:00:00Z")
            for i in range(5)
        ]
        content = _build_prompt_content("final", history)
        for i in range(5):
            assert f"msg{i}" in content


class TestExtractAssistantText:
    """Tests for _extract_assistant_text helper."""

    def _make_message(self, role: str, text: str) -> MagicMock:
        item = MagicMock()
        item.text.value = text
        msg = MagicMock()
        msg.role = role
        msg.content = [item]
        return msg

    def test_extracts_text_from_assistant_message(self) -> None:
        """Returns text value from an assistant role message."""
        messages = [self._make_message("assistant", '{"intent":"billing"}')]
        assert _extract_assistant_text(messages) == '{"intent":"billing"}'

    def test_extracts_text_from_agent_role(self) -> None:
        """Returns text value when role is 'agent' (newer SDK variant)."""
        messages = [self._make_message("agent", '{"intent":"technical"}')]
        assert _extract_assistant_text(messages) == '{"intent":"technical"}'

    def test_skips_user_messages(self) -> None:
        """Skips user messages and finds the assistant response."""
        user_msg = self._make_message("user", "ignored")
        assistant_msg = self._make_message("assistant", '{"intent":"info"}')
        assert _extract_assistant_text([user_msg, assistant_msg]) == '{"intent":"info"}'

    def test_raises_if_no_assistant_message(self) -> None:
        """Raises RuntimeError if no assistant message exists."""
        messages = [self._make_message("user", "only user")]
        with pytest.raises(RuntimeError, match="No assistant text response"):
            _extract_assistant_text(messages)

    def test_raises_on_empty_message_list(self) -> None:
        """Raises RuntimeError on empty message list."""
        with pytest.raises(RuntimeError):
            _extract_assistant_text([])


class TestFallbackOutput:
    """Tests for _fallback_output helper."""

    def test_fallback_has_unknown_intent(self) -> None:
        result = _fallback_output()
        assert result.intent == "unknown"

    def test_fallback_has_zero_confidence(self) -> None:
        result = _fallback_output()
        assert result.confidence == 0.0

    def test_fallback_is_not_off_topic(self) -> None:
        result = _fallback_output()
        assert result.off_topic is False

    def test_fallback_has_no_emotion(self) -> None:
        result = _fallback_output()
        assert result.detected_emotion is None

    def test_fallback_returns_new_instance_each_time(self) -> None:
        """Each call returns a fresh object (no shared mutable state)."""
        a = _fallback_output()
        b = _fallback_output()
        assert a is not b


# ---------------------------------------------------------------------------
# ClassifyState.run() - happy paths
# ---------------------------------------------------------------------------


class TestClassifyStateHappyPaths:
    """Tests for successful classification across all 6 intent values."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("intent", ["billing", "technical", "account", "info", "escalate", "unknown"])
    async def test_all_six_intents(
        self, state: ClassifyState, context: StateContext, intent: str
    ) -> None:
        """Each valid intent value is returned correctly from a JSON response."""
        response = _json_response(intent=intent, confidence=0.85)
        with patch.object(state, "_invoke_agent", return_value=response):
            result = await state.run(context)
        assert result.intent == intent

    @pytest.mark.asyncio
    async def test_returns_correct_confidence(
        self, state: ClassifyState, context: StateContext
    ) -> None:
        """Confidence score from JSON is preserved in the result."""
        response = _json_response(confidence=0.75)
        with patch.object(state, "_invoke_agent", return_value=response):
            result = await state.run(context)
        assert result.confidence == 0.75

    @pytest.mark.asyncio
    async def test_off_topic_true(
        self, state: ClassifyState, context: StateContext
    ) -> None:
        """off_topic=true in JSON response is returned correctly."""
        response = _json_response(intent="escalate", off_topic=True)
        with patch.object(state, "_invoke_agent", return_value=response):
            result = await state.run(context)
        assert result.off_topic is True

    @pytest.mark.asyncio
    async def test_emotion_detected(
        self, state: ClassifyState, context: StateContext
    ) -> None:
        """detected_emotion from JSON is returned correctly."""
        response = _json_response(intent="billing", emotion="frustrated")
        with patch.object(state, "_invoke_agent", return_value=response):
            result = await state.run(context)
        assert result.detected_emotion == "frustrated"

    @pytest.mark.asyncio
    async def test_null_emotion_returns_none(
        self, state: ClassifyState, context: StateContext
    ) -> None:
        """detected_emotion=null in JSON maps to None in ClassifyOutput."""
        response = _json_response(intent="info", emotion=None)
        with patch.object(state, "_invoke_agent", return_value=response):
            result = await state.run(context)
        assert result.detected_emotion is None


# ---------------------------------------------------------------------------
# ClassifyState.run() - error / fallback cases
# ---------------------------------------------------------------------------


class TestClassifyStateFallbacks:
    """Tests for error handling - all errors must return the fallback output."""

    @pytest.mark.asyncio
    async def test_timeout_exception_returns_fallback(
        self, state: ClassifyState, context: StateContext
    ) -> None:
        """An exception (e.g., timeout) from _invoke_agent returns fallback."""
        with patch.object(state, "_invoke_agent", side_effect=TimeoutError("agent timed out")):
            result = await state.run(context)
        assert result.intent == "unknown"
        assert result.confidence == 0.0

    @pytest.mark.asyncio
    async def test_malformed_json_returns_fallback(
        self, state: ClassifyState, context: StateContext
    ) -> None:
        """Malformed JSON from the agent returns fallback."""
        with patch.object(state, "_invoke_agent", return_value="not valid json {{{"):
            result = await state.run(context)
        assert result.intent == "unknown"
        assert result.confidence == 0.0

    @pytest.mark.asyncio
    async def test_invalid_intent_value_returns_fallback(
        self, state: ClassifyState, context: StateContext
    ) -> None:
        """A valid JSON but unknown intent enum triggers Pydantic validation error -> fallback."""
        bad_response = json.dumps({
            "intent": "sports",
            "confidence": 0.9,
            "detected_emotion": "neutral",
            "off_topic": False,
        })
        with patch.object(state, "_invoke_agent", return_value=bad_response):
            result = await state.run(context)
        assert result.intent == "unknown"

    @pytest.mark.asyncio
    async def test_confidence_out_of_range_returns_fallback(
        self, state: ClassifyState, context: StateContext
    ) -> None:
        """confidence > 1.0 triggers Pydantic validation error -> fallback."""
        bad_response = json.dumps({
            "intent": "billing",
            "confidence": 1.5,
            "detected_emotion": None,
            "off_topic": False,
        })
        with patch.object(state, "_invoke_agent", return_value=bad_response):
            result = await state.run(context)
        assert result.intent == "unknown"

    @pytest.mark.asyncio
    async def test_http_error_returns_fallback(
        self, state: ClassifyState, context: StateContext
    ) -> None:
        """An HttpResponseError from the agent client returns fallback."""
        from azure.core.exceptions import HttpResponseError
        with patch.object(state, "_invoke_agent", side_effect=HttpResponseError(message="503")):
            result = await state.run(context)
        assert result.intent == "unknown"
        assert result.off_topic is False

    @pytest.mark.asyncio
    async def test_empty_message_raises_value_error(
        self, state: ClassifyState, session: SessionState
    ) -> None:
        """Empty customer_message raises ValueError (not a fallback)."""
        context = StateContext(session_state=session, customer_message="")
        with pytest.raises(ValueError, match="non-empty customer_message"):
            await state.run(context)


# ---------------------------------------------------------------------------
# ClassifyState.run() - context and mutation contract
# ---------------------------------------------------------------------------


class TestClassifyStateContextHandling:
    """Tests for correct context reading and mutation contract."""

    @pytest.mark.asyncio
    async def test_does_not_mutate_context(
        self, state: ClassifyState, context: StateContext
    ) -> None:
        """ClassifyState must not mutate the input context (pure function contract)."""
        context_before = copy.deepcopy(context)
        with patch.object(state, "_invoke_agent", return_value=_json_response()):
            await state.run(context)
        assert context.model_dump() == context_before.model_dump()

    @pytest.mark.asyncio
    async def test_history_is_passed_to_invoke_agent(
        self, state: ClassifyState, mock_factory: MagicMock
    ) -> None:
        """Conversation history turns must appear in the content sent to _invoke_agent."""
        history = [
            ConversationTurn(role="customer", content="I was overbilled last month", timestamp="2026-06-23T10:00:00Z"),
            ConversationTurn(role="agent", content="Let me look into that", timestamp="2026-06-23T10:00:05Z"),
        ]
        session = SessionState(
            session_id="SESS-002",
            correlation_id="corr-002",
            conversation_history=history,
            started_at="2026-06-23T10:00:00Z",
            last_updated="2026-06-23T10:00:00Z",
        )
        context = StateContext(
            session_state=session,
            customer_message="Still seeing the wrong charge",
        )
        captured: list[str] = []

        def capture_invoke(agent_id: str, content: str) -> str:
            captured.append(content)
            return _json_response(intent="billing")

        with patch.object(state, "_invoke_agent", side_effect=capture_invoke):
            await state.run(context)

        assert len(captured) == 1
        assert "I was overbilled last month" in captured[0]
        assert "Let me look into that" in captured[0]
        assert "Still seeing the wrong charge" in captured[0]

    @pytest.mark.asyncio
    async def test_current_message_always_in_content(
        self, state: ClassifyState, context: StateContext
    ) -> None:
        """The customer_message is always present in the content sent to the agent."""
        captured: list[str] = []

        def capture_invoke(agent_id: str, content: str) -> str:
            captured.append(content)
            return _json_response()

        with patch.object(state, "_invoke_agent", side_effect=capture_invoke):
            await state.run(context)

        assert "What is my current bill?" in captured[0]

    @pytest.mark.asyncio
    async def test_uses_classifier_agent(
        self, state: ClassifyState, context: StateContext, mock_factory: MagicMock
    ) -> None:
        """ClassifyState calls get_classifier_agent() on the factory."""
        with patch.object(state, "_invoke_agent", return_value=_json_response()):
            await state.run(context)
        mock_factory.get_classifier_agent.assert_called_once()
