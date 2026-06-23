"""Unit tests for EscalateState escalation ticket generation."""

import copy
import json
from unittest.mock import MagicMock, call, patch

import pytest

from src.config import get_config
from src.orchestrator.agents.factory import AgentFactory
from src.orchestrator.models import (
    ActOutput,
    ClassifyOutput,
    RoutingDecision,
    SessionState,
    StateContext,
    ToolCallRecord,
)
from src.orchestrator.states.escalate import EscalateState
from src.tools.escalation import CreateEscalationTicketResult


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
    """AgentFactory mock with a pre-configured escalate agent."""
    factory = MagicMock(spec=AgentFactory)
    factory.get_escalate_agent.return_value = MagicMock(id="agent-escalate-001")
    return factory


@pytest.fixture
def state(mock_factory: MagicMock) -> EscalateState:
    """EscalateState under test with mocked factory."""
    return EscalateState(mock_factory)


@pytest.fixture
def session() -> SessionState:
    """Minimal SessionState with no emotion and no history."""
    return SessionState(
        session_id="SESS-001",
        correlation_id="corr-001",
        account_id="ACC-001",
        conversation_history=[],
        detected_emotion=None,
        channel="chat",
        started_at="2026-06-23T10:00:00Z",
        last_updated="2026-06-23T10:00:00Z",
    )


@pytest.fixture
def classify_out() -> ClassifyOutput:
    """Standard ClassifyOutput with billing intent."""
    return ClassifyOutput(
        intent="billing",
        confidence=0.92,
        detected_emotion=None,
        off_topic=False,
    )


@pytest.fixture
def skip_context(session: SessionState, classify_out: ClassifyOutput) -> StateContext:
    """Context for SKIP_TO_ESCALATE path (act_output is None)."""
    return StateContext(
        session_state=session,
        customer_message="I need to speak to a human.",
        routing_decision=RoutingDecision.SKIP_TO_ESCALATE,
        classify_output=classify_out,
        act_output=None,
    )


@pytest.fixture
def unresolved_context(session: SessionState, classify_out: ClassifyOutput) -> StateContext:
    """Context for post-Act unresolved path (act_output populated)."""
    act_out = ActOutput(
        resolution_status="unresolved",
        tools_called=[
            ToolCallRecord(
                tool_name="get_billing_info",
                input={"account_id": "ACC-001", "months": 3},
                result_summary="data_unavailable after retry",
                called_at="2026-06-23T10:00:05Z",
                success=False,
                error_code="data_unavailable",
            )
        ],
        kb_citations=[],
        error_details="data_unavailable",
    )
    return StateContext(
        session_state=session,
        customer_message="My bill is wrong.",
        routing_decision=RoutingDecision.BILLING_PATH,
        classify_output=classify_out,
        act_output=act_out,
    )


def _agent_json(
    summary: str = "Customer needs help with billing.",
    suggested_next_action: str = "Review billing history.",
) -> str:
    """Build a valid EscalateAgent JSON response string."""
    return json.dumps({"summary": summary, "suggested_next_action": suggested_next_action})


def _ticket_ok() -> MagicMock:
    """Successful ticket creation result as plain MagicMock (avoids Pydantic sub-model validation)."""
    mock = MagicMock()
    mock.success = True
    mock.error_code = None
    mock.error_message = None
    mock.ticket = MagicMock()
    return mock


def _ticket_fail() -> CreateEscalationTicketResult:
    """Failed ticket creation result."""
    return CreateEscalationTicketResult(
        success=False,
        error_code="validation_failed",
        error_message="bad payload",
    )


# ---------------------------------------------------------------------------
# TestEscalateStateHappyPaths
# ---------------------------------------------------------------------------


class TestEscalateStateHappyPaths:
    """Tests for successful escalation across both trigger paths."""

    @pytest.mark.asyncio
    async def test_skip_to_escalate_path(
        self, state: EscalateState, skip_context: StateContext
    ) -> None:
        """SKIP_TO_ESCALATE path returns success=True when agent and ticket both succeed."""
        with (
            patch.object(state, "_invoke_agent", return_value=_agent_json()),
            patch(
                "src.orchestrator.states.escalate.create_escalation_ticket",
                return_value=_ticket_ok(),
            ),
        ):
            result = await state.run(skip_context)
        assert result.success is True

    @pytest.mark.asyncio
    async def test_post_act_unresolved_path(
        self, state: EscalateState, unresolved_context: StateContext
    ) -> None:
        """Post-Act unresolved path calls create_escalation_ticket and returns success."""
        with (
            patch.object(state, "_invoke_agent", return_value=_agent_json()),
            patch(
                "src.orchestrator.states.escalate.create_escalation_ticket",
                return_value=_ticket_ok(),
            ) as mock_ticket,
        ):
            result = await state.run(unresolved_context)
        assert result.success is True
        mock_ticket.assert_called_once()


# ---------------------------------------------------------------------------
# TestEscalateStateAgentFallback
# ---------------------------------------------------------------------------


class TestEscalateStateAgentFallback:
    """Tests for EscalateAgent failure handling."""

    @pytest.mark.asyncio
    async def test_agent_failure_still_calls_create_ticket(
        self, state: EscalateState, skip_context: StateContext
    ) -> None:
        """Agent failure falls back to hardcoded strings and still calls create_escalation_ticket."""
        with (
            patch.object(state, "_invoke_agent", side_effect=RuntimeError("agent timeout")),
            patch(
                "src.orchestrator.states.escalate.create_escalation_ticket",
                return_value=_ticket_ok(),
            ) as mock_ticket,
        ):
            result = await state.run(skip_context)
        mock_ticket.assert_called_once()
        assert result.success is True

    @pytest.mark.asyncio
    async def test_agent_failure_uses_hardcoded_summary(
        self, state: EscalateState, skip_context: StateContext
    ) -> None:
        """Agent failure causes payload to contain the hardcoded fallback summary text."""
        captured_payload: list[dict] = []

        def capture_ticket(payload: dict) -> CreateEscalationTicketResult:
            captured_payload.append(payload)
            return _ticket_ok()

        with (
            patch.object(state, "_invoke_agent", side_effect=RuntimeError("agent timeout")),
            patch(
                "src.orchestrator.states.escalate.create_escalation_ticket",
                side_effect=capture_ticket,
            ),
        ):
            await state.run(skip_context)

        assert len(captured_payload) == 1
        assert "manual review" in captured_payload[0]["summary"].lower()


# ---------------------------------------------------------------------------
# TestEscalateStateTicketFailure
# ---------------------------------------------------------------------------


class TestEscalateStateTicketFailure:
    """Tests for create_escalation_ticket failure handling."""

    @pytest.mark.asyncio
    async def test_ticket_creation_failure_returns_result(
        self, state: EscalateState, skip_context: StateContext
    ) -> None:
        """create_escalation_ticket failure is returned directly (not raised)."""
        with (
            patch.object(state, "_invoke_agent", return_value=_agent_json()),
            patch(
                "src.orchestrator.states.escalate.create_escalation_ticket",
                return_value=_ticket_fail(),
            ),
        ):
            result = await state.run(skip_context)
        assert result.success is False
        assert result.error_code == "validation_failed"


# ---------------------------------------------------------------------------
# TestEscalateStateReasonCode
# ---------------------------------------------------------------------------


class TestEscalateStateReasonCode:
    """Tests for reason_code selection logic."""

    @pytest.mark.asyncio
    async def test_reason_code_tool_failure_when_act_unresolved(
        self, state: EscalateState, unresolved_context: StateContext
    ) -> None:
        """act_output.resolution_status='unresolved' produces reason_code='tool_failure'."""
        captured: list[dict] = []

        with (
            patch.object(state, "_invoke_agent", return_value=_agent_json()),
            patch(
                "src.orchestrator.states.escalate.create_escalation_ticket",
                side_effect=lambda p: captured.append(p) or _ticket_ok(),
            ),
        ):
            await state.run(unresolved_context)

        assert captured[0]["reason_code"] == "tool_failure"

    @pytest.mark.asyncio
    async def test_reason_code_out_of_scope_for_skip_to_escalate(
        self, state: EscalateState, session: SessionState
    ) -> None:
        """SKIP_TO_ESCALATE with intent='escalate' produces reason_code='out_of_scope'."""
        context = StateContext(
            session_state=session,
            customer_message="I want a human agent.",
            routing_decision=RoutingDecision.SKIP_TO_ESCALATE,
            classify_output=ClassifyOutput(
                intent="escalate", confidence=0.95, detected_emotion=None, off_topic=False
            ),
            act_output=None,
        )
        captured: list[dict] = []

        with (
            patch.object(state, "_invoke_agent", return_value=_agent_json()),
            patch(
                "src.orchestrator.states.escalate.create_escalation_ticket",
                side_effect=lambda p: captured.append(p) or _ticket_ok(),
            ),
        ):
            await state.run(context)

        assert captured[0]["reason_code"] == "out_of_scope"

    @pytest.mark.asyncio
    async def test_reason_code_customer_frustration(
        self, state: EscalateState, classify_out: ClassifyOutput
    ) -> None:
        """detected_emotion='frustrated' produces reason_code='customer_frustration'."""
        frustrated_session = SessionState(
            session_id="SESS-002",
            correlation_id="corr-002",
            account_id="ACC-002",
            conversation_history=[],
            detected_emotion="frustrated",
            channel="chat",
            started_at="2026-06-23T10:00:00Z",
            last_updated="2026-06-23T10:00:00Z",
        )
        context = StateContext(
            session_state=frustrated_session,
            customer_message="This is ridiculous.",
            routing_decision=RoutingDecision.SKIP_TO_ESCALATE,
            classify_output=classify_out,
            act_output=None,
        )
        captured: list[dict] = []

        with (
            patch.object(state, "_invoke_agent", return_value=_agent_json()),
            patch(
                "src.orchestrator.states.escalate.create_escalation_ticket",
                side_effect=lambda p: captured.append(p) or _ticket_ok(),
            ),
        ):
            await state.run(context)

        assert captured[0]["reason_code"] == "customer_frustration"


# ---------------------------------------------------------------------------
# TestEscalateStateMutationContract
# ---------------------------------------------------------------------------


class TestEscalateStateMutationContract:
    """Tests for pure-function (no mutation) contract."""

    @pytest.mark.asyncio
    async def test_does_not_mutate_context(
        self, state: EscalateState, skip_context: StateContext
    ) -> None:
        """EscalateState must not mutate the input context."""
        context_before = copy.deepcopy(skip_context)
        with (
            patch.object(state, "_invoke_agent", return_value=_agent_json()),
            patch(
                "src.orchestrator.states.escalate.create_escalation_ticket",
                return_value=_ticket_ok(),
            ),
        ):
            await state.run(skip_context)
        assert skip_context.model_dump() == context_before.model_dump()


# ---------------------------------------------------------------------------
# TestEscalateStateEdgeCases
# ---------------------------------------------------------------------------


class TestEscalateStateEdgeCases:
    """Tests for optional-field edge cases."""

    @pytest.mark.asyncio
    async def test_classify_output_none_uses_unknown_intent(
        self, state: EscalateState, session: SessionState
    ) -> None:
        """classify_output=None defaults to intent.primary='unknown' in the payload."""
        context = StateContext(
            session_state=session,
            customer_message="Help.",
            classify_output=None,
            act_output=None,
        )
        captured: list[dict] = []

        with (
            patch.object(state, "_invoke_agent", return_value=_agent_json()),
            patch(
                "src.orchestrator.states.escalate.create_escalation_ticket",
                side_effect=lambda p: captured.append(p) or _ticket_ok(),
            ),
        ):
            await state.run(context)

        assert captured[0]["intent"]["primary"] == "unknown"

    @pytest.mark.asyncio
    async def test_detected_emotion_none_defaults_neutral(
        self, state: EscalateState, skip_context: StateContext
    ) -> None:
        """detected_emotion=None defaults to customer_emotion.sentiment='neutral' in payload."""
        # skip_context.session_state.detected_emotion is already None per fixture
        captured: list[dict] = []

        with (
            patch.object(state, "_invoke_agent", return_value=_agent_json()),
            patch(
                "src.orchestrator.states.escalate.create_escalation_ticket",
                side_effect=lambda p: captured.append(p) or _ticket_ok(),
            ),
        ):
            await state.run(skip_context)

        assert captured[0]["customer_emotion"]["sentiment"] == "neutral"

    @pytest.mark.asyncio
    async def test_act_output_none_tools_called_empty(
        self, state: EscalateState, skip_context: StateContext
    ) -> None:
        """act_output=None results in tools_called=[] in the assembled payload."""
        captured: list[dict] = []

        with (
            patch.object(state, "_invoke_agent", return_value=_agent_json()),
            patch(
                "src.orchestrator.states.escalate.create_escalation_ticket",
                side_effect=lambda p: captured.append(p) or _ticket_ok(),
            ),
        ):
            await state.run(skip_context)

        assert captured[0]["tools_called"] == []
