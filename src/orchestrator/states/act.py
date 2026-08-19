"""ActState implementation for tool-calling and KB retrieval.

Dispatches to one of four path methods based on RoutingDecision, calls
existing Python tool functions directly for BILLING, ACCOUNT, and TECHNICAL
paths, and invokes the act agent (file_search enabled) for INFO_PATH.

Per FR-035, transient tool errors are retried once with 250 ms backoff.
Per FR-044, error_code drives resolution_status (partial vs unresolved).
Per FR-048, each tool attempt is logged as a tool_call event.
"""

import asyncio
import json
from datetime import datetime, timezone
from functools import lru_cache
from time import monotonic
from typing import Any

from azure.ai.agents.models import MessageRole

from src.orchestrator.agents.factory import AgentFactory
from src.orchestrator.models import (
    ActOutput,
    KBCitation,
    RoutingDecision,
    StateContext,
    ToolCallRecord,
)
from src.orchestrator.observability.structured import StructuredLogger, log_tool_call
from src.config import PROJECT_ROOT, get_config
from src.orchestrator.states.base import BaseState
from src.tools.billing import GetBillingInfoResult, get_billing_info
from src.tools.customer import get_customer_account
from src.tools.diagnostic import run_speed_diagnostic
from src.tools.outage import check_network_outage

# Error codes that resolve to "partial" without triggering a retry.
# These indicate a caller-side problem that a retry cannot fix.
_PARTIAL_ERROR_CODES: frozenset[str] = frozenset({"invalid_format", "not_found"})

# Routing decisions that must never be routed to ActState.
_BYPASS_DECISIONS: frozenset[RoutingDecision] = frozenset({
    RoutingDecision.SKIP_TO_ESCALATE,
    RoutingDecision.ASK_CLARIFYING_QUESTION,
    RoutingDecision.REFUSE_OFF_TOPIC,
})

def _format_billing_outputs(
    result: GetBillingInfoResult,
) -> tuple[str | None, str | None]:
    """Return (tool_results_json, prepared_response) for a billing result.

    Returns (None, None) if result has no bills.
    """
    if not result.success or result.billing_info is None or not result.billing_info.bills:
        return None, None
    bill = result.billing_info.bills[0]

    def _fmt(val: float) -> str:
        return f"-${abs(val):.2f}" if val < 0 else f"${val:.2f}"

    summary = (
        f"Latest bill: period {bill.billing_period_start} to {bill.billing_period_end}, "
        f"total {_fmt(bill.total)}, subtotal {_fmt(bill.subtotal)}, "
        f"discounts {_fmt(bill.discounts)}, taxes {_fmt(bill.taxes)}, "
        f"due {bill.due_date}, status {bill.status}"
    )
    prepared = (
        f"Your latest bill covers {bill.billing_period_start} to {bill.billing_period_end}. "
        f"Total: {_fmt(bill.total)}. "
        f"This includes a subtotal of {_fmt(bill.subtotal)}, "
        f"discounts of {_fmt(bill.discounts)}, "
        f"and taxes of {_fmt(bill.taxes)}. "
        f"Due date: {bill.due_date}. Status: {bill.status}."
    )
    return summary, prepared


def _now_iso() -> str:
    """Return current UTC time as an ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _status_from_record(record: ToolCallRecord) -> str:
    """Map a single ToolCallRecord to a resolution_status string.

    Args:
        record: Completed tool call record.

    Returns:
        "resolved" if the call succeeded, "partial" for caller-side errors
        (invalid_format, not_found), or "unresolved" for transient/system errors.
    """
    if record.success:
        return "resolved"
    if record.error_code in _PARTIAL_ERROR_CODES:
        return "partial"
    return "unresolved"


def _worst_status(statuses: list[str]) -> str:
    """Return the most severe resolution_status from a list.

    Args:
        statuses: List of resolution_status strings.

    Returns:
        "unresolved" if any entry is unresolved, "partial" if any is partial,
        otherwise "resolved".
    """
    if "unresolved" in statuses:
        return "unresolved"
    if "partial" in statuses:
        return "partial"
    return "resolved"


def _first_error(records: list[ToolCallRecord]) -> str | None:
    """Return the error_code of the first failed ToolCallRecord, or None.

    Args:
        records: List of tool call records from a multi-step path.

    Returns:
        First non-None error_code found, or None if all calls succeeded.
    """
    for record in records:
        if not record.success and record.error_code:
            return record.error_code
    return None


@lru_cache(maxsize=1)
def _kb_index() -> tuple[frozenset[str], dict[str, str]]:
    """Return (canonical KB paths, basename to canonical path lookup).

    Cached so the kb/ directory is scanned once per process on first use rather
    than as an import side effect. KB basenames are unique, so a doc_id carrying
    only a basename resolves unambiguously to one canonical path.
    """
    paths = {
        p.relative_to(PROJECT_ROOT).as_posix()
        for p in (PROJECT_ROOT / "kb").rglob("*.md")
    }
    return frozenset(paths), {p.rsplit("/", 1)[-1]: p for p in paths}


def _validate_citations(
    citations: list[KBCitation], logger: StructuredLogger, correlation_id: str
) -> list[KBCitation]:
    """Normalise citation doc_ids to canonical KB paths and drop fabricated ones.

    The act agent returns doc_id verbatim from its own output, which in practice
    mixes canonical paths, bare basenames, and paths for documents that do not
    exist. A doc_id whose basename matches a real KB file is normalised; anything
    else is dropped so the customer is never shown a citation to a document that
    cannot be retrieved.

    Args:
        citations: Citations parsed from the act agent JSON response.
        logger: StructuredLogger for emitting citation_dropped events.
        correlation_id: Tracing ID for log events.

    Returns:
        Citations with canonical doc_ids, excluding any that match no KB file.
    """
    kb_paths, kb_by_basename = _kb_index()
    validated: list[KBCitation] = []
    for citation in citations:
        if citation.doc_id in kb_paths:
            validated.append(citation)
            continue
        canonical = kb_by_basename.get(citation.doc_id.rsplit("/", 1)[-1])
        if canonical is not None:
            validated.append(citation.model_copy(update={"doc_id": canonical}))
            continue
        logger.log_event(
            event_type="citation_dropped",
            state_name="act",
            correlation_id=correlation_id,
            level="warn",
            doc_id=citation.doc_id,
            reason="not_found_in_kb",
        )
    return validated


class ActState(BaseState[StateContext, ActOutput]):
    """Tool-calling state that executes actions based on the routing decision.

    Dispatches to one of four path methods:
    - BILLING_PATH: calls get_billing_info with account_id
    - ACCOUNT_PATH: calls get_customer_account with account_id
    - TECHNICAL_PATH: calls get_customer_account, check_network_outage, and
      run_speed_diagnostic in sequence; all attempted calls are recorded
    - INFO_PATH: invokes the act agent (file_search enabled) for KB retrieval

    All tool calls go through _call_with_retry, which applies one retry with
    250 ms backoff for transient failures (FR-035). Each attempt is logged as
    a tool_call event (FR-048).

    Error handling per FR-044:
    - invalid_format or not_found: resolution_status="partial", no retry
    - data_unavailable, data_invalid, or exception: retry once, then "unresolved"
    """

    def __init__(self, agent_factory: AgentFactory) -> None:
        """Initialize with an agent factory.

        Args:
            agent_factory: AgentFactory for retrieving the act agent and its
                          underlying AgentsClient (used for INFO_PATH KB search).
        """
        self.factory = agent_factory
        self._logger = StructuredLogger()

    async def run(self, context: StateContext) -> ActOutput:
        """Execute the appropriate action path based on routing_decision.

        Reads routing_decision, account_id, and customer_message from context.
        Returns ActOutput without mutating context.

        Args:
            context: StateContext with routing_decision and session_state populated.

        Returns:
            ActOutput with resolution_status, tools_called, kb_citations,
            and error_details.

        Raises:
            ValueError: If routing_decision is None or is a bypass decision
                       (SKIP_TO_ESCALATE, ASK_CLARIFYING_QUESTION, REFUSE_OFF_TOPIC).
        """
        decision = context.routing_decision
        if decision is None:
            raise ValueError(
                "ActState requires routing_decision in context, but it was None. "
                "Ensure RouteState runs before ActState."
            )
        if decision in _BYPASS_DECISIONS:
            raise ValueError(
                f"ActState must not be called for bypass decision {decision!r}. "
                "The StateMachine should route this decision directly to Respond or Escalate."
            )

        correlation_id = context.session_state.correlation_id
        account_id = context.session_state.account_id

        if decision == RoutingDecision.BILLING_PATH:
            return await self._run_billing(account_id, correlation_id)
        if decision == RoutingDecision.ACCOUNT_PATH:
            return await self._run_account(account_id, correlation_id)
        if decision == RoutingDecision.TECHNICAL_PATH:
            return await self._run_technical(account_id, correlation_id)
        # INFO_PATH
        return await self._run_info(context.customer_message, correlation_id)

    async def _run_billing(
        self, account_id: str | None, correlation_id: str
    ) -> ActOutput:
        """Execute the billing path by calling get_billing_info.

        Args:
            account_id: Customer account ID from session state (may be None).
            correlation_id: Tracing ID for log events.

        Returns:
            ActOutput with a single ToolCallRecord and resolution_status.
        """
        if account_id is None:
            return ActOutput(
                resolution_status="partial",
                tools_called=[],
                kb_citations=[],
                error_details=(
                    "account_id is required for billing lookup but was not set in session_state."
                ),
            )

        result, record = await self._call_with_retry(
            get_billing_info,
            tool_name="get_billing_info",
            correlation_id=correlation_id,
            account_id=account_id,
            months=3,
        )
        tool_results_json, prepared_response = (
            _format_billing_outputs(result)
            if record.success and result is not None
            else (None, None)
        )
        return ActOutput(
            resolution_status=_status_from_record(record),
            tools_called=[record],
            kb_citations=[],
            error_details=record.error_code if not record.success else None,
            tool_results_json=tool_results_json,
            prepared_response=prepared_response,
        )

    async def _run_account(
        self, account_id: str | None, correlation_id: str
    ) -> ActOutput:
        """Execute the account path by calling get_customer_account.

        Args:
            account_id: Customer account ID from session state (may be None).
            correlation_id: Tracing ID for log events.

        Returns:
            ActOutput with a single ToolCallRecord and resolution_status.
        """
        if account_id is None:
            return ActOutput(
                resolution_status="partial",
                tools_called=[],
                kb_citations=[],
                error_details=(
                    "account_id is required for account lookup but was not set in session_state."
                ),
            )

        result, record = await self._call_with_retry(
            get_customer_account,
            tool_name="get_customer_account",
            correlation_id=correlation_id,
            account_id=account_id,
        )
        tool_results_json = (
            json.dumps(result.model_dump(), default=str) if record.success and result is not None else None
        )
        return ActOutput(
            resolution_status=_status_from_record(record),
            tools_called=[record],
            kb_citations=[],
            error_details=record.error_code if not record.success else None,
            tool_results_json=tool_results_json,
        )

    async def _run_technical(
        self, account_id: str | None, correlation_id: str
    ) -> ActOutput:
        """Execute the technical path: account lookup, outage check, speed diagnostic.

        Calls three tools in sequence. ToolCallRecord entries for every attempted
        call are appended to tools_called regardless of individual outcomes, so
        the full call history is available for observability and the eval framework.

        Step 1 failure aborts steps 2 and 3 (billing_zip is unavailable).
        Step 2 failure does NOT abort step 3.

        Args:
            account_id: Customer account ID from session state (may be None).
            correlation_id: Tracing ID for log events.

        Returns:
            ActOutput where resolution_status reflects the worst outcome across
            all attempted tool calls.
        """
        if account_id is None:
            return ActOutput(
                resolution_status="partial",
                tools_called=[],
                kb_citations=[],
                error_details=(
                    "account_id is required for technical diagnostics but was not set in session_state."
                ),
            )

        records: list[ToolCallRecord] = []

        # Step 1: fetch account to get billing_zip for outage check
        acct_result, acct_record = await self._call_with_retry(
            get_customer_account,
            tool_name="get_customer_account",
            correlation_id=correlation_id,
            account_id=account_id,
        )
        records.append(acct_record)

        if not acct_record.success:
            return ActOutput(
                resolution_status=_status_from_record(acct_record),
                tools_called=records,
                kb_citations=[],
                error_details=acct_record.error_code,
            )

        # Step 2: check outage using billing_zip from account
        billing_zip: str = acct_result.account.billing_zip
        outage_result, outage_record = await self._call_with_retry(
            check_network_outage,
            tool_name="check_network_outage",
            correlation_id=correlation_id,
            zip_code=billing_zip,
        )
        records.append(outage_record)

        # Step 3: speed diagnostic (always runs if step 1 succeeded)
        diag_result, diag_record = await self._call_with_retry(
            run_speed_diagnostic,
            tool_name="run_speed_diagnostic",
            correlation_id=correlation_id,
            account_id=account_id,
        )
        records.append(diag_record)

        results_data: dict = {}
        if acct_record.success and acct_result is not None:
            results_data["get_customer_account"] = acct_result.model_dump()
        if outage_record.success and outage_result is not None:
            results_data["check_network_outage"] = outage_result.model_dump()
        if diag_record.success and diag_result is not None:
            results_data["run_speed_diagnostic"] = diag_result.model_dump()
        tool_results_json = json.dumps(results_data, default=str) if results_data else None

        statuses = [_status_from_record(r) for r in records]
        return ActOutput(
            resolution_status=_worst_status(statuses),
            tools_called=records,
            kb_citations=[],
            error_details=_first_error(records),
            tool_results_json=tool_results_json,
        )

    async def _run_info(self, content: str, correlation_id: str) -> ActOutput:
        """Execute the info path by invoking the act agent with file_search.

        Args:
            content: Customer message to send to the act agent.
            correlation_id: Tracing ID for log events.

        Returns:
            ActOutput with kb_citations extracted from the agent JSON response,
            or resolution_status="unresolved" on agent failure.
        """
        raw_json = ""
        try:
            raw_json = await asyncio.to_thread(
                self._invoke_agent_for_kb, content
            )
            raw_json = raw_json.strip()
            if raw_json.startswith("```"):
                raw_json = raw_json.split("\n", 1)[1]
                raw_json = raw_json.rsplit("```", 1)[0].strip()
            data = json.loads(raw_json)
            parsed = [
                KBCitation(
                    doc_id=c.get("doc_id", ""),
                    section=c.get("section", ""),
                    relevance=c.get("relevance", ""),
                    text_content=c.get("text_content") or None,
                )
                for c in data.get("kb_citations", [])
            ]
            citations = _validate_citations(parsed, self._logger, correlation_id)
            self._logger.log_event(
                event_type="act_kb_result",
                state_name="act",
                correlation_id=correlation_id,
                level="info",
                resolution_status="resolved",
                kb_citation_count=len(citations),
            )
            return ActOutput(
                resolution_status="resolved",
                tools_called=[],
                kb_citations=citations,
                error_details=None,
            )
        except Exception as exc:
            self._logger.log_event(
                event_type="act_kb_error",
                state_name="act",
                correlation_id=correlation_id,
                level="error",
                error=str(exc),
                error_type=type(exc).__name__,
                raw_response_snippet=raw_json[:200],
            )
            return ActOutput(
                resolution_status="unresolved",
                tools_called=[],
                kb_citations=[],
                error_details=str(exc),
            )

    def _invoke_agent_for_kb(self, content: str) -> str:
        """Invoke the act agent synchronously and return its JSON response text.

        Designed to run inside asyncio.to_thread. Uses the act agent, which has
        file_search enabled on the vector store configured in Config.VECTOR_STORE_ID.

        Args:
            content: Customer message to send to the act agent.

        Returns:
            Raw JSON string from the act agent response.

        Raises:
            RuntimeError: If no assistant text response is found in the thread.
            azure.core.exceptions.HttpResponseError: If a Foundry API call fails.
        """
        client = self.factory.agents_client
        agent = self.factory.get_act_agent()
        thread = client.threads.create()
        client.messages.create(thread_id=thread.id, role="user", content=content)
        client.runs.create_and_process(thread_id=thread.id, agent_id=agent.id)
        msg = client.messages.get_last_message_text_by_role(
            thread_id=thread.id, role=MessageRole.AGENT
        )
        if msg is None:
            raise RuntimeError("No assistant text response found in act agent thread.")
        return msg.text.value

    async def _call_with_retry(
        self,
        fn: Any,
        tool_name: str,
        correlation_id: str,
        **tool_kwargs: Any,
    ) -> tuple[Any, ToolCallRecord]:
        """Call a tool function with one retry on transient failure.

        Wraps the synchronous tool function in asyncio.to_thread. On first
        attempt failure, checks error_code to decide whether to retry:
        - invalid_format or not_found: no retry (retrying cannot fix a caller error)
        - data_unavailable, data_invalid, or exception: retry once after 250 ms

        Logs a tool_call event after each attempt.

        Args:
            fn: Synchronous tool function to call.
            tool_name: Name used in ToolCallRecord and log events.
            correlation_id: Tracing ID for log events.
            **tool_kwargs: Keyword arguments forwarded to fn on each attempt.

        Returns:
            Tuple of (raw result object or None, ToolCallRecord).
            The result is None when an exception was raised on all attempts.
        """
        async def _attempt() -> tuple[Any, bool, str | None, str, int]:
            start = monotonic()
            try:
                result = await asyncio.to_thread(fn, **tool_kwargs)
                duration_ms = int((monotonic() - start) * 1000)
                if result.success:
                    return result, True, None, f"{tool_name} succeeded", duration_ms
                return (
                    result,
                    False,
                    result.error_code,
                    result.error_message or "",
                    duration_ms,
                )
            except Exception as exc:
                duration_ms = int((monotonic() - start) * 1000)
                return None, False, "exception", str(exc), duration_ms

        result, success, error_code, summary, duration_ms = await _attempt()

        log_tool_call(
            logger=self._logger,
            tool_name=tool_name,
            state_name="act",
            correlation_id=correlation_id,
            success=success,
            duration_ms=duration_ms,
            input_summary=str(tool_kwargs),
            output_summary=summary,
        )

        # Caller-side errors: no retry, resolve as partial
        if not success and error_code in _PARTIAL_ERROR_CODES:
            return result, ToolCallRecord(
                tool_name=tool_name,
                input=dict(tool_kwargs),
                result_summary=summary,
                called_at=_now_iso(),
                success=False,
                error_code=error_code,
            )

        # First attempt succeeded
        if success:
            return result, ToolCallRecord(
                tool_name=tool_name,
                input=dict(tool_kwargs),
                result_summary=summary,
                called_at=_now_iso(),
                success=True,
                error_code=None,
            )

        # Transient failure: one retry after 250 ms backoff
        await asyncio.sleep(get_config().RETRY_BACKOFF_MS / 1000)
        result2, success2, error_code2, summary2, duration_ms2 = await _attempt()

        log_tool_call(
            logger=self._logger,
            tool_name=tool_name,
            state_name="act",
            correlation_id=correlation_id,
            success=success2,
            duration_ms=duration_ms2,
            input_summary=str(tool_kwargs),
            output_summary=f"retry: {summary2}",
        )

        return result2, ToolCallRecord(
            tool_name=tool_name,
            input=dict(tool_kwargs),
            result_summary=summary2,
            called_at=_now_iso(),
            success=success2,
            error_code=error_code2 if not success2 else None,
        )
