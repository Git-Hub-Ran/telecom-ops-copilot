"""Tests for ClassifyOutput Pydantic model."""

import pytest
from pydantic import ValidationError

from src.orchestrator.models.classify import ClassifyOutput


class TestClassifyOutput:
    """Test suite for ClassifyOutput model."""

    def test_accepts_valid_intent_billing(self) -> None:
        """Test that ClassifyOutput accepts valid intent 'billing'."""
        output = ClassifyOutput(
            intent="billing",
            confidence=0.92,
            detected_emotion="neutral",
            off_topic=False
        )
        assert output.intent == "billing"
        assert output.confidence == 0.92

    def test_accepts_valid_intent_escalate(self) -> None:
        """Test that ClassifyOutput accepts valid intent 'escalate'."""
        output = ClassifyOutput(
            intent="escalate",
            confidence=0.95,
            off_topic=False
        )
        assert output.intent == "escalate"
        assert output.confidence == 0.95

    def test_rejects_invalid_intent_value(self) -> None:
        """Test that ClassifyOutput rejects invalid intent value."""
        with pytest.raises(ValidationError) as exc_info:
            ClassifyOutput(
                intent="refund",  # Invalid: not in the 6 allowed values
                confidence=0.8,
                off_topic=False
            )

        # Verify error mentions the intent field
        error_str = str(exc_info.value)
        assert "intent" in error_str.lower()

    def test_confidence_092_is_valid(self) -> None:
        """Test that ClassifyOutput confidence=0.92 is valid."""
        output = ClassifyOutput(
            intent="billing",
            confidence=0.92,
            off_topic=False
        )
        assert output.confidence == 0.92

    def test_confidence_negative_raises_validation_error(self) -> None:
        """Test that ClassifyOutput confidence=-0.1 raises ValidationError (below ge=0.0)."""
        with pytest.raises(ValidationError) as exc_info:
            ClassifyOutput(
                intent="billing",
                confidence=-0.1,  # Invalid: below 0.0
                off_topic=False
            )

        # Verify error mentions confidence or the constraint
        error_str = str(exc_info.value)
        assert "confidence" in error_str.lower() or "greater" in error_str.lower()

    def test_confidence_above_1_raises_validation_error(self) -> None:
        """Test that ClassifyOutput confidence=1.5 raises ValidationError (above le=1.0)."""
        with pytest.raises(ValidationError) as exc_info:
            ClassifyOutput(
                intent="technical",
                confidence=1.5,  # Invalid: above 1.0
                off_topic=False
            )

        # Verify error mentions confidence or the constraint
        error_str = str(exc_info.value)
        assert "confidence" in error_str.lower() or "less" in error_str.lower()

    def test_off_topic_defaults_to_false(self) -> None:
        """Test that ClassifyOutput off_topic defaults to False."""
        output = ClassifyOutput(
            intent="info",
            confidence=0.88
        )
        assert output.off_topic is False
