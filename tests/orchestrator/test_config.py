"""Tests for configuration loading using Pydantic Settings."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from src.config import Config, PROJECT_ROOT


class TestConfig:
    """Test suite for Config class and environment variable loading."""

    def test_config_loads_all_required_env_vars(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that Config loads all required environment variables."""
        # Set all required env vars
        monkeypatch.setenv("AZURE_FOUNDRY_PROJECT_ENDPOINT", "https://test.services.ai.azure.com/api/projects/test")
        monkeypatch.setenv("AZURE_TENANT_ID", "12345678-1234-1234-1234-123456789abc")
        monkeypatch.setenv("VECTOR_STORE_ID", "vs_TestVectorStoreId123")

        # Create config instance
        config = Config()

        # Verify all required fields are loaded
        assert config.AZURE_FOUNDRY_PROJECT_ENDPOINT == "https://test.services.ai.azure.com/api/projects/test"
        assert config.AZURE_TENANT_ID == "12345678-1234-1234-1234-123456789abc"
        assert config.VECTOR_STORE_ID == "vs_TestVectorStoreId123"

    def test_config_raises_validation_error_for_missing_required_var(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that Config raises ValidationError when required env var is missing."""
        # Set only 2 of 3 required vars (missing VECTOR_STORE_ID)
        monkeypatch.setenv("AZURE_FOUNDRY_PROJECT_ENDPOINT", "https://test.services.ai.azure.com/api/projects/test")
        monkeypatch.setenv("AZURE_TENANT_ID", "12345678-1234-1234-1234-123456789abc")
        # Explicitly unset VECTOR_STORE_ID if it exists
        monkeypatch.delenv("VECTOR_STORE_ID", raising=False)

        # Attempt to create config should raise ValidationError
        with pytest.raises(ValidationError) as exc_info:
            Config()

        # Verify error message mentions the missing field
        assert "VECTOR_STORE_ID" in str(exc_info.value)

    def test_config_applies_defaults_for_optional_fields(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that Config uses default values for optional fields when not provided."""
        # Set only required vars, no optional ones
        monkeypatch.setenv("AZURE_FOUNDRY_PROJECT_ENDPOINT", "https://test.services.ai.azure.com/api/projects/test")
        monkeypatch.setenv("AZURE_TENANT_ID", "12345678-1234-1234-1234-123456789abc")
        monkeypatch.setenv("VECTOR_STORE_ID", "vs_TestVectorStoreId123")

        # Create config instance
        config = Config()

        # Verify defaults are applied (per config.py)
        assert config.CLASSIFIER_MODEL == "gpt-4o-mini"
        assert config.ACT_MODEL == "gpt-4o"
        assert config.ESCALATE_MODEL == "gpt-4o"
        assert config.RESPOND_MODEL == "gpt-4o"
        assert config.CLASSIFICATION_CONFIDENCE_THRESHOLD == 0.6
        assert config.RETRY_BACKOFF_MS == 250
        assert config.MAX_CONVERSATION_TURNS == 10

    def test_vector_store_id_loads_expected_value(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that VECTOR_STORE_ID loads the expected production value."""
        # Set required vars with the actual production vector store ID
        monkeypatch.setenv("AZURE_FOUNDRY_PROJECT_ENDPOINT", "https://test.services.ai.azure.com/api/projects/test")
        monkeypatch.setenv("AZURE_TENANT_ID", "12345678-1234-1234-1234-123456789abc")
        monkeypatch.setenv("VECTOR_STORE_ID", "vs_RUhIersucd9In0EAafTaorBG")

        # Create config instance
        config = Config()

        # Verify the production vector store ID is loaded
        assert config.VECTOR_STORE_ID == "vs_RUhIersucd9In0EAafTaorBG"
        # Verify format (starts with vs_)
        assert config.VECTOR_STORE_ID.startswith("vs_")

    def test_mock_data_dir_returns_absolute_path_object(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that MOCK_DATA_DIR returns an absolute Path object."""
        # Set required vars
        monkeypatch.setenv("AZURE_FOUNDRY_PROJECT_ENDPOINT", "https://test.services.ai.azure.com/api/projects/test")
        monkeypatch.setenv("AZURE_TENANT_ID", "12345678-1234-1234-1234-123456789abc")
        monkeypatch.setenv("VECTOR_STORE_ID", "vs_TestVectorStoreId123")

        # Create config instance
        config = Config()

        # Access MOCK_DATA_DIR property
        mock_data_dir = config.MOCK_DATA_DIR

        # Verify it's a Path object
        assert isinstance(mock_data_dir, Path)
        # Verify it's absolute
        assert mock_data_dir.is_absolute()
        # Verify it points to PROJECT_ROOT / "mock-data"
        assert mock_data_dir == PROJECT_ROOT / "mock-data"
        # Verify the path string ends with "mock-data"
        assert str(mock_data_dir).endswith("mock-data")
