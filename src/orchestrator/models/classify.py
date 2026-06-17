"""Classification output models from ClassifyState.

This module defines the output schema for the intent classification state.
ClassifyState invokes the ClassifierAgent to determine customer intent,
confidence level, detected emotion, and whether the query is off-topic.

Per FR-009, ClassifyOutput must include: intent, confidence, detected_emotion,
and off_topic flag.
"""

from typing import Literal, Optional

from pydantic import BaseModel, Field


class ClassifyOutput(BaseModel):
    """Classification result from ClassifierAgent.

    This model represents the structured output from the Classify state after
    analyzing the customer message. The intent drives routing decisions, while
    confidence determines whether clarification is needed. The off_topic flag
    triggers refusal responses for non-telecom queries.

    Per FR-009, all four fields (intent, confidence, detected_emotion, off_topic)
    are required outputs from the classification stage.

    Example:
        {
            "intent": "billing",
            "confidence": 0.92,
            "detected_emotion": "neutral",
            "off_topic": false
        }
    """

    intent: Literal["billing", "technical", "account", "info", "escalate", "unknown"] = Field(
        description="Classified intent category (one of 6 valid values)"
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Classification confidence score between 0.0 and 1.0"
    )
    detected_emotion: Optional[str] = Field(
        default=None,
        description="Customer emotion if detected (e.g., neutral, mildly_frustrated, frustrated, angry)"
    )
    off_topic: bool = Field(
        default=False,
        description="True if query is off-topic (not telecom-related, per FR-018)"
    )
