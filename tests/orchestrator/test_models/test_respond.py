"""Tests for RespondOutput Pydantic model."""

import pytest
from pydantic import ValidationError

from src.orchestrator.models.respond import RespondOutput


class TestRespondOutput:
    """Test suite for RespondOutput model."""

    def test_accepts_all_required_fields(self) -> None:
        """Test that RespondOutput accepts all required fields."""
        output = RespondOutput(
            message="Your current balance is $125.50."
        )
        assert output.message == "Your current balance is $125.50."
        assert output.citations == []
        assert output.metadata == {}

    def test_missing_message_raises_validation_error(self) -> None:
        """Test that RespondOutput missing message raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            RespondOutput(
                citations=["kb/policies/01-billing.md"]
            )

        # Verify error mentions message
        error_str = str(exc_info.value)
        assert "message" in error_str.lower()

    def test_citations_defaults_to_empty_list(self) -> None:
        """Test that RespondOutput citations defaults to empty list."""
        output = RespondOutput(
            message="How can I help you today?"
        )
        assert output.citations == []
        assert isinstance(output.citations, list)

    def test_metadata_defaults_to_empty_dict(self) -> None:
        """Test that RespondOutput metadata defaults to empty dict."""
        output = RespondOutput(
            message="Your bill is $125.50."
        )
        assert output.metadata == {}
        assert isinstance(output.metadata, dict)

    def test_accepts_list_of_citations(self) -> None:
        """Test that RespondOutput accepts list of citation strings."""
        output = RespondOutput(
            message="According to our policy, the grace period is 5 days.",
            citations=["kb/policies/02-late-fees.md", "kb/policies/01-billing.md"]
        )
        assert len(output.citations) == 2
        assert output.citations[0] == "kb/policies/02-late-fees.md"
        assert output.citations[1] == "kb/policies/01-billing.md"

    def test_metadata_can_include_escalation_offered_flag(self) -> None:
        """Test that RespondOutput metadata can include escalation_offered as UI state."""
        output = RespondOutput(
            message="I couldn't find that account. Would you like to speak with a representative?",
            citations=[],
            metadata={"error_code": "not_found", "escalation_offered": True}
        )
        assert output.metadata["error_code"] == "not_found"
        assert output.metadata["escalation_offered"] is True
