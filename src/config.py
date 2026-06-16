"""Project configuration using Pydantic Settings.

This module provides a single, type-safe configuration interface for the entire
project. Configuration values are loaded from environment variables or a .env file.

Usage:
    from src.config import get_config

    # Access config values
    endpoint = get_config().AZURE_FOUNDRY_PROJECT_ENDPOINT
    model = get_config().CLASSIFIER_MODEL
"""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Project root directory (parent of src/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Config(BaseSettings):
    """Application configuration loaded from environment variables.

    Required environment variables:
        AZURE_FOUNDRY_PROJECT_ENDPOINT: Azure AI Foundry project endpoint URL
        AZURE_TENANT_ID: Azure tenant ID for DeviceCodeCredential authentication
        VECTOR_STORE_ID: Foundry vector store ID for KB file search

    Optional environment variables (have defaults):
        CLASSIFIER_MODEL: Model for classification (default: gpt-4o-mini)
        ACT_MODEL: Model for action execution (default: gpt-4o)
        ESCALATE_MODEL: Model for escalation (default: gpt-4o)
        RESPOND_MODEL: Model for response generation (default: gpt-4o)
        CLASSIFICATION_CONFIDENCE_THRESHOLD: Confidence threshold (default: 0.6)
        RETRY_BACKOFF_MS: Retry backoff in milliseconds (default: 250)
        MAX_CONVERSATION_TURNS: Max conversation turns in rolling window (default: 10)
    """

    # Azure AI Foundry authentication (DeviceCodeCredential)
    AZURE_FOUNDRY_PROJECT_ENDPOINT: str = Field(
        description="Azure AI Foundry project endpoint URL (includes project ID)"
    )
    AZURE_TENANT_ID: str = Field(
        description="Azure tenant ID for DeviceCodeCredential authentication"
    )

    # Foundry resources
    VECTOR_STORE_ID: str = Field(
        description="Foundry vector store ID for KB file search (used by ActAgent and RespondAgent)"
    )

    # Agent model assignments
    CLASSIFIER_MODEL: str = Field(
        default="gpt-4o-mini",
        description="Model for intent classification (fast, cheap)"
    )
    ACT_MODEL: str = Field(
        default="gpt-4o",
        description="Model for action execution (quality matters for tool use)"
    )
    ESCALATE_MODEL: str = Field(
        default="gpt-4o",
        description="Model for escalation summary generation"
    )
    RESPOND_MODEL: str = Field(
        default="gpt-4o",
        description="Model for customer-facing response generation"
    )

    # Thresholds and limits
    CLASSIFICATION_CONFIDENCE_THRESHOLD: float = Field(
        default=0.6,
        ge=0.0,
        le=1.0,
        description="Minimum confidence for classification (0.0 to 1.0)"
    )
    RETRY_BACKOFF_MS: int = Field(
        default=250,
        ge=0,
        description="Backoff time in milliseconds for retry logic"
    )
    MAX_CONVERSATION_TURNS: int = Field(
        default=10,
        ge=1,
        description="Maximum conversation turns in rolling window (per FR-055)"
    )

    # Data paths (computed, not from env)
    @property
    def MOCK_DATA_DIR(self) -> Path:
        """Absolute path to mock data directory."""
        return PROJECT_ROOT / "mock-data"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )


@lru_cache(maxsize=1)
def get_config() -> Config:
    """Return the singleton Config instance. Created on first call."""
    return Config()
