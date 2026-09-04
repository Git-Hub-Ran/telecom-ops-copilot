"""Structured JSON logging for orchestrator observability.

This module provides structured logging that emits JSON events to stdout for
ingestion by log aggregators (Application Insights, CloudWatch, Datadog, etc.).

Per FR-050, this implementation emits JSON to stdout without direct integration
with any specific cloud service. The structured format ensures compatibility with
any log aggregator.

Usage:
    from src.orchestrator.observability.structured import StructuredLogger

    logger = StructuredLogger()
    logger.log_event(
        event_type="state_transition",
        state_name="classify",
        correlation_id="abc123",
        level="info",
        from_state="classify",
        to_state="route",
        duration_ms=340
    )
"""

import json
from datetime import datetime, timezone
from typing import Any, Literal


class StructuredLogger:
    """Structured JSON logger for orchestrator events.

    Emits JSON-formatted log events to stdout. Each event includes required
    fields (timestamp, event_type, state_name, correlation_id, level) plus
    any additional event-specific fields passed as kwargs.

    The JSON output is one event per line, making it easy to parse by log
    aggregators and command-line tools like jq.

    Example:
        logger = StructuredLogger()
        logger.log_event(
            event_type="classification_result",
            state_name="classify",
            correlation_id="req-123",
            level="info",
            intent="billing",
            confidence=0.92
        )

        # Output:
        # {"timestamp":"2026-06-16T14:30:00Z","event_type":"classification_result",
        #  "state_name":"classify","correlation_id":"req-123","level":"info",
        #  "intent":"billing","confidence":0.92}
    """

    def log_event(
        self,
        event_type: str,
        state_name: str,
        correlation_id: str,
        level: Literal["info", "warn", "error"] = "info",
        **kwargs: Any,
    ) -> None:
        """Emit a structured JSON log event to stdout.

        Constructs a JSON object with required fields plus any additional kwargs,
        then prints it to stdout as a single line. The timestamp is auto-generated
        using timezone-aware UTC time.

        Per FR-047 to FR-052, all orchestrator events must include the required
        fields. Additional fields are event-specific (e.g., duration_ms, intent,
        tool_name, etc.).

        Args:
            event_type: Event type identifier (e.g., "state_transition", "tool_call",
                       "classification_result"). Used to filter and categorize events.
            state_name: Name of the state that emitted this event (e.g., "classify",
                       "route", "act", "escalate", "respond").
            correlation_id: Unique identifier for tracing a single request across
                           all states (per FR-051). Same ID used for all events
                           in a single conversation turn.
            level: Log level severity. One of "info" (normal operation), "warn"
                  (non-fatal issues), or "error" (failures). Defaults to "info".
            **kwargs: Additional event-specific fields. Common examples:
                     - from_state, to_state, decision_reason, duration_ms (state transitions)
                     - tool_name, success, input, output_summary (tool calls)
                     - intent, confidence, detected_emotion (classification)

        Returns:
            None. The event is printed to stdout.

        Raises:
            None. If JSON serialization fails, the error is caught and a fallback
            error event is printed instead.

        Example:
            logger.log_event(
                event_type="state_transition",
                state_name="classify",
                correlation_id="uuid-abc",
                level="info",
                from_state="classify",
                to_state="route",
                duration_ms=120
            )
        """
        # Build the event dictionary with required fields
        event: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "event_type": event_type,
            "state_name": state_name,
            "correlation_id": correlation_id,
            "level": level,
        }

        # Add any additional event-specific fields
        event.update(kwargs)

        try:
            # Emit as single-line JSON to stdout
            print(json.dumps(event), flush=True)
        except (TypeError, ValueError) as e:
            # Fallback: if kwargs contain non-serializable objects, emit error event
            fallback_event = {
                "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "event_type": "log_serialization_error",
                "state_name": state_name,
                "correlation_id": correlation_id,
                "level": "error",
                "error": str(e),
                "original_event_type": event_type,
            }
            print(json.dumps(fallback_event), flush=True)


# Convenience functions for common event types


def log_state_transition(
    logger: StructuredLogger,
    from_state: str,
    to_state: str,
    correlation_id: str,
    duration_ms: int,
    decision_reason: str = "",
) -> None:
    """Log a state transition event.

    Convenience function for logging transitions between orchestrator states.
    Per FR-047, state transitions must be logged with from/to states, decision
    reason, timestamp, session_id, and duration.

    Args:
        logger: StructuredLogger instance to use for logging.
        from_state: Name of the state being transitioned from (e.g., "classify").
        to_state: Name of the state being transitioned to (e.g., "route").
        correlation_id: Request correlation ID for tracing.
        duration_ms: Time spent in the from_state, in milliseconds.
        decision_reason: Optional explanation of why this transition occurred
                        (e.g., "intent=billing, confidence=0.92").

    Returns:
        None. Event is emitted to stdout.

    Example:
        logger = StructuredLogger()
        log_state_transition(
            logger=logger,
            from_state="classify",
            to_state="route",
            correlation_id="req-abc",
            duration_ms=340,
            decision_reason="intent=billing, confidence=0.92"
        )
    """
    logger.log_event(
        event_type="state_transition",
        state_name=from_state,
        correlation_id=correlation_id,
        level="info",
        from_state=from_state,
        to_state=to_state,
        duration_ms=duration_ms,
        decision_reason=decision_reason,
    )


def log_tool_call(
    logger: StructuredLogger,
    tool_name: str,
    state_name: str,
    correlation_id: str,
    success: bool,
    duration_ms: int,
    input_summary: str = "",
    output_summary: str = "",
) -> None:
    """Log a tool call event.

    Convenience function for logging tool invocations from the Act state.
    Per FR-048, tool calls must be logged with tool name, input, output summary,
    success flag, duration, and timestamp.

    Args:
        logger: StructuredLogger instance to use for logging.
        tool_name: Name of the tool function called (e.g., "get_billing_info").
        state_name: State that called the tool (typically "act").
        correlation_id: Request correlation ID for tracing.
        success: True if tool call succeeded, False otherwise.
        duration_ms: Time spent executing the tool, in milliseconds.
        input_summary: Optional summary of tool input (for observability).
        output_summary: Optional summary of tool output (for observability).

    Returns:
        None. Event is emitted to stdout.

    Example:
        logger = StructuredLogger()
        log_tool_call(
            logger=logger,
            tool_name="get_billing_info",
            state_name="act",
            correlation_id="req-abc",
            success=True,
            duration_ms=450,
            input_summary="account_id=ACC-10001, months=3",
            output_summary="Retrieved 3 bills"
        )
    """
    logger.log_event(
        event_type="tool_call",
        state_name=state_name,
        correlation_id=correlation_id,
        level="info" if success else "warn",
        tool_name=tool_name,
        success=success,
        duration_ms=duration_ms,
        input_summary=input_summary,
        output_summary=output_summary,
    )


def log_classification_result(
    logger: StructuredLogger,
    correlation_id: str,
    intent: str,
    confidence: float,
    detected_emotion: str = "",
    off_topic: bool = False,
    message_length: int = 0,
) -> None:
    """Log a classification result event.

    Convenience function for logging intent classification results from the
    Classify state. Per FR-049, classification results must be logged with
    intent, confidence, detected emotion, off_topic flag, message length,
    and timestamp.

    Args:
        logger: StructuredLogger instance to use for logging.
        correlation_id: Request correlation ID for tracing.
        intent: Classified intent (e.g., "billing", "technical", "account").
        confidence: Classification confidence score (0.0 to 1.0).
        detected_emotion: Optional detected customer emotion (e.g., "neutral",
                         "frustrated", "angry").
        off_topic: True if query is off-topic (not telecom-related).
        message_length: Length of the customer message in characters.

    Returns:
        None. Event is emitted to stdout.

    Example:
        logger = StructuredLogger()
        log_classification_result(
            logger=logger,
            correlation_id="req-abc",
            intent="billing",
            confidence=0.92,
            detected_emotion="neutral",
            off_topic=False,
            message_length=27
        )
    """
    logger.log_event(
        event_type="classification_result",
        state_name="classify",
        correlation_id=correlation_id,
        level="info",
        intent=intent,
        confidence=confidence,
        detected_emotion=detected_emotion,
        off_topic=off_topic,
        message_length=message_length,
    )
