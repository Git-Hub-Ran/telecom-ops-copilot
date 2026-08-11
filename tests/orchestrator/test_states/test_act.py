"""Unit tests for ActState tool dispatch, error handling, and retry logic."""

import copy
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.config import get_config
from src.orchestrator.agents.factory import AgentFactory
from src.orchestrator.models import (
    ClassifyOutput,
    RoutingDecision,
    SessionState,
    StateContext,
)
from src.orchestrator.states.act import ActState, _format_billing_outputs
from src.tools.billing import Bill, BillingInfo, GetBillingInfoResult
from src.tools.customer import GetCustomerAccountResult
from src.tools.diagnostic import RunSpeedDiagnosticResult
from src.tools.outage import CheckNetworkOutageResult


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
    factory = MagicMock(spec=AgentFactory)
    factory.get_act_agent.return_value = MagicMock(id="agent-act-001")
    return factory


@pytest.fixture
def state(mock_factory: MagicMock) -> ActState:
    return ActState(mock_factory)


@pytest.fixture
def session() -> SessionState:
    return SessionState(
        session_id="SESS-001",
        correlation_id="corr-001",
        account_id="ACC-001",
        conversation_history=[],
        started_at="2026-06-23T10:00:00Z",
        last_updated="2026-06-23T10:00:00Z",
    )


def _make_context(session: SessionState, decision: RoutingDecision) -> StateContext:
    return StateContext(
        session_state=session,
        customer_message="test message",
        classify_output=ClassifyOutput(intent="billing", confidence=0.9),
        routing_decision=decision,
    )


# ---------------------------------------------------------------------------
# Result helpers
# ---------------------------------------------------------------------------


def _billing_ok() -> GetBillingInfoResult:
    """Return a real GetBillingInfoResult for a successful billing lookup."""
    bill = Bill(
        bill_id="BILL-00001-202604",
        account_id="ACC-001",
        billing_period_start="2026-04-01",
        billing_period_end="2026-04-30",
        issue_date="2026-04-01",
        due_date="2026-05-15",
        subtotal=25.00,
        discounts=-5.00,
        taxes=2.00,
        total=22.00,
        status="paid",
        paid_date="2026-05-10",
        line_items=[],
    )
    return GetBillingInfoResult(
        success=True,
        billing_info=BillingInfo(account_id="ACC-001", bills=[bill], total_bills=1),
    )


def _account_ok(billing_zip: str = "90210") -> MagicMock:
    """Return a mock GetCustomerAccountResult for a successful account lookup."""
    account = MagicMock()
    account.billing_zip = billing_zip
    mock = MagicMock()
    mock.success = True
    mock.error_code = None
    mock.error_message = None
    mock.account = account
    return mock


def _outage_ok() -> MagicMock:
    """Return a mock CheckNetworkOutageResult for a successful outage check."""
    mock = MagicMock()
    mock.success = True
    mock.error_code = None
    mock.error_message = None
    return mock


def _diagnostic_ok() -> MagicMock:
    """Return a mock RunSpeedDiagnosticResult for a successful speed diagnostic."""
    mock = MagicMock()
    mock.success = True
    mock.error_code = None
    mock.error_message = None
    return mock


def _error_billing(error_code: str) -> GetBillingInfoResult:
    return GetBillingInfoResult(
        success=False,
        billing_info=None,
        error_code=error_code,
        error_message=f"error: {error_code}",
    )


def _error_account(error_code: str) -> GetCustomerAccountResult:
    return GetCustomerAccountResult(
        success=False,
        account=None,
        error_code=error_code,
        error_message=f"error: {error_code}",
    )


def _error_outage(error_code: str) -> CheckNetworkOutageResult:
    return CheckNetworkOutageResult(
        success=False,
        outage_check=None,
        error_code=error_code,
        error_message=f"error: {error_code}",
    )


def _error_diagnostic(error_code: str) -> RunSpeedDiagnosticResult:
    return RunSpeedDiagnosticResult(
        success=False,
        diagnostic=None,
        error_code=error_code,
        error_message=f"error: {error_code}",
    )


_INFO_JSON = json.dumps({
    "kb_citations": [
        {"doc_id": "kb/policies/01-billing-cycle.md", "section": "Late Fees", "relevance": "directly relevant"},
        {"doc_id": "kb/policies/02-late-fees.md", "section": "Payment Methods", "relevance": "related"},
    ]
})


# ---------------------------------------------------------------------------
# TestActStateHappyPaths
# ---------------------------------------------------------------------------


class TestActStateHappyPaths:
    """Happy-path tests: one per routing decision."""

    @pytest.mark.asyncio
    @patch("src.orchestrator.states.act.get_billing_info")
    async def test_billing_path_resolved(
        self, mock_billing: MagicMock, state: ActState, session: SessionState
    ) -> None:
        """BILLING_PATH with successful tool call returns resolved ActOutput."""
        mock_billing.return_value = _billing_ok()
        context = _make_context(session, RoutingDecision.BILLING_PATH)

        result = await state.run(context)

        mock_billing.assert_called_once_with(account_id="ACC-001", months=3)
        assert result.resolution_status == "resolved"
        assert len(result.tools_called) == 1
        assert result.tools_called[0].tool_name == "get_billing_info"
        assert result.tools_called[0].success is True
        assert result.kb_citations == []

    @pytest.mark.asyncio
    @patch("src.orchestrator.states.act.get_customer_account")
    async def test_account_path_resolved(
        self, mock_account: MagicMock, state: ActState, session: SessionState
    ) -> None:
        """ACCOUNT_PATH with successful tool call returns resolved ActOutput."""
        mock_account.return_value = _account_ok()
        context = _make_context(session, RoutingDecision.ACCOUNT_PATH)

        result = await state.run(context)

        mock_account.assert_called_once_with(account_id="ACC-001")
        assert result.resolution_status == "resolved"
        assert result.tools_called[0].tool_name == "get_customer_account"
        assert result.tools_called[0].success is True

    @pytest.mark.asyncio
    @patch("src.orchestrator.states.act.run_speed_diagnostic")
    @patch("src.orchestrator.states.act.check_network_outage")
    @patch("src.orchestrator.states.act.get_customer_account")
    async def test_technical_path_all_tools_resolved(
        self,
        mock_account: MagicMock,
        mock_outage: MagicMock,
        mock_diag: MagicMock,
        state: ActState,
        session: SessionState,
    ) -> None:
        """TECHNICAL_PATH with all three tools succeeding returns resolved ActOutput."""
        mock_account.return_value = _account_ok(billing_zip="90210")
        mock_outage.return_value = _outage_ok()
        mock_diag.return_value = _diagnostic_ok()
        context = _make_context(session, RoutingDecision.TECHNICAL_PATH)

        result = await state.run(context)

        assert result.resolution_status == "resolved"
        assert len(result.tools_called) == 3
        assert [r.tool_name for r in result.tools_called] == [
            "get_customer_account",
            "check_network_outage",
            "run_speed_diagnostic",
        ]
        mock_outage.assert_called_once_with(zip_code="90210")
        mock_diag.assert_called_once_with(account_id="ACC-001")

    @pytest.mark.asyncio
    async def test_info_path_returns_kb_citations(
        self, state: ActState, session: SessionState
    ) -> None:
        """INFO_PATH via act agent returns resolved ActOutput with kb_citations."""
        context = _make_context(session, RoutingDecision.INFO_PATH)

        with patch.object(state, "_invoke_agent_for_kb", return_value=_INFO_JSON):
            result = await state.run(context)

        assert result.resolution_status == "resolved"
        assert len(result.kb_citations) == 2
        assert result.kb_citations[0].doc_id == "kb/policies/01-billing-cycle.md"
        assert result.kb_citations[0].section == "Late Fees"
        assert result.tools_called == []


# ---------------------------------------------------------------------------
# TestActStateToolErrorModes
# ---------------------------------------------------------------------------


class TestActStateToolErrorModes:
    """Both tool error modes from Q2: result.success==False and exception."""

    @pytest.mark.asyncio
    @patch("src.orchestrator.states.act.get_billing_info")
    async def test_mode_a_invalid_format_returns_partial(
        self, mock_billing: MagicMock, state: ActState, session: SessionState
    ) -> None:
        """Mode A: tool returns invalid_format -> partial, no retry."""
        mock_billing.return_value = _error_billing("invalid_format")
        context = _make_context(session, RoutingDecision.BILLING_PATH)

        result = await state.run(context)

        assert result.resolution_status == "partial"
        assert result.tools_called[0].success is False
        assert result.tools_called[0].error_code == "invalid_format"
        mock_billing.assert_called_once()  # no retry

    @pytest.mark.asyncio
    @patch("src.orchestrator.states.act.get_billing_info")
    async def test_mode_a_not_found_returns_partial(
        self, mock_billing: MagicMock, state: ActState, session: SessionState
    ) -> None:
        """Mode A: tool returns not_found -> partial, no retry."""
        mock_billing.return_value = _error_billing("not_found")
        context = _make_context(session, RoutingDecision.BILLING_PATH)

        result = await state.run(context)

        assert result.resolution_status == "partial"
        mock_billing.assert_called_once()  # no retry

    @pytest.mark.asyncio
    @patch("src.orchestrator.states.act.get_billing_info")
    async def test_mode_a_data_unavailable_retries_then_unresolved(
        self, mock_billing: MagicMock, state: ActState, session: SessionState
    ) -> None:
        """Mode A: data_unavailable on both attempts -> unresolved after one retry."""
        mock_billing.return_value = _error_billing("data_unavailable")
        context = _make_context(session, RoutingDecision.BILLING_PATH)

        result = await state.run(context)

        assert result.resolution_status == "unresolved"
        assert mock_billing.call_count == 2  # original + one retry

    @pytest.mark.asyncio
    @patch("src.orchestrator.states.act.get_billing_info")
    async def test_mode_b_exception_retries_then_unresolved(
        self, mock_billing: MagicMock, state: ActState, session: SessionState
    ) -> None:
        """Mode B: exception on both attempts -> unresolved after one retry."""
        mock_billing.side_effect = Exception("network timeout")
        context = _make_context(session, RoutingDecision.BILLING_PATH)

        result = await state.run(context)

        assert result.resolution_status == "unresolved"
        assert mock_billing.call_count == 2  # original + one retry
        assert result.tools_called[0].error_code == "exception"

    @pytest.mark.asyncio
    @patch("src.orchestrator.states.act.get_billing_info")
    async def test_mode_a_data_unavailable_retry_succeeds(
        self, mock_billing: MagicMock, state: ActState, session: SessionState
    ) -> None:
        """Mode A: data_unavailable on first attempt, retry succeeds -> resolved."""
        mock_billing.side_effect = [_error_billing("data_unavailable"), _billing_ok()]
        context = _make_context(session, RoutingDecision.BILLING_PATH)

        result = await state.run(context)

        assert result.resolution_status == "resolved"
        assert mock_billing.call_count == 2
        assert result.tools_called[0].success is True


# ---------------------------------------------------------------------------
# TestActStateTechnicalPath
# ---------------------------------------------------------------------------


class TestActStateTechnicalPath:
    """TECHNICAL_PATH sequencing and partial-failure record-keeping."""

    @pytest.mark.asyncio
    @patch("src.orchestrator.states.act.run_speed_diagnostic")
    @patch("src.orchestrator.states.act.check_network_outage")
    @patch("src.orchestrator.states.act.get_customer_account")
    async def test_step1_fails_steps2_and_3_not_attempted(
        self,
        mock_account: MagicMock,
        mock_outage: MagicMock,
        mock_diag: MagicMock,
        state: ActState,
        session: SessionState,
    ) -> None:
        """Step 1 failure aborts steps 2 and 3; only one record is produced."""
        mock_account.return_value = _error_account("not_found")
        context = _make_context(session, RoutingDecision.TECHNICAL_PATH)

        result = await state.run(context)

        assert len(result.tools_called) == 1
        assert result.tools_called[0].tool_name == "get_customer_account"
        assert result.tools_called[0].success is False
        mock_outage.assert_not_called()
        mock_diag.assert_not_called()

    @pytest.mark.asyncio
    @patch("src.orchestrator.states.act.run_speed_diagnostic")
    @patch("src.orchestrator.states.act.check_network_outage")
    @patch("src.orchestrator.states.act.get_customer_account")
    async def test_step2_fails_step3_still_runs(
        self,
        mock_account: MagicMock,
        mock_outage: MagicMock,
        mock_diag: MagicMock,
        state: ActState,
        session: SessionState,
    ) -> None:
        """Step 2 failure does not prevent step 3 from running."""
        mock_account.return_value = _account_ok()
        mock_outage.return_value = _error_outage("data_unavailable")
        mock_diag.return_value = _diagnostic_ok()
        context = _make_context(session, RoutingDecision.TECHNICAL_PATH)

        result = await state.run(context)

        assert len(result.tools_called) == 3
        assert result.tools_called[2].tool_name == "run_speed_diagnostic"
        assert result.tools_called[2].success is True
        mock_diag.assert_called_once()

    @pytest.mark.asyncio
    @patch("src.orchestrator.states.act.run_speed_diagnostic")
    @patch("src.orchestrator.states.act.check_network_outage")
    @patch("src.orchestrator.states.act.get_customer_account")
    async def test_all_records_appended_worst_outcome_wins(
        self,
        mock_account: MagicMock,
        mock_outage: MagicMock,
        mock_diag: MagicMock,
        state: ActState,
        session: SessionState,
    ) -> None:
        """All three ToolCallRecords present; worst status (unresolved) propagates."""
        mock_account.return_value = _account_ok()
        # step 2 fails transiently (both retries): unresolved
        mock_outage.return_value = _error_outage("data_unavailable")
        mock_diag.return_value = _diagnostic_ok()
        context = _make_context(session, RoutingDecision.TECHNICAL_PATH)

        result = await state.run(context)

        tool_names = [r.tool_name for r in result.tools_called]
        assert "get_customer_account" in tool_names
        assert "check_network_outage" in tool_names
        assert "run_speed_diagnostic" in tool_names
        assert result.resolution_status == "unresolved"


# ---------------------------------------------------------------------------
# TestActStateBypassDecisions
# ---------------------------------------------------------------------------


class TestActStateBypassDecisions:
    """Bypass routing decisions must raise ValueError immediately."""

    @pytest.mark.asyncio
    async def test_skip_to_escalate_raises_value_error(
        self, state: ActState, session: SessionState
    ) -> None:
        context = _make_context(session, RoutingDecision.SKIP_TO_ESCALATE)
        with pytest.raises(ValueError, match="bypass decision"):
            await state.run(context)

    @pytest.mark.asyncio
    async def test_ask_clarifying_question_raises_value_error(
        self, state: ActState, session: SessionState
    ) -> None:
        context = _make_context(session, RoutingDecision.ASK_CLARIFYING_QUESTION)
        with pytest.raises(ValueError, match="bypass decision"):
            await state.run(context)

    @pytest.mark.asyncio
    async def test_refuse_off_topic_raises_value_error(
        self, state: ActState, session: SessionState
    ) -> None:
        context = _make_context(session, RoutingDecision.REFUSE_OFF_TOPIC)
        with pytest.raises(ValueError, match="bypass decision"):
            await state.run(context)


# ---------------------------------------------------------------------------
# TestActStateContextHandling
# ---------------------------------------------------------------------------


class TestActStateContextHandling:
    """Mutation contract, missing account_id, and None routing_decision."""

    @pytest.mark.asyncio
    @patch("src.orchestrator.states.act.get_billing_info")
    async def test_does_not_mutate_context(
        self, mock_billing: MagicMock, state: ActState, session: SessionState
    ) -> None:
        """ActState must not mutate the input context."""
        mock_billing.return_value = _billing_ok()
        context = _make_context(session, RoutingDecision.BILLING_PATH)
        context_before = copy.deepcopy(context)

        await state.run(context)

        assert context.model_dump() == context_before.model_dump()

    @pytest.mark.asyncio
    async def test_missing_account_id_returns_partial(
        self, state: ActState
    ) -> None:
        """account_id=None produces partial ActOutput with explanatory error_details."""
        session_no_account = SessionState(
            session_id="SESS-002",
            correlation_id="corr-002",
            account_id=None,
            conversation_history=[],
            started_at="2026-06-23T10:00:00Z",
            last_updated="2026-06-23T10:00:00Z",
        )
        context = _make_context(session_no_account, RoutingDecision.BILLING_PATH)

        result = await state.run(context)

        assert result.resolution_status == "partial"
        assert result.error_details is not None
        assert "account_id" in result.error_details

    @pytest.mark.asyncio
    async def test_routing_decision_none_raises_value_error(
        self, state: ActState, session: SessionState
    ) -> None:
        """routing_decision=None raises ValueError before any tool is called."""
        context = StateContext(
            session_state=session,
            customer_message="test",
        )
        with pytest.raises(ValueError, match="routing_decision"):
            await state.run(context)

    @pytest.mark.asyncio
    async def test_info_path_agent_error_returns_unresolved(
        self, state: ActState, session: SessionState
    ) -> None:
        """INFO_PATH agent failure returns unresolved ActOutput with error_details."""
        context = _make_context(session, RoutingDecision.INFO_PATH)

        with patch.object(
            state, "_invoke_agent_for_kb", side_effect=RuntimeError("agent unavailable")
        ):
            result = await state.run(context)

        assert result.resolution_status == "unresolved"
        assert result.error_details == "agent unavailable"
        assert result.kb_citations == []

    @pytest.mark.asyncio
    async def test_info_path_malformed_json_returns_unresolved(
        self, state: ActState, session: SessionState
    ) -> None:
        """INFO_PATH with malformed JSON response returns unresolved ActOutput."""
        context = _make_context(session, RoutingDecision.INFO_PATH)

        with patch.object(state, "_invoke_agent_for_kb", return_value="not valid json {{{"):
            result = await state.run(context)

        assert result.resolution_status == "unresolved"
        assert result.kb_citations == []


# ---------------------------------------------------------------------------
# TestBillingPreparedResponse
# ---------------------------------------------------------------------------


class TestFormatBillingOutputs:
    """Tests for the _format_billing_outputs helper."""

    def test_happy_path_returns_both_outputs(self) -> None:
        """Happy path: both summary and prepared strings contain formatted values."""
        result = _billing_ok()
        summary, prepared = _format_billing_outputs(result)
        assert summary is not None
        assert prepared is not None
        for s in (summary, prepared):
            assert "$22.00" in s
            assert "$25.00" in s
            assert "-$5.00" in s
            assert "$2.00" in s
            assert "2026-04-01" in s
            assert "2026-04-30" in s

    def test_returns_none_tuple_when_success_false(self) -> None:
        """Returns (None, None) when the billing result indicates failure."""
        result = _error_billing("not_found")
        assert _format_billing_outputs(result) == (None, None)
