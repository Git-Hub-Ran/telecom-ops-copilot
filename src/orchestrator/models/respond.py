"""Response output models from RespondState.

This module defines the final customer-facing response schema. RespondState
generates the message text, KB document citations, and optional metadata for
analytics and UI state.

Per FR-017, RespondOutput must include: message, citations list, and metadata.
"""

from pydantic import BaseModel, Field


class RespondOutput(BaseModel):
    """Final response to customer from RespondAgent.

    This model represents the complete response package delivered to the customer,
    including the message text, KB citations used as evidence, and metadata for
    analytics or UI state.

    Per FR-017, RespondOutput must include: message (str), citations (list[str]),
    and metadata (dict).

    The citations field contains KB document IDs or section identifiers that were
    used to ground the response. Empty if no KB retrieval occurred.

    The metadata field can capture UI-specific state like escalation_offered flag,
    tool call counts, error codes, or other analytics data.

    Example (with KB citations):
        {
            "message": "According to our late payment policy, the grace period is 5 business days. Your bill is due on June 15th, so the grace period extends to June 22nd.",
            "citations": ["kb/policies/02-late-fees.md"],
            "metadata": {
                "kb_docs_used": 1,
                "tools_called": 0
            }
        }

    Example (not_found error with escalation offered via metadata):
        {
            "message": "I couldn't find an account with ID ACC-99999. Would you like me to connect you with a representative to verify your account information?",
            "citations": [],
            "metadata": {
                "error_code": "not_found",
                "escalation_offered": true
            }
        }
    """

    message: str = Field(
        description="Customer-facing response text"
    )
    citations: list[str] = Field(
        default_factory=list,
        description="List of KB document IDs or section identifiers used as evidence in the response. Empty list if no KB was consulted."
    )
    metadata: dict = Field(
        default_factory=dict,
        description="Optional metadata (tools_called count, kb_docs_used count, error_code, escalation_offered flag, etc.)"
    )
