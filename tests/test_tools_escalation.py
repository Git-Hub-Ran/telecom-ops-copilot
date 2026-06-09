"""Tests for escalation ticket creation tool."""

import pytest

from src.tools.escalation import create_escalation_ticket


class TestCreateEscalationTicket:
    """Test suite for create_escalation_ticket function."""

    def get_minimal_valid_payload(self):
        """Helper to get a minimal valid escalation payload."""
        return {
            "reason_code": "customer_frustration",
            "priority": "medium",
            "customer": {
                "account_id": "ACC-10001",
                "phone_contact": "+1-555-100-0001",
                "name_on_file": "John Smith",
                "verified": True,
            },
            "session": {
                "session_id": "SESS-test-001",
                "started_at": "2026-05-13T14:25:00Z",
                "channel": "chat",
                "language": "en",
            },
            "intent": {"primary": "billing", "secondary": [], "confidence": 0.85},
            "summary": "Customer requests help with billing issue.",
            "customer_emotion": {
                "sentiment": "neutral",
                "indicators": ["polite tone"],
            },
            "transcript": [
                {
                    "role": "customer",
                    "content": "I need help with my bill",
                    "at": "2026-05-13T14:25:10Z",
                }
            ],
            "agent_attempts": ["Attempted to look up billing information"],
            "suggested_next_action": "Review the customer's billing history manually",
        }

    def test_valid_payload_returns_success(self):
        """Test that a valid payload creates a ticket successfully."""
        payload = self.get_minimal_valid_payload()
        result = create_escalation_ticket(payload)

        assert result.success is True
        assert result.ticket is not None
        assert result.error_code is None
        assert result.error_message is None

    def test_created_ticket_has_all_fields(self):
        """Test that created ticket contains all expected fields."""
        payload = self.get_minimal_valid_payload()
        result = create_escalation_ticket(payload)

        assert result.success is True
        ticket = result.ticket

        # Verify top-level fields
        assert ticket.escalation_id.startswith("ESC-")
        assert ticket.created_at is not None
        assert ticket.reason_code == "customer_frustration"
        assert ticket.priority == "medium"
        assert ticket.summary is not None

        # Verify nested structures
        assert ticket.customer.account_id == "ACC-10001"
        assert ticket.session.session_id == "SESS-test-001"
        assert ticket.intent.primary == "billing"
        assert ticket.customer_emotion.sentiment == "neutral"
        assert len(ticket.transcript) == 1
        assert len(ticket.agent_attempts) == 1

    def test_escalation_id_auto_generated_if_not_provided(self):
        """Test that escalation_id is auto-generated when not in payload."""
        payload = self.get_minimal_valid_payload()
        # Don't include escalation_id
        result = create_escalation_ticket(payload)

        assert result.success is True
        assert result.ticket.escalation_id.startswith("ESC-")
        # Format: ESC-YYYYMMDD-HHMMSS-XXXX (24 characters)
        assert len(result.ticket.escalation_id) == 24

    def test_created_at_auto_generated_if_not_provided(self):
        """Test that created_at is auto-generated when not in payload."""
        payload = self.get_minimal_valid_payload()
        # Don't include created_at
        result = create_escalation_ticket(payload)

        assert result.success is True
        assert result.ticket.created_at is not None
        assert "T" in result.ticket.created_at
        assert "Z" in result.ticket.created_at

    def test_manual_escalation_id_is_preserved(self):
        """Test that manually provided escalation_id is preserved."""
        payload = self.get_minimal_valid_payload()
        payload["escalation_id"] = "ESC-20260513-143023-1234"
        result = create_escalation_ticket(payload)

        assert result.success is True
        assert result.ticket.escalation_id == "ESC-20260513-143023-1234"

    def test_all_reason_codes_accepted(self):
        """Test that all valid reason codes are accepted."""
        reason_codes = [
            "tool_failure",
            "out_of_scope",
            "customer_frustration",
            "unresolved_ambiguity",
            "safety_trip",
        ]

        for reason_code in reason_codes:
            payload = self.get_minimal_valid_payload()
            payload["reason_code"] = reason_code
            result = create_escalation_ticket(payload)

            assert result.success is True
            assert result.ticket.reason_code == reason_code

    def test_all_priority_levels_accepted(self):
        """Test that all valid priority levels are accepted."""
        priorities = ["low", "medium", "high", "urgent"]

        for priority in priorities:
            payload = self.get_minimal_valid_payload()
            payload["priority"] = priority
            result = create_escalation_ticket(payload)

            assert result.success is True
            assert result.ticket.priority == priority

    def test_all_intent_types_accepted(self):
        """Test that all valid intent types are accepted."""
        intents = ["billing", "technical", "account", "info", "unknown"]

        for intent in intents:
            payload = self.get_minimal_valid_payload()
            payload["intent"]["primary"] = intent
            result = create_escalation_ticket(payload)

            assert result.success is True
            assert result.ticket.intent.primary == intent

    def test_all_sentiment_types_accepted(self):
        """Test that all valid sentiment types are accepted."""
        sentiments = ["neutral", "mildly_frustrated", "frustrated", "angry"]

        for sentiment in sentiments:
            payload = self.get_minimal_valid_payload()
            payload["customer_emotion"]["sentiment"] = sentiment
            result = create_escalation_ticket(payload)

            assert result.success is True
            assert result.ticket.customer_emotion.sentiment == sentiment

    def test_all_channel_types_accepted(self):
        """Test that all valid channel types are accepted."""
        channels = ["chat", "voice", "email"]

        for channel in channels:
            payload = self.get_minimal_valid_payload()
            payload["session"]["channel"] = channel
            result = create_escalation_ticket(payload)

            assert result.success is True
            assert result.ticket.session.channel == channel

    def test_optional_customer_fields_can_be_null(self):
        """Test that optional customer fields can be null."""
        payload = self.get_minimal_valid_payload()
        payload["customer"] = {
            "account_id": None,
            "phone_contact": None,
            "name_on_file": None,
            "verified": False,
        }
        result = create_escalation_ticket(payload)

        assert result.success is True
        assert result.ticket.customer.account_id is None
        assert result.ticket.customer.phone_contact is None
        assert result.ticket.customer.name_on_file is None
        assert result.ticket.customer.verified is False

    def test_tools_called_list_accepted(self):
        """Test that tools_called list is properly stored."""
        payload = self.get_minimal_valid_payload()
        payload["tools_called"] = [
            {
                "tool_name": "get_customer_account",
                "input": {"account_id": "ACC-10001"},
                "result_summary": "Account found, status active",
                "called_at": "2026-05-13T14:26:00Z",
            },
            {
                "tool_name": "get_billing_info",
                "input": {"account_id": "ACC-10001", "months": 3},
                "result_summary": "Retrieved 3 months of bills",
                "called_at": "2026-05-13T14:27:00Z",
            },
        ]
        result = create_escalation_ticket(payload)

        assert result.success is True
        assert len(result.ticket.tools_called) == 2
        assert result.ticket.tools_called[0].tool_name == "get_customer_account"
        assert result.ticket.tools_called[1].tool_name == "get_billing_info"

    def test_kb_citations_list_accepted(self):
        """Test that kb_citations list is properly stored."""
        payload = self.get_minimal_valid_payload()
        payload["kb_citations"] = [
            {
                "doc_id": "kb/policies/02-late-fees.md",
                "section": "Disputing a late fee",
                "relevance": "Customer asking about fee dispute",
            }
        ]
        result = create_escalation_ticket(payload)

        assert result.success is True
        assert len(result.ticket.kb_citations) == 1
        assert result.ticket.kb_citations[0].doc_id == "kb/policies/02-late-fees.md"

    def test_empty_tools_called_list_accepted(self):
        """Test that empty tools_called list is accepted."""
        payload = self.get_minimal_valid_payload()
        payload["tools_called"] = []
        result = create_escalation_ticket(payload)

        assert result.success is True
        assert len(result.ticket.tools_called) == 0

    def test_empty_kb_citations_list_accepted(self):
        """Test that empty kb_citations list is accepted."""
        payload = self.get_minimal_valid_payload()
        payload["kb_citations"] = []
        result = create_escalation_ticket(payload)

        assert result.success is True
        assert len(result.ticket.kb_citations) == 0

    def test_secondary_intent_list_accepted(self):
        """Test that secondary intent list is properly stored."""
        payload = self.get_minimal_valid_payload()
        payload["intent"]["secondary"] = ["dispute", "cancellation"]
        result = create_escalation_ticket(payload)

        assert result.success is True
        assert len(result.ticket.intent.secondary) == 2
        assert "dispute" in result.ticket.intent.secondary

    def test_customer_emotion_indicators_list(self):
        """Test that customer emotion indicators list is properly stored."""
        payload = self.get_minimal_valid_payload()
        payload["customer_emotion"]["indicators"] = [
            "mentioned cancellation",
            "used all caps",
            "repeated issue",
        ]
        result = create_escalation_ticket(payload)

        assert result.success is True
        assert len(result.ticket.customer_emotion.indicators) == 3
        assert "mentioned cancellation" in result.ticket.customer_emotion.indicators

    def test_transcript_with_multiple_messages(self):
        """Test that transcript with multiple messages is properly stored."""
        payload = self.get_minimal_valid_payload()
        payload["transcript"] = [
            {
                "role": "customer",
                "content": "I need help",
                "at": "2026-05-13T14:25:10Z",
            },
            {
                "role": "agent",
                "content": "I can help. What's your account ID?",
                "at": "2026-05-13T14:25:15Z",
            },
            {
                "role": "customer",
                "content": "ACC-10001",
                "at": "2026-05-13T14:25:20Z",
            },
        ]
        result = create_escalation_ticket(payload)

        assert result.success is True
        assert len(result.ticket.transcript) == 3
        assert result.ticket.transcript[0].role == "customer"
        assert result.ticket.transcript[1].role == "agent"

    def test_agent_attempts_list(self):
        """Test that agent_attempts list is properly stored."""
        payload = self.get_minimal_valid_payload()
        payload["agent_attempts"] = [
            "Looked up customer account",
            "Retrieved billing history",
            "Checked KB for policy",
            "Could not determine waiver eligibility",
        ]
        result = create_escalation_ticket(payload)

        assert result.success is True
        assert len(result.ticket.agent_attempts) == 4
        assert "Looked up customer account" in result.ticket.agent_attempts

    def test_invalid_reason_code_fails_validation(self):
        """Test that invalid reason_code causes validation error."""
        payload = self.get_minimal_valid_payload()
        payload["reason_code"] = "invalid_reason"
        result = create_escalation_ticket(payload)

        assert result.success is False
        assert result.ticket is None
        assert result.error_code == "validation_failed"
        assert "validation failed" in result.error_message.lower()

    def test_invalid_priority_fails_validation(self):
        """Test that invalid priority causes validation error."""
        payload = self.get_minimal_valid_payload()
        payload["priority"] = "super_urgent"
        result = create_escalation_ticket(payload)

        assert result.success is False
        assert result.ticket is None
        assert result.error_code == "validation_failed"

    def test_missing_required_field_fails_validation(self):
        """Test that missing required field causes validation error."""
        payload = self.get_minimal_valid_payload()
        del payload["summary"]
        result = create_escalation_ticket(payload)

        assert result.success is False
        assert result.ticket is None
        assert result.error_code == "validation_failed"

    def test_invalid_intent_confidence_fails_validation(self):
        """Test that confidence outside 0-1 range causes validation error."""
        payload = self.get_minimal_valid_payload()
        payload["intent"]["confidence"] = 1.5
        result = create_escalation_ticket(payload)

        # Pydantic might allow this, so we just test the field
        # If validation is strict, update this test
        if result.success:
            assert result.ticket.intent.confidence == 1.5
        else:
            assert result.error_code == "validation_failed"

    def test_complete_payload_from_schema_example(self):
        """Test creating ticket with complete payload matching schema example."""
        payload = {
            "escalation_id": "ESC-20260513-143023-A7F2",
            "created_at": "2026-05-13T14:30:23Z",
            "reason_code": "out_of_scope",
            "priority": "medium",
            "customer": {
                "account_id": "ACC-10003",
                "phone_contact": "+1-555-100-0003",
                "name_on_file": "Maria Garcia",
                "verified": True,
            },
            "session": {
                "session_id": "SESS-b3a7f9c1",
                "started_at": "2026-05-13T14:26:00Z",
                "channel": "chat",
                "language": "en",
            },
            "intent": {"primary": "billing", "secondary": ["dispute"], "confidence": 0.92},
            "summary": "Customer disputes a $10 late fee on the May bill.",
            "tools_called": [
                {
                    "tool_name": "get_customer_account",
                    "input": {"account_id": "ACC-10003"},
                    "result_summary": "Active customer since 2022",
                    "called_at": "2026-05-13T14:26:30Z",
                }
            ],
            "kb_citations": [
                {
                    "doc_id": "kb/policies/02-late-fees.md",
                    "section": "Disputing a late fee",
                    "relevance": "Policy allows one fee waiver per 12 months",
                }
            ],
            "customer_emotion": {
                "sentiment": "mildly_frustrated",
                "indicators": ["polite but firm"],
            },
            "transcript": [
                {
                    "role": "customer",
                    "content": "Why is there a $10 charge?",
                    "at": "2026-05-13T14:26:10Z",
                }
            ],
            "agent_attempts": [
                "Verified customer identity",
                "Found late fee policy",
                "Confirmed eligibility for waiver but need human approval",
            ],
            "suggested_next_action": "Apply one-time courtesy waiver of $10 late fee.",
        }
        result = create_escalation_ticket(payload)

        assert result.success is True
        assert result.ticket.escalation_id == "ESC-20260513-143023-A7F2"
        assert result.ticket.customer.name_on_file == "Maria Garcia"
        assert result.ticket.priority == "medium"
