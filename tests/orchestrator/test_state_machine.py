"""Unit tests for StateMachine orchestration of the 5-state pipeline."""

import copy
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.config import get_config
from src.orchestrator.agents.factory import AgentFactory
from src.orchestrator.models import (
    ActOutput,
    ClassifyOutput,
    ConversationTurn,
    RespondOutput,
    RoutingDecision,
    SessionState,
)
from src.orchestrator.state_machine import StateMachine
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
    """AgentFactory mock."""
    return MagicMock(spec=AgentFactory)


@pytest.fixture
def machine(mock_factory: MagicMock) -> StateMachine:
    """StateMachine under test."""
    return StateMachine(mock_factory)


@pytest.fixture
def session() -> SessionState:
    """Minimal SessionState with empty history."""
    return SessionState(
        session_id="SESS-001",
        correlation_id="corr-001",
        account_id="ACC-001",
        conversation_history=[],
        started_at="2026-06-24T10:00:00Z",
        last_updated="2026-06-24T10:00:00Z",
        detected_emotion=None,
    )


# ---------------------------------------------------------------------------
# State output helpers
# ---------------------------------------------------------------------------


def _classify_out(
    intent: str = "billing",
    confidence: float = 0.92,
    detected_emotion: str | None = None,
    off_topic: bool = False,
) -> ClassifyOutput:
    return ClassifyOutput(
        intent=intent,
        confidence=confidence,
        detected_emotion=detected_emotion,
        off_topic=off_topic,
    )


def _act_resolved() -> ActOutput:
    return ActOutput(
        resolution_status="resolved",
        tools_called=[],
        kb_citations=[],
        error_details=None,
    )


def _act_unresolved() -> ActOutput:
    return ActOutput(
        resolution_status="unresolved",
        tools_called=[],
        kb_citations=[],
        error_details="data_unavailable",
    )


def _escalate_ok() -> CreateEscalationTicketResult:
    return CreateEscalationTicketResult(success=True)


def _respond_out(msg: str = "Done.") -> RespondOutput:
    return RespondOutput(message=msg, citations=[], metadata={})


# ---------------------------------------------------------------------------
# TestStateMachineHappyPaths
# ---------------------------------------------------------------------------


class TestStateMachineHappyPaths:
    """Tests for all four primary routing branches."""

    @pytest.mark.asyncio
    async def test_billing_resolved_end_to_end(
        self, machine: StateMachine, session: SessionState
    ) -> None:
        """Billing resolved path: Act runs, Escalate skipped, RespondOutput returned."""
        mock_act = AsyncMock(return_value=_act_resolved())
        mock_escalate = AsyncMock(return_value=_escalate_ok())
        with (
            patch.object(machine._classify, "run", new=AsyncMock(return_value=_classify_out())),
            patch.object(machine._route, "run", new=AsyncMock(return_value=RoutingDecision.BILLING_PATH)),
            patch.object(machine._act, "run", new=mock_act),
            patch.object(machine._escalate, "run", new=mock_escalate),
            patch.object(machine._respond, "run", new=AsyncMock(return_value=_respond_out())),
        ):
            result = await machine.process_turn("What is my bill?", session)

        assert result.message == "Done."
        mock_act.assert_called_once()
        mock_escalate.assert_not_called()

    @pytest.mark.asyncio
    async def test_skip_to_escalate_act_not_called(
        self, machine: StateMachine, session: SessionState
    ) -> None:
        """SKIP_TO_ESCALATE path: Act skipped, Escalate runs."""
        mock_act = AsyncMock(return_value=_act_resolved())
        mock_escalate = AsyncMock(return_value=_escalate_ok())
        with (
            patch.object(machine._classify, "run", new=AsyncMock(return_value=_classify_out(intent="escalate"))),
            patch.object(machine._route, "run", new=AsyncMock(return_value=RoutingDecision.SKIP_TO_ESCALATE)),
            patch.object(machine._act, "run", new=mock_act),
            patch.object(machine._escalate, "run", new=mock_escalate),
            patch.object(machine._respond, "run", new=AsyncMock(return_value=_respond_out())),
        ):
            result = await machine.process_turn("I want a human.", session)

        mock_act.assert_not_called()
        mock_escalate.assert_called_once()
        assert isinstance(result, RespondOutput)

    @pytest.mark.asyncio
    async def test_post_act_escalation_path(
        self, machine: StateMachine, session: SessionState
    ) -> None:
        """Act unresolved: EscalateState runs after ActState."""
        mock_act = AsyncMock(return_value=_act_unresolved())
        mock_escalate = AsyncMock(return_value=_escalate_ok())
        with (
            patch.object(machine._classify, "run", new=AsyncMock(return_value=_classify_out())),
            patch.object(machine._route, "run", new=AsyncMock(return_value=RoutingDecision.BILLING_PATH)),
            patch.object(machine._act, "run", new=mock_act),
            patch.object(machine._escalate, "run", new=mock_escalate),
            patch.object(machine._respond, "run", new=AsyncMock(return_value=_respond_out())),
        ):
            result = await machine.process_turn("My bill is wrong.", session)

        mock_act.assert_called_once()
        mock_escalate.assert_called_once()
        assert isinstance(result, RespondOutput)

    @pytest.mark.asyncio
    async def test_refuse_off_topic_act_and_escalate_skipped(
        self, machine: StateMachine, session: SessionState
    ) -> None:
        """REFUSE_OFF_TOPIC: Act and Escalate both skipped."""
        mock_act = AsyncMock(return_value=_act_resolved())
        mock_escalate = AsyncMock(return_value=_escalate_ok())
        with (
            patch.object(machine._classify, "run", new=AsyncMock(return_value=_classify_out(off_topic=True))),
            patch.object(machine._route, "run", new=AsyncMock(return_value=RoutingDecision.REFUSE_OFF_TOPIC)),
            patch.object(machine._act, "run", new=mock_act),
            patch.object(machine._escalate, "run", new=mock_escalate),
            patch.object(machine._respond, "run", new=AsyncMock(return_value=_respond_out())),
        ):
            result = await machine.process_turn("What is the weather?", session)

        mock_act.assert_not_called()
        mock_escalate.assert_not_called()
        assert isinstance(result, RespondOutput)


# ---------------------------------------------------------------------------
# TestStateMachineExceptionHandling
# ---------------------------------------------------------------------------


class TestStateMachineExceptionHandling:
    """Tests for exception paths in ClassifyState and ActState."""

    @pytest.mark.asyncio
    async def test_classify_exception_returns_fallback(
        self, machine: StateMachine, session: SessionState
    ) -> None:
        """ClassifyState exception returns fallback RespondOutput; no further states run."""
        mock_route = AsyncMock(return_value=RoutingDecision.BILLING_PATH)
        with (
            patch.object(machine._classify, "run", new=AsyncMock(side_effect=RuntimeError("timeout"))),
            patch.object(machine._route, "run", new=mock_route),
            patch.object(machine._respond, "run", new=AsyncMock(return_value=_respond_out())),
        ):
            result = await machine.process_turn("What is my bill?", session)

        assert isinstance(result, RespondOutput)
        assert result.metadata.get("escalation_offered") is True
        mock_route.assert_not_called()

    @pytest.mark.asyncio
    async def test_act_exception_proceeds_to_escalate(
        self, machine: StateMachine, session: SessionState
    ) -> None:
        """ActState exception does not abort the turn; EscalateState still runs."""
        mock_escalate = AsyncMock(return_value=_escalate_ok())
        with (
            patch.object(machine._classify, "run", new=AsyncMock(return_value=_classify_out())),
            patch.object(machine._route, "run", new=AsyncMock(return_value=RoutingDecision.BILLING_PATH)),
            patch.object(machine._act, "run", new=AsyncMock(side_effect=RuntimeError("SDK error"))),
            patch.object(machine._escalate, "run", new=mock_escalate),
            patch.object(machine._respond, "run", new=AsyncMock(return_value=_respond_out())),
        ):
            result = await machine.process_turn("What is my bill?", session)

        mock_escalate.assert_called_once()
        assert isinstance(result, RespondOutput)


# ---------------------------------------------------------------------------
# TestStateMachineSessionMutation
# ---------------------------------------------------------------------------


class TestStateMachineSessionMutation:
    """Tests for post-respond session state updates."""

    @pytest.mark.asyncio
    async def test_rolling_window_enforced_at_10_turns(
        self, machine: StateMachine, session: SessionState
    ) -> None:
        """9 pre-existing turns + 2 new = 11; sliced to 10."""
        session.conversation_history = [
            ConversationTurn(role="customer", content=f"msg {i}", timestamp="2026-06-24T10:00:00Z")
            for i in range(9)
        ]
        with (
            patch.object(machine._classify, "run", new=AsyncMock(return_value=_classify_out())),
            patch.object(machine._route, "run", new=AsyncMock(return_value=RoutingDecision.BILLING_PATH)),
            patch.object(machine._act, "run", new=AsyncMock(return_value=_act_resolved())),
            patch.object(machine._escalate, "run", new=AsyncMock(return_value=_escalate_ok())),
            patch.object(machine._respond, "run", new=AsyncMock(return_value=_respond_out())),
        ):
            await machine.process_turn("What is my bill?", session)

        assert len(session.conversation_history) == 10

    @pytest.mark.asyncio
    async def test_rolling_window_does_not_exceed_10(
        self, machine: StateMachine, session: SessionState
    ) -> None:
        """10 pre-existing turns + 2 new = 12; sliced to 10."""
        session.conversation_history = [
            ConversationTurn(role="customer", content=f"msg {i}", timestamp="2026-06-24T10:00:00Z")
            for i in range(10)
        ]
        with (
            patch.object(machine._classify, "run", new=AsyncMock(return_value=_classify_out())),
            patch.object(machine._route, "run", new=AsyncMock(return_value=RoutingDecision.BILLING_PATH)),
            patch.object(machine._act, "run", new=AsyncMock(return_value=_act_resolved())),
            patch.object(machine._escalate, "run", new=AsyncMock(return_value=_escalate_ok())),
            patch.object(machine._respond, "run", new=AsyncMock(return_value=_respond_out())),
        ):
            await machine.process_turn("What is my bill?", session)

        assert len(session.conversation_history) == 10

    @pytest.mark.asyncio
    async def test_correlation_id_refreshed_after_turn(
        self, machine: StateMachine, session: SessionState
    ) -> None:
        """correlation_id is replaced with a new UUID after each turn."""
        original_id = session.correlation_id
        with (
            patch.object(machine._classify, "run", new=AsyncMock(return_value=_classify_out())),
            patch.object(machine._route, "run", new=AsyncMock(return_value=RoutingDecision.BILLING_PATH)),
            patch.object(machine._act, "run", new=AsyncMock(return_value=_act_resolved())),
            patch.object(machine._escalate, "run", new=AsyncMock(return_value=_escalate_ok())),
            patch.object(machine._respond, "run", new=AsyncMock(return_value=_respond_out())),
        ):
            await machine.process_turn("What is my bill?", session)

        assert session.correlation_id != original_id

    @pytest.mark.asyncio
    async def test_both_turns_appended_to_history(
        self, machine: StateMachine, session: SessionState
    ) -> None:
        """Customer and agent turns are both appended with correct roles."""
        with (
            patch.object(machine._classify, "run", new=AsyncMock(return_value=_classify_out())),
            patch.object(machine._route, "run", new=AsyncMock(return_value=RoutingDecision.BILLING_PATH)),
            patch.object(machine._act, "run", new=AsyncMock(return_value=_act_resolved())),
            patch.object(machine._escalate, "run", new=AsyncMock(return_value=_escalate_ok())),
            patch.object(machine._respond, "run", new=AsyncMock(return_value=_respond_out("Agent reply."))),
        ):
            await machine.process_turn("Customer question.", session)

        assert session.conversation_history[-2].role == "customer"
        assert session.conversation_history[-2].content == "Customer question."
        assert session.conversation_history[-1].role == "agent"
        assert session.conversation_history[-1].content == "Agent reply."

    @pytest.mark.asyncio
    async def test_detected_emotion_written_to_session_after_classify(
        self, machine: StateMachine, session: SessionState
    ) -> None:
        """detected_emotion on session reflects ClassifyOutput after classify runs."""
        with (
            patch.object(
                machine._classify,
                "run",
                new=AsyncMock(return_value=_classify_out(detected_emotion="frustrated")),
            ),
            patch.object(machine._route, "run", new=AsyncMock(return_value=RoutingDecision.BILLING_PATH)),
            patch.object(machine._act, "run", new=AsyncMock(return_value=_act_resolved())),
            patch.object(machine._escalate, "run", new=AsyncMock(return_value=_escalate_ok())),
            patch.object(machine._respond, "run", new=AsyncMock(return_value=_respond_out())),
        ):
            await machine.process_turn("I am angry about my bill.", session)

        assert session.detected_emotion == "frustrated"


# ---------------------------------------------------------------------------
# TestStateMachineReturnType
# ---------------------------------------------------------------------------


class TestStateMachineReturnType:
    """Tests for return type and context isolation."""

    @pytest.mark.asyncio
    async def test_process_turn_returns_respond_output(
        self, machine: StateMachine, session: SessionState
    ) -> None:
        """process_turn always returns a RespondOutput instance."""
        with (
            patch.object(machine._classify, "run", new=AsyncMock(return_value=_classify_out())),
            patch.object(machine._route, "run", new=AsyncMock(return_value=RoutingDecision.BILLING_PATH)),
            patch.object(machine._act, "run", new=AsyncMock(return_value=_act_resolved())),
            patch.object(machine._escalate, "run", new=AsyncMock(return_value=_escalate_ok())),
            patch.object(machine._respond, "run", new=AsyncMock(return_value=_respond_out())),
        ):
            result = await machine.process_turn("What is my bill?", session)

        assert isinstance(result, RespondOutput)

    @pytest.mark.asyncio
    async def test_process_turn_does_not_leak_context(
        self, machine: StateMachine, session: SessionState
    ) -> None:
        """RespondOutput does not carry StateContext internals."""
        with (
            patch.object(machine._classify, "run", new=AsyncMock(return_value=_classify_out())),
            patch.object(machine._route, "run", new=AsyncMock(return_value=RoutingDecision.BILLING_PATH)),
            patch.object(machine._act, "run", new=AsyncMock(return_value=_act_resolved())),
            patch.object(machine._escalate, "run", new=AsyncMock(return_value=_escalate_ok())),
            patch.object(machine._respond, "run", new=AsyncMock(return_value=_respond_out())),
        ):
            result = await machine.process_turn("What is my bill?", session)

        assert not hasattr(result, "classify_output")
        assert not hasattr(result, "routing_decision")


# ---------------------------------------------------------------------------
# TestStateMachineAccountIdExtraction
# ---------------------------------------------------------------------------


class TestStateMachineAccountIdExtraction:
    """Tests for account ID extraction from customer messages."""

    @pytest.mark.asyncio
    async def test_account_id_extracted_from_message(
        self, machine: StateMachine
    ) -> None:
        """ACC-XXXXX in message is stored in session.account_id when it is None."""
        session = SessionState(
            session_id="SESS-EXT-001",
            correlation_id="corr-ext-001",
            account_id=None,
            conversation_history=[],
            started_at="2026-06-24T10:00:00Z",
            last_updated="2026-06-24T10:00:00Z",
        )
        with (
            patch.object(machine._classify, "run", new=AsyncMock(return_value=_classify_out())),
            patch.object(machine._route, "run", new=AsyncMock(return_value=RoutingDecision.BILLING_PATH)),
            patch.object(machine._act, "run", new=AsyncMock(return_value=_act_resolved())),
            patch.object(machine._escalate, "run", new=AsyncMock(return_value=_escalate_ok())),
            patch.object(machine._respond, "run", new=AsyncMock(return_value=_respond_out())),
        ):
            await machine.process_turn("My account is ACC-10001 and I have a billing question.", session)

        assert session.account_id == "ACC-10001"

    @pytest.mark.asyncio
    async def test_account_id_not_overwritten(
        self, machine: StateMachine
    ) -> None:
        """Existing session.account_id is not replaced when message contains a different ID."""
        session = SessionState(
            session_id="SESS-EXT-002",
            correlation_id="corr-ext-002",
            account_id="ACC-10001",
            conversation_history=[],
            started_at="2026-06-24T10:00:00Z",
            last_updated="2026-06-24T10:00:00Z",
        )
        with (
            patch.object(machine._classify, "run", new=AsyncMock(return_value=_classify_out())),
            patch.object(machine._route, "run", new=AsyncMock(return_value=RoutingDecision.BILLING_PATH)),
            patch.object(machine._act, "run", new=AsyncMock(return_value=_act_resolved())),
            patch.object(machine._escalate, "run", new=AsyncMock(return_value=_escalate_ok())),
            patch.object(machine._respond, "run", new=AsyncMock(return_value=_respond_out())),
        ):
            await machine.process_turn("Can you check billing for ACC-10002?", session)

        assert session.account_id == "ACC-10001"

    @pytest.mark.asyncio
    async def test_account_id_extracted_when_agent_solicited_it(
        self, machine: StateMachine
    ) -> None:
        """Bare ACC-XXXXX reply is stored when the last agent turn asked for an account ID."""
        session = SessionState(
            session_id="SESS-EXT-003",
            correlation_id="corr-ext-003",
            account_id=None,
            conversation_history=[
                ConversationTurn(
                    role="agent",
                    content="Could you please provide your account ID so I can look that up?",
                    timestamp="2026-06-24T10:00:00Z",
                )
            ],
            started_at="2026-06-24T10:00:00Z",
            last_updated="2026-06-24T10:00:00Z",
        )
        with (
            patch.object(machine._classify, "run", new=AsyncMock(return_value=_classify_out())),
            patch.object(machine._route, "run", new=AsyncMock(return_value=RoutingDecision.BILLING_PATH)),
            patch.object(machine._act, "run", new=AsyncMock(return_value=_act_resolved())),
            patch.object(machine._escalate, "run", new=AsyncMock(return_value=_escalate_ok())),
            patch.object(machine._respond, "run", new=AsyncMock(return_value=_respond_out())),
        ):
            await machine.process_turn("ACC-10005", session)

        assert session.account_id == "ACC-10005"

    @pytest.mark.asyncio
    async def test_account_id_overwritten_when_explicit_ownership(
        self, machine: StateMachine
    ) -> None:
        """Existing account_id is overwritten when message contains explicit ownership phrase."""
        session = SessionState(
            session_id="SESS-EXT-004",
            correlation_id="corr-ext-004",
            account_id="ACC-10001",
            conversation_history=[],
            started_at="2026-06-24T10:00:00Z",
            last_updated="2026-06-24T10:00:00Z",
        )
        with (
            patch.object(machine._classify, "run", new=AsyncMock(return_value=_classify_out())),
            patch.object(machine._route, "run", new=AsyncMock(return_value=RoutingDecision.BILLING_PATH)),
            patch.object(machine._act, "run", new=AsyncMock(return_value=_act_resolved())),
            patch.object(machine._escalate, "run", new=AsyncMock(return_value=_escalate_ok())),
            patch.object(machine._respond, "run", new=AsyncMock(return_value=_respond_out())),
        ):
            await machine.process_turn("my account is ACC-10002, show me my bill", session)

        assert session.account_id == "ACC-10002"

    @pytest.mark.asyncio
    async def test_account_id_not_overwritten_without_explicit_ownership(
        self, machine: StateMachine
    ) -> None:
        """Existing account_id is not replaced when message lacks an explicit ownership phrase."""
        session = SessionState(
            session_id="SESS-EXT-005",
            correlation_id="corr-ext-005",
            account_id="ACC-10001",
            conversation_history=[],
            started_at="2026-06-24T10:00:00Z",
            last_updated="2026-06-24T10:00:00Z",
        )
        with (
            patch.object(machine._classify, "run", new=AsyncMock(return_value=_classify_out())),
            patch.object(machine._route, "run", new=AsyncMock(return_value=RoutingDecision.BILLING_PATH)),
            patch.object(machine._act, "run", new=AsyncMock(return_value=_act_resolved())),
            patch.object(machine._escalate, "run", new=AsyncMock(return_value=_escalate_ok())),
            patch.object(machine._respond, "run", new=AsyncMock(return_value=_respond_out())),
        ):
            await machine.process_turn("What is my bill ACC-10002", session)

        assert session.account_id == "ACC-10001"

    @pytest.mark.asyncio
    async def test_account_id_overwritten_with_account_prefix(
        self, machine: StateMachine
    ) -> None:
        """Existing account_id is overwritten when message has 'Account ACC-XXXXX' pattern."""
        session = SessionState(
            session_id="SESS-EXT-006",
            correlation_id="corr-ext-006",
            account_id="ACC-10001",
            conversation_history=[],
            started_at="2026-06-24T10:00:00Z",
            last_updated="2026-06-24T10:00:00Z",
        )
        with (
            patch.object(machine._classify, "run", new=AsyncMock(return_value=_classify_out())),
            patch.object(machine._route, "run", new=AsyncMock(return_value=RoutingDecision.BILLING_PATH)),
            patch.object(machine._act, "run", new=AsyncMock(return_value=_act_resolved())),
            patch.object(machine._escalate, "run", new=AsyncMock(return_value=_escalate_ok())),
            patch.object(machine._respond, "run", new=AsyncMock(return_value=_respond_out())),
        ):
            await machine.process_turn("What plan am I on? Account ACC-10002.", session)

        assert session.account_id == "ACC-10002"
