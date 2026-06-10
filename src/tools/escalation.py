"""Escalation ticket creation tool.

This module provides the create_escalation_ticket function, which creates
a structured escalation payload for handoff to human support representatives.
"""

from datetime import datetime, timezone
from typing import Literal, Optional

from pydantic import BaseModel, Field


class CustomerInfo(BaseModel):
    """Customer identification information."""

    account_id: Optional[str] = Field(
        default=None, description="Account identifier (ACC-XXXXX) if known"
    )
    phone_contact: Optional[str] = Field(
        default=None, description="Customer contact phone number if known"
    )
    name_on_file: Optional[str] = Field(
        default=None, description="Customer name from account if known"
    )
    verified: bool = Field(
        description="Whether customer identity was verified during session"
    )


class SessionInfo(BaseModel):
    """Session metadata."""

    session_id: str = Field(description="Unique session identifier")
    started_at: str = Field(description="Session start time in ISO 8601 format (UTC)")
    channel: Literal["chat", "voice", "email"] = Field(
        description="Communication channel"
    )
    language: str = Field(default="en", description="Conversation language code")


class IntentInfo(BaseModel):
    """Classified customer intent."""

    primary: Literal["billing", "technical", "account", "info", "unknown"] = Field(
        description="Primary classified intent"
    )
    secondary: list[str] = Field(
        default_factory=list, description="Secondary or multi-intent classifications"
    )
    confidence: float = Field(
        description="Classification confidence score (0.0 to 1.0)"
    )


class ToolCall(BaseModel):
    """Record of a tool invocation."""

    tool_name: str = Field(description="Name of tool that was called")
    input: dict = Field(description="Tool input parameters")
    result_summary: str = Field(description="Brief summary of tool result")
    called_at: str = Field(description="Tool call timestamp in ISO 8601 format (UTC)")


class KBCitation(BaseModel):
    """Reference to a knowledge base document used."""

    doc_id: str = Field(description="Knowledge base document identifier")
    section: str = Field(description="Specific section referenced")
    relevance: str = Field(description="Why this document is relevant to the case")


class CustomerEmotion(BaseModel):
    """Customer emotional state assessment."""

    sentiment: Literal["neutral", "mildly_frustrated", "frustrated", "angry"] = Field(
        description="Overall sentiment classification"
    )
    indicators: list[str] = Field(
        description="Specific signals observed (e.g., 'mentioned cancellation', 'used all caps')"
    )


class TranscriptMessage(BaseModel):
    """A single message in the conversation transcript."""

    role: Literal["customer", "agent"] = Field(description="Speaker role")
    content: str = Field(description="Message content")
    at: str = Field(description="Message timestamp in ISO 8601 format (UTC)")


class EscalationPayload(BaseModel):
    """Complete escalation payload for human handoff."""

    escalation_id: str = Field(
        description="Unique escalation identifier (ESC-YYYYMMDD-HHMMSS-XXXX)"
    )
    created_at: str = Field(
        description="Escalation creation time in ISO 8601 format (UTC)"
    )
    reason_code: Literal[
        "tool_failure",
        "out_of_scope",
        "customer_frustration",
        "unresolved_ambiguity",
        "safety_trip",
    ] = Field(description="Machine-readable escalation reason")
    priority: Literal["low", "medium", "high", "urgent"] = Field(
        description="Escalation priority level"
    )
    customer: CustomerInfo = Field(description="Customer identification")
    session: SessionInfo = Field(description="Session metadata")
    intent: IntentInfo = Field(description="Classified intent")
    summary: str = Field(
        description="1-3 sentence plain-English summary of the situation"
    )
    tools_called: list[ToolCall] = Field(
        default_factory=list, description="Tools invoked during session"
    )
    kb_citations: list[KBCitation] = Field(
        default_factory=list, description="Knowledge base documents referenced"
    )
    customer_emotion: CustomerEmotion = Field(
        description="Customer emotional state assessment"
    )
    transcript: list[TranscriptMessage] = Field(
        description="Complete conversation transcript"
    )
    agent_attempts: list[str] = Field(
        description="Narrative list of what the agent tried"
    )
    suggested_next_action: str = Field(
        description="Recommended next step for human agent"
    )


class CreateEscalationTicketResult(BaseModel):
    """Result of escalation ticket creation.

    Returns either success with the created ticket, or an error with reason.
    The agent should check success=True before using ticket data.
    """

    success: bool = Field(
        description="True if ticket created, False if error occurred"
    )
    ticket: Optional[EscalationPayload] = Field(
        default=None, description="Created escalation ticket if success=True"
    )
    error_code: Optional[str] = Field(
        default=None,
        description="Error code if success=False: validation_failed or creation_failed",
    )
    error_message: Optional[str] = Field(
        default=None, description="Human-readable error explanation if success=False"
    )


def create_escalation_ticket(payload: dict) -> CreateEscalationTicketResult:
    """Create a structured escalation ticket for human handoff.

    This tool creates a complete escalation payload containing all context needed
    for a human support representative to pick up the case without starting cold.
    The payload includes customer info, conversation transcript, tools called,
    KB documents referenced, emotional state, and recommended next actions.

    Use this tool when:
    - A tool fails and you cannot resolve the customer's issue
    - The customer asks for something outside your authorization (e.g., account changes)
    - The customer expresses frustration or explicitly asks for a human
    - The conversation remains ambiguous after multiple clarification attempts
    - A content safety filter is triggered

    The payload must include the escalation reason, customer context, what you tried,
    and a summary that orients the human agent immediately.

    Args:
        payload: Dictionary containing the escalation data. Must include all required
                 fields per the escalation schema (see docs/ESCALATION_SCHEMA.md).
                 The escalation_id and created_at will be auto-generated if not provided.

    Returns:
        CreateEscalationTicketResult with either:
        - success=True and the created ticket with all fields validated
        - success=False with error_code and error_message explaining validation failures

    Examples:
        Create escalation for customer frustration:
            payload = {
                "reason_code": "customer_frustration",
                "priority": "high",
                "customer": {
                    "account_id": "ACC-10003",
                    "phone_contact": "+1-555-100-0003",
                    "name_on_file": "Maria Garcia",
                    "verified": True
                },
                "session": {
                    "session_id": "SESS-abc123",
                    "started_at": "2026-05-13T14:26:00Z",
                    "channel": "chat",
                    "language": "en"
                },
                "intent": {
                    "primary": "billing",
                    "secondary": ["dispute"],
                    "confidence": 0.92
                },
                "summary": "Customer disputes late fee, requesting waiver.",
                "customer_emotion": {
                    "sentiment": "mildly_frustrated",
                    "indicators": ["polite but firm"]
                },
                "transcript": [
                    {"role": "customer", "content": "Why is there a $10 charge?", "at": "2026-05-13T14:26:10Z"}
                ],
                "agent_attempts": ["Looked up account", "Found late fee policy"],
                "suggested_next_action": "Review waiver eligibility"
            }
            result = create_escalation_ticket(payload)
            if result.success:
                print(f"Ticket created: {result.ticket.escalation_id}")
    """
    try:
        # Auto-generate escalation_id if not provided
        if "escalation_id" not in payload:
            now = datetime.now(timezone.utc)
            # Format: ESC-YYYYMMDD-HHMMSS-XXXX
            import random

            random_suffix = f"{random.randint(0, 9999):04d}"
            payload["escalation_id"] = (
                f"ESC-{now.strftime('%Y%m%d-%H%M%S')}-{random_suffix}"
            )

        # Auto-generate created_at if not provided
        if "created_at" not in payload:
            payload["created_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        # Validate and parse the payload using Pydantic
        ticket = EscalationPayload(**payload)
        return CreateEscalationTicketResult(success=True, ticket=ticket)

    except ValueError as e:
        # Pydantic validation error
        return CreateEscalationTicketResult(
            success=False,
            error_code="validation_failed",
            error_message=f"Escalation payload validation failed: {str(e)}",
        )
    except Exception as e:
        # Any other error
        return CreateEscalationTicketResult(
            success=False,
            error_code="creation_failed",
            error_message=f"Failed to create escalation ticket: {str(e)}",
        )
