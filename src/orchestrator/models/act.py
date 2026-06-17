"""Act state output models including tool calls and KB citations.

This module defines the data contracts for the Act state, which handles tool
execution and knowledge base retrieval. ActOutput aggregates all tool call
results and KB citations to determine resolution status.

Per FR-013, ActOutput must include: resolution_status, tools_called list,
kb_citations list, and error_details.

Per FR-028, ToolCallRecord must include: tool_name, input, result_summary,
success, called_at, and duration_ms (note: current implementation uses
called_at timestamp only, duration_ms will be added in state implementation).
"""

from typing import Literal, Optional

from pydantic import BaseModel, Field


class ToolCallRecord(BaseModel):
    """Record of a single tool call made by ActAgent.

    This model captures the complete audit trail for each tool invocation,
    including inputs, outputs, success status, and timing information.
    Used for escalation payloads, analytics, and debugging.

    Per FR-028, all tool call records must include timing and success tracking.
    """

    tool_name: str = Field(
        description="Tool function name (e.g., get_customer_account, get_billing_info)"
    )
    input: dict = Field(
        description="Tool input arguments as dictionary"
    )
    result_summary: str = Field(
        description="Human-readable summary of tool result for logging and escalation"
    )
    called_at: str = Field(
        description="ISO 8601 timestamp when tool was invoked (e.g., 2026-06-17T14:30:00Z)"
    )
    success: bool = Field(
        description="True if tool returned success=True, False otherwise"
    )
    error_code: Optional[str] = Field(
        default=None,
        description="Error code if success=False (e.g., not_found, invalid_format, data_unavailable)"
    )


class KBCitation(BaseModel):
    """Citation from knowledge base file search.

    This model represents a single KB document or section retrieved during
    Act state execution. Citations are included in final responses to ground
    answers in authoritative sources.

    Per FR-013, KB citations must be tracked alongside tool calls in ActOutput.
    """

    doc_id: str = Field(
        description="KB document identifier (e.g., kb/policies/02-late-fees.md)"
    )
    section: str = Field(
        description="Section title or heading within the document"
    )
    relevance: str = Field(
        description="Explanation of why this citation is relevant to the customer query"
    )


class ActOutput(BaseModel):
    """Result from ActState after tool calls and KB retrieval.

    This model aggregates all Act state execution results including tool calls,
    KB citations, and resolution status. The resolution_status field determines
    whether the orchestrator proceeds to Respond or escalates to a human.

    Per FR-013, ActOutput must include resolution_status, tools_called list,
    kb_citations list, and error_details.

    Validation rules:
    - If resolution_status="resolved", error_details should be None
    - If resolution_status="unresolved", error_details should explain the failure
    - tools_called can be empty for info-only queries (KB retrieval without tools)
    - kb_citations can be empty if no KB retrieval occurred

    Example (resolved with tool call):
        {
            "resolution_status": "resolved",
            "tools_called": [
                {
                    "tool_name": "get_billing_info",
                    "input": {"account_id": "ACC-10001", "months": 3},
                    "result_summary": "Retrieved 3 months of billing history",
                    "called_at": "2026-06-17T14:30:00Z",
                    "success": true,
                    "error_code": null
                }
            ],
            "kb_citations": [],
            "error_details": null
        }
    """

    resolution_status: Literal["resolved", "partial", "unresolved"] = Field(
        description="Whether the query was fully resolved, partially resolved, or unresolved"
    )
    tools_called: list[ToolCallRecord] = Field(
        default_factory=list,
        description="List of tools called during Act state (empty if info-only query)"
    )
    kb_citations: list[KBCitation] = Field(
        default_factory=list,
        description="KB documents retrieved and used for grounding"
    )
    error_details: Optional[str] = Field(
        default=None,
        description="Error explanation if resolution_status=unresolved"
    )
