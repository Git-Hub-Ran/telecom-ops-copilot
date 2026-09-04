"""Tests for structured JSON logging."""

import json
from datetime import datetime
from io import StringIO
from unittest.mock import patch

from src.orchestrator.observability.structured import (
    StructuredLogger,
    log_classification_result,
    log_state_transition,
    log_tool_call,
)


class TestStructuredLogger:
    """Test suite for StructuredLogger class."""

    def test_log_event_emits_valid_json_to_stdout(self) -> None:
        """Test that log_event() emits valid JSON to stdout."""
        logger = StructuredLogger()

        # Capture stdout
        with patch("sys.stdout", new=StringIO()) as fake_stdout:
            logger.log_event(
                event_type="test_event",
                state_name="test_state",
                correlation_id="test-corr-123",
                level="info",
            )

            # Get captured output
            output = fake_stdout.getvalue().strip()

        # Should be parsable as JSON
        event = json.loads(output)
        assert isinstance(event, dict)

    def test_json_includes_required_fields(self) -> None:
        """Test that emitted JSON includes all required fields."""
        logger = StructuredLogger()

        with patch("sys.stdout", new=StringIO()) as fake_stdout:
            logger.log_event(
                event_type="test_event",
                state_name="test_state",
                correlation_id="test-corr-123",
                level="warn",
            )

            output = fake_stdout.getvalue().strip()

        event = json.loads(output)

        # Verify required fields exist
        assert "timestamp" in event
        assert "event_type" in event
        assert "state_name" in event
        assert "correlation_id" in event
        assert "level" in event

        # Verify field values
        assert event["event_type"] == "test_event"
        assert event["state_name"] == "test_state"
        assert event["correlation_id"] == "test-corr-123"
        assert event["level"] == "warn"

    def test_json_includes_optional_kwargs(self) -> None:
        """Test that emitted JSON includes additional kwargs."""
        logger = StructuredLogger()

        with patch("sys.stdout", new=StringIO()) as fake_stdout:
            logger.log_event(
                event_type="test_event",
                state_name="test_state",
                correlation_id="test-corr-123",
                level="info",
                custom_field="custom_value",
                duration_ms=340,
                success=True,
            )

            output = fake_stdout.getvalue().strip()

        event = json.loads(output)

        # Verify custom fields exist
        assert event["custom_field"] == "custom_value"
        assert event["duration_ms"] == 340
        assert event["success"] is True

    def test_timestamp_is_iso8601_format(self) -> None:
        """Test that timestamp is in ISO 8601 format with Z suffix."""
        logger = StructuredLogger()

        with patch("sys.stdout", new=StringIO()) as fake_stdout:
            logger.log_event(
                event_type="test_event",
                state_name="test_state",
                correlation_id="test-corr-123",
            )

            output = fake_stdout.getvalue().strip()

        event = json.loads(output)
        timestamp_str = event["timestamp"]

        # Should end with Z (Zulu time, UTC)
        assert timestamp_str.endswith("Z")

        # Should be parsable as ISO 8601 (replace Z with +00:00 for parsing)
        timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        assert isinstance(timestamp, datetime)

    def test_log_state_transition_emits_correct_event_type(self) -> None:
        """Test that log_state_transition() emits event_type='state_transition'."""
        logger = StructuredLogger()

        with patch("sys.stdout", new=StringIO()) as fake_stdout:
            log_state_transition(
                logger=logger,
                from_state="classify",
                to_state="route",
                correlation_id="test-corr",
                duration_ms=340,
                decision_reason="intent=billing",
            )

            output = fake_stdout.getvalue().strip()

        event = json.loads(output)

        # Verify event_type
        assert event["event_type"] == "state_transition"
        assert event["from_state"] == "classify"
        assert event["to_state"] == "route"
        assert event["duration_ms"] == 340
        assert event["decision_reason"] == "intent=billing"

    def test_log_tool_call_emits_correct_event_type(self) -> None:
        """Test that log_tool_call() emits event_type='tool_call'."""
        logger = StructuredLogger()

        with patch("sys.stdout", new=StringIO()) as fake_stdout:
            log_tool_call(
                logger=logger,
                tool_name="get_billing_info",
                state_name="act",
                correlation_id="test-corr",
                success=True,
                duration_ms=450,
                input_summary="account_id=ACC-10001",
                output_summary="Retrieved 3 bills",
            )

            output = fake_stdout.getvalue().strip()

        event = json.loads(output)

        # Verify event_type
        assert event["event_type"] == "tool_call"
        assert event["tool_name"] == "get_billing_info"
        assert event["success"] is True
        assert event["duration_ms"] == 450

    def test_log_classification_result_emits_correct_event_type(self) -> None:
        """Test that log_classification_result() emits event_type='classification_result'."""
        logger = StructuredLogger()

        with patch("sys.stdout", new=StringIO()) as fake_stdout:
            log_classification_result(
                logger=logger,
                correlation_id="test-corr",
                intent="billing",
                confidence=0.92,
                detected_emotion="neutral",
                off_topic=False,
                message_length=27,
            )

            output = fake_stdout.getvalue().strip()

        event = json.loads(output)

        # Verify event_type
        assert event["event_type"] == "classification_result"
        assert event["intent"] == "billing"
        assert event["confidence"] == 0.92
        assert event["detected_emotion"] == "neutral"
        assert event["off_topic"] is False
        assert event["message_length"] == 27
