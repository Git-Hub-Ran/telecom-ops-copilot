"""Tests for Act state output Pydantic models."""

import pytest
from pydantic import ValidationError

from src.orchestrator.models.act import ActOutput, KBCitation, ToolCallRecord


class TestToolCallRecord:
    """Test suite for ToolCallRecord model."""

    def test_accepts_all_required_fields(self) -> None:
        """Test that ToolCallRecord accepts all required fields."""
        record = ToolCallRecord(
            tool_name="get_billing_info",
            input={"account_id": "ACC-10001", "months": 3},
            result_summary="Retrieved 3 months of billing history",
            called_at="2026-06-17T14:30:00Z",
            success=True
        )
        assert record.tool_name == "get_billing_info"
        assert record.input == {"account_id": "ACC-10001", "months": 3}
        assert record.success is True

    def test_missing_tool_name_raises_validation_error(self) -> None:
        """Test that ToolCallRecord missing tool_name raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            ToolCallRecord(
                input={"account_id": "ACC-10001"},
                result_summary="Retrieved account info",
                called_at="2026-06-17T14:30:00Z",
                success=True
            )

        # Verify error mentions tool_name
        error_str = str(exc_info.value)
        assert "tool_name" in error_str.lower()

    def test_error_code_can_be_none(self) -> None:
        """Test that ToolCallRecord error_code can be None."""
        record = ToolCallRecord(
            tool_name="get_billing_info",
            input={"account_id": "ACC-10001"},
            result_summary="Success",
            called_at="2026-06-17T14:30:00Z",
            success=True,
            error_code=None
        )
        assert record.error_code is None


class TestKBCitation:
    """Test suite for KBCitation model."""

    def test_accepts_all_required_fields(self) -> None:
        """Test that KBCitation accepts all required fields."""
        citation = KBCitation(
            doc_id="kb/policies/02-late-fees.md",
            section="Grace Period Policy",
            relevance="Explains the 5-day grace period for late payments"
        )
        assert citation.doc_id == "kb/policies/02-late-fees.md"
        assert citation.section == "Grace Period Policy"
        assert citation.relevance == "Explains the 5-day grace period for late payments"

    def test_missing_doc_id_raises_validation_error(self) -> None:
        """Test that KBCitation missing doc_id raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            KBCitation(
                section="Grace Period Policy",
                relevance="Explains grace period"
            )

        # Verify error mentions doc_id
        error_str = str(exc_info.value)
        assert "doc_id" in error_str.lower()


class TestActOutput:
    """Test suite for ActOutput model."""

    def test_accepts_valid_resolution_status_resolved(self) -> None:
        """Test that ActOutput accepts valid resolution_status 'resolved'."""
        output = ActOutput(
            resolution_status="resolved",
            tools_called=[],
            kb_citations=[]
        )
        assert output.resolution_status == "resolved"

    def test_rejects_invalid_resolution_status_value(self) -> None:
        """Test that ActOutput rejects invalid resolution_status value."""
        with pytest.raises(ValidationError) as exc_info:
            ActOutput(
                resolution_status="completed",  # Invalid: not in allowed values
                tools_called=[],
                kb_citations=[]
            )

        # Verify error mentions resolution_status
        error_str = str(exc_info.value)
        assert "resolution_status" in error_str.lower()

    def test_tools_called_defaults_to_empty_list(self) -> None:
        """Test that ActOutput tools_called defaults to empty list."""
        output = ActOutput(
            resolution_status="resolved"
        )
        assert output.tools_called == []
        assert isinstance(output.tools_called, list)

    def test_kb_citations_defaults_to_empty_list(self) -> None:
        """Test that ActOutput kb_citations defaults to empty list."""
        output = ActOutput(
            resolution_status="partial"
        )
        assert output.kb_citations == []
        assert isinstance(output.kb_citations, list)

    def test_accepts_list_of_tool_call_record_and_kb_citation(self) -> None:
        """Test that ActOutput accepts list of ToolCallRecord and list of KBCitation."""
        tool_calls = [
            ToolCallRecord(
                tool_name="get_billing_info",
                input={"account_id": "ACC-10001"},
                result_summary="Retrieved billing info",
                called_at="2026-06-17T14:30:00Z",
                success=True
            )
        ]

        citations = [
            KBCitation(
                doc_id="kb/policies/02-late-fees.md",
                section="Grace Period",
                relevance="Explains grace period policy"
            )
        ]

        output = ActOutput(
            resolution_status="resolved",
            tools_called=tool_calls,
            kb_citations=citations
        )

        assert len(output.tools_called) == 1
        assert len(output.kb_citations) == 1
        assert output.tools_called[0].tool_name == "get_billing_info"
        assert output.kb_citations[0].doc_id == "kb/policies/02-late-fees.md"
