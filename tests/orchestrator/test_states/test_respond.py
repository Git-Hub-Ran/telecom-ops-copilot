"""Unit tests for RespondState customer-facing message generation."""

import copy
import json
from unittest.mock import MagicMock, patch

import pytest

from src.config import get_config
from src.orchestrator.agents.factory import AgentFactory
from src.orchestrator.models import (
    ActOutput,
    ClassifyOutput,
    KBCitation,
    RespondOutput,
    RoutingDecision,
    SessionState,
    StateContext,
    ToolCallRecord,
)
from src.orchestrator.states.respond import (
    RespondState,
    _CLARIFY_MESSAGE,
    _FALLBACK_MESSAGE,
    _REFUSE_MESSAGE,
)
from src.tools.escalation import CreateEscalationTicketResult, EscalationPayload


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
    """AgentFactory mock with a pre-configured respond agent."""
    factory = MagicMock(spec=AgentFactory)
    factory.get_respond_agent.return_value = MagicMock(id="agent-respond-001")
    return factory


@pytest.fixture
def state(mock_factory: MagicMock) -> RespondState:
    """RespondState under test with mocked factory."""
    return RespondState(mock_factory)


@pytest.fixture
def session() -> SessionState:
    """Minimal SessionState."""
    return SessionState(
        session_id="SESS-001",
        correlation_id="corr-001",
        account_id="ACC-001",
        conversation_history=[],
        started_at="2026-06-23T10:00:00Z",
        last_updated="2026-06-23T10:00:00Z",
    )


@pytest.fixture
def resolved_context(session: SessionState) -> StateContext:
    """Context for the Act-resolved path with one KB citation and one tool record."""
    act_out = ActOutput(
        resolution_status="resolved",
        tools_called=[
            ToolCallRecord(
                tool_name="get_billing_info",
                input={"account_id": "ACC-001", "months": 3},
                result_summary="Retrieved 3 months of billing history",
                called_at="2026-06-23T10:00:05Z",
                success=True,
                error_code=None,
            )
        ],
        kb_citations=[
            KBCitation(
                doc_id="kb/01.md",
                section="S1",
                relevance="Relevant to billing query",
            )
        ],
        error_details=None,
    )
    return StateContext(
        session_state=session,
        customer_message="What is my current bill?",
        routing_decision=RoutingDecision.BILLING_PATH,
        act_output=act_out,
        escalate_output=None,
    )


@pytest.fixture
def unresolved_escalated_context(session: SessionState) -> StateContext:
    """Context for the unresolved + escalated path."""
    act_out = ActOutput(
        resolution_status="unresolved",
        tools_called=[],
        kb_citations=[],
        error_details="data_unavailable",
    )
    return StateContext(
        session_state=session,
        customer_message="My bill is wrong.",
        routing_decision=RoutingDecision.BILLING_PATH,
        act_output=act_out,
        escalate_output=CreateEscalationTicketResult(success=True),
    )


@pytest.fixture
def direct_escalation_context(session: SessionState) -> StateContext:
    """Context for the direct escalation path (act was skipped)."""
    return StateContext(
        session_state=session,
        customer_message="I want to speak to a human.",
        routing_decision=RoutingDecision.SKIP_TO_ESCALATE,
        act_output=None,
        escalate_output=CreateEscalationTicketResult(success=True),
    )


@pytest.fixture
def refuse_context(session: SessionState) -> StateContext:
    """Context for the REFUSE_OFF_TOPIC path."""
    return StateContext(
        session_state=session,
        customer_message="What is the weather today?",
        routing_decision=RoutingDecision.REFUSE_OFF_TOPIC,
    )


@pytest.fixture
def clarify_context(session: SessionState) -> StateContext:
    """Context for the ASK_CLARIFYING_QUESTION path."""
    return StateContext(
        session_state=session,
        customer_message="I have a problem.",
        routing_decision=RoutingDecision.ASK_CLARIFYING_QUESTION,
    )


def _agent_json(
    message: str = "Here is your billing summary.",
    citations: list[str] | None = None,
    metadata: dict | None = None,
) -> str:
    """Build a valid RespondAgent JSON response string."""
    return json.dumps({
        "message": message,
        "citations": citations if citations is not None else [],
        "metadata": metadata if metadata is not None else {},
    })


# ---------------------------------------------------------------------------
# TestRespondStateIncomingBranches
# ---------------------------------------------------------------------------


class TestRespondStateIncomingBranches:
    """Tests for all four incoming state branches."""

    @pytest.mark.asyncio
    async def test_resolved_path_returns_message(
        self, state: RespondState, resolved_context: StateContext
    ) -> None:
        """Resolved path returns a non-empty message without escalation_offered."""
        with patch.object(state, "_invoke_agent", return_value=_agent_json()):
            result = await state.run(resolved_context)
        assert isinstance(result.message, str)
        assert len(result.message) > 0
        assert result.metadata.get("escalation_offered", False) == False

    @pytest.mark.asyncio
    async def test_unresolved_escalated_path_sets_escalation_offered(
        self, state: RespondState, unresolved_escalated_context: StateContext
    ) -> None:
        """Unresolved + escalated path sets escalation_offered=True in metadata."""
        with patch.object(state, "_invoke_agent", return_value=_agent_json()):
            result = await state.run(unresolved_escalated_context)
        assert result.metadata["escalation_offered"] is True

    @pytest.mark.asyncio
    async def test_direct_escalation_path_no_act_output(
        self, state: RespondState, direct_escalation_context: StateContext
    ) -> None:
        """Direct escalation path (act_output=None) sets escalation_offered=True and tools_called=0."""
        with patch.object(state, "_invoke_agent", return_value=_agent_json()):
            result = await state.run(direct_escalation_context)
        assert isinstance(result, RespondOutput)
        assert result.metadata["escalation_offered"] is True
        assert result.metadata["tools_called"] == 0

    @pytest.mark.asyncio
    async def test_refuse_off_topic_no_agent_call(
        self, state: RespondState, refuse_context: StateContext
    ) -> None:
        """REFUSE_OFF_TOPIC returns canned refusal message without invoking RespondAgent."""
        with patch.object(state, "_invoke_agent") as mock_agent:
            result = await state.run(refuse_context)
        mock_agent.assert_not_called()
        assert _REFUSE_MESSAGE in result.message


# ---------------------------------------------------------------------------
# TestRespondStateBypassDecisions
# ---------------------------------------------------------------------------


class TestRespondStateBypassDecisions:
    """Tests for Python-only canned responses."""

    @pytest.mark.asyncio
    async def test_ask_clarifying_question_no_agent_call(
        self, state: RespondState, clarify_context: StateContext
    ) -> None:
        """ASK_CLARIFYING_QUESTION returns canned clarification message without invoking RespondAgent."""
        with patch.object(state, "_invoke_agent") as mock_agent:
            result = await state.run(clarify_context)
        mock_agent.assert_not_called()
        assert _CLARIFY_MESSAGE in result.message


# ---------------------------------------------------------------------------
# TestRespondStateAgentFallback
# ---------------------------------------------------------------------------


class TestRespondStateAgentFallback:
    """Tests for FR-045 hardcoded fallback on agent failure."""

    @pytest.mark.asyncio
    async def test_agent_failure_returns_fr045_message(
        self, state: RespondState, resolved_context: StateContext
    ) -> None:
        """Agent failure returns the FR-045 hardcoded fallback message."""
        with patch.object(state, "_invoke_agent", side_effect=RuntimeError("timeout")):
            result = await state.run(resolved_context)
        assert result.message == _FALLBACK_MESSAGE
        assert result.metadata["escalation_offered"] is True

    @pytest.mark.asyncio
    async def test_agent_failure_still_returns_respond_output(
        self, state: RespondState, resolved_context: StateContext
    ) -> None:
        """Agent failure returns a RespondOutput instance, not a raised exception."""
        with patch.object(state, "_invoke_agent", side_effect=RuntimeError("timeout")):
            result = await state.run(resolved_context)
        assert isinstance(result, RespondOutput)


# ---------------------------------------------------------------------------
# TestRespondStateMetadata
# ---------------------------------------------------------------------------


class TestRespondStateMetadata:
    """Tests for metadata field population."""

    @pytest.mark.asyncio
    async def test_kb_docs_used_matches_citations_count(
        self, state: RespondState, resolved_context: StateContext
    ) -> None:
        """kb_docs_used in metadata equals the number of KB citations in act_output."""
        with patch.object(state, "_invoke_agent", return_value=_agent_json()):
            result = await state.run(resolved_context)
        assert result.metadata["kb_docs_used"] == 1

    @pytest.mark.asyncio
    async def test_tools_called_count_in_metadata(
        self, state: RespondState, resolved_context: StateContext
    ) -> None:
        """tools_called in metadata equals the number of ToolCallRecords in act_output."""
        with patch.object(state, "_invoke_agent", return_value=_agent_json()):
            result = await state.run(resolved_context)
        assert result.metadata["tools_called"] == 1

    @pytest.mark.asyncio
    async def test_no_escalation_offered_when_escalate_output_none(
        self, state: RespondState, resolved_context: StateContext
    ) -> None:
        """escalation_offered is False when escalate_output is None."""
        with patch.object(state, "_invoke_agent", return_value=_agent_json()):
            result = await state.run(resolved_context)
        assert result.metadata.get("escalation_offered", False) == False


# ---------------------------------------------------------------------------
# TestRespondStateMutationContract
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# TestRespondStateBuildAgentPrompt
# ---------------------------------------------------------------------------


class TestRespondStateBuildAgentPrompt:
    """Tests for _build_agent_prompt content."""

    def test_escalation_id_included_in_prompt_when_ticket_present(
        self, state: RespondState, session: SessionState
    ) -> None:
        """When escalate_output has success=True and a ticket, the prompt contains the escalation_id."""
        ticket = EscalationPayload(
            escalation_id="ESC-20260513-143023-9999",
            created_at="2026-05-13T14:30:23Z",
            reason_code="out_of_scope",
            priority="medium",
            customer={"account_id": "ACC-001", "phone_contact": None, "name_on_file": None, "verified": False},
            session={"session_id": "SESS-001", "started_at": "2026-05-13T14:26:00Z", "channel": "chat"},
            intent={"primary": "billing", "secondary": [], "confidence": 0.85},
            summary="Customer requested a human agent.",
            customer_emotion={"sentiment": "neutral", "indicators": []},
            transcript=[{"role": "customer", "content": "Help", "at": "2026-05-13T14:26:10Z"}],
            agent_attempts=["Could not resolve"],
            suggested_next_action="Assist customer directly",
        )
        context = StateContext(
            session_state=session,
            customer_message="I want to speak to a human.",
            routing_decision=RoutingDecision.SKIP_TO_ESCALATE,
            act_output=None,
            escalate_output=CreateEscalationTicketResult(success=True, ticket=ticket),
        )
        prompt = state._build_agent_prompt(context)
        assert "ESC-20260513-143023-9999" in prompt

    def test_tool_results_json_included_in_prompt(
        self, state: RespondState, session: SessionState
    ) -> None:
        """When act_output.tool_results_json is set, the prompt contains the data block."""
        payload = '{"billing_info": {"total": 42.50}}'
        act_out = ActOutput(
            resolution_status="resolved",
            tools_called=[],
            kb_citations=[],
            error_details=None,
            tool_results_json=payload,
        )
        context = StateContext(
            session_state=session,
            customer_message="What is my bill?",
            routing_decision=RoutingDecision.BILLING_PATH,
            act_output=act_out,
        )
        prompt = state._build_agent_prompt(context)
        assert "Tool result data (use this to answer the customer):" in prompt
        assert payload in prompt


class TestRespondStateMutationContract:
    """Tests for pure-function (no mutation) contract."""

    @pytest.mark.asyncio
    async def test_does_not_mutate_context(
        self, state: RespondState, resolved_context: StateContext
    ) -> None:
        """RespondState must not mutate the input context."""
        context_before = copy.deepcopy(resolved_context)
        with patch.object(state, "_invoke_agent", return_value=_agent_json()):
            await state.run(resolved_context)
        assert resolved_context.model_dump() == context_before.model_dump()
