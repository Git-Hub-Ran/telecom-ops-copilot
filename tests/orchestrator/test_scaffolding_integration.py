"""Integration tests for Phase 2.1 scaffolding components.

Verifies that all scaffolding pieces work together: config, BaseState, and
structured logging.
"""

import json
from io import StringIO
from unittest.mock import patch

import pytest

from src.config import Config
from src.orchestrator.observability.structured import StructuredLogger
from src.orchestrator.states.base import BaseState


class TestScaffoldingIntegration:
    """Integration tests for scaffolding components."""

    def test_import_config_from_src_config_works(self) -> None:
        """Test that importing get_config from src.config works."""
        # This test verifies the import itself works
        from src.config import get_config

        # Verify get_config is callable
        assert callable(get_config)

    def test_import_basestate_from_orchestrator_states_base_works(self) -> None:
        """Test that importing BaseState from src.orchestrator.states.base works."""
        from src.orchestrator.states.base import BaseState as ImportedBaseState

        # Verify it's the abstract base class
        assert ImportedBaseState.__name__ == "BaseState"

    def test_import_structured_logging_works(self) -> None:
        """Test that importing structured logging from observability.structured works."""
        from src.orchestrator.observability.structured import (
            StructuredLogger as ImportedLogger,
        )
        from src.orchestrator.observability.structured import (
            log_classification_result,
            log_state_transition,
            log_tool_call,
        )

        # Verify imports work
        assert ImportedLogger.__name__ == "StructuredLogger"
        assert callable(log_state_transition)
        assert callable(log_tool_call)
        assert callable(log_classification_result)

    def test_concrete_state_can_access_config(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that concrete state subclass can access config."""
        # Set required env vars
        monkeypatch.setenv("AZURE_FOUNDRY_PROJECT_ENDPOINT", "https://test.services.ai.azure.com/api/projects/test")
        monkeypatch.setenv("AZURE_TENANT_ID", "12345678-1234-1234-1234-123456789abc")
        monkeypatch.setenv("VECTOR_STORE_ID", "vs_TestVectorStoreId")

        # Create a config instance
        test_config = Config()

        # Define a concrete state that accesses config
        class TestState(BaseState[dict, dict]):
            def __init__(self, config: Config):
                self.config = config

            async def run(self, context: dict) -> dict:
                # Access config values
                return {
                    "endpoint": self.config.AZURE_FOUNDRY_PROJECT_ENDPOINT,
                    "model": self.config.CLASSIFIER_MODEL,
                }

        # Instantiate state with config
        state = TestState(test_config)

        # Verify state can access config
        assert state.config.AZURE_FOUNDRY_PROJECT_ENDPOINT == "https://test.services.ai.azure.com/api/projects/test"
        assert state.config.CLASSIFIER_MODEL == "gpt-4o-mini"

    def test_log_event_with_correlation_id_in_json_output(self) -> None:
        """Test that logging event with correlation_id includes it in JSON output."""
        logger = StructuredLogger()

        test_correlation_id = "integration-test-corr-id-123"

        # Capture stdout
        with patch("sys.stdout", new=StringIO()) as fake_stdout:
            logger.log_event(
                event_type="integration_test",
                state_name="test_integration",
                correlation_id=test_correlation_id,
                level="info",
                test_field="test_value",
            )

            output = fake_stdout.getvalue().strip()

        # Parse JSON output
        event = json.loads(output)

        # Verify correlation_id is in output
        assert event["correlation_id"] == test_correlation_id
        assert event["event_type"] == "integration_test"
        assert event["test_field"] == "test_value"
