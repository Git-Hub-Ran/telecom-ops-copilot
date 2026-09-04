"""Unit tests for AgentFactory get-or-create logic."""

from unittest.mock import MagicMock, patch

import pytest
from azure.core.exceptions import HttpResponseError

from src.config import get_config
from src.orchestrator.agents.factory import (
    ACT_AGENT_NAME,
    CLASSIFIER_AGENT_NAME,
    ESCALATE_AGENT_NAME,
    RESPOND_AGENT_NAME,
    AgentFactory,
)
from src.orchestrator.agents.prompts import (
    ACT_SYSTEM_PROMPT,
    CLASSIFIER_SYSTEM_PROMPT,
    ESCALATE_SYSTEM_PROMPT,
    RESPOND_SYSTEM_PROMPT,
)


@pytest.fixture(autouse=True)
def setup_test_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Setup required environment variables for all tests.

    This fixture uses the same pattern as test_route.py to ensure Config
    can be instantiated with all required fields during testing.
    """
    # Set required Config env vars
    monkeypatch.setenv(
        "AZURE_FOUNDRY_PROJECT_ENDPOINT", "https://test.ai.azure.com/api/projects/test"
    )
    monkeypatch.setenv("AZURE_TENANT_ID", "12345678-1234-1234-1234-123456789abc")
    monkeypatch.setenv("VECTOR_STORE_ID", "vs_test")
    # Clear cache so new env vars take effect
    get_config.cache_clear()


class TestAgentFactoryInit:
    """Tests for AgentFactory initialization and credential setup."""

    @patch("src.orchestrator.agents.factory.AgentsClient")
    @patch("src.orchestrator.agents.factory.DeviceCodeCredential")
    def test_init_creates_devicecode_credential_with_tenant_id(
        self, mock_credential_class, mock_client_class
    ):
        """Verify __init__ creates DeviceCodeCredential with correct tenant_id."""
        config = get_config()
        factory = AgentFactory(config)

        # Assert DeviceCodeCredential was called with tenant_id from config
        mock_credential_class.assert_called_once_with(
            tenant_id="12345678-1234-1234-1234-123456789abc"
        )

    @patch("src.orchestrator.agents.factory.AgentsClient")
    @patch("src.orchestrator.agents.factory.DeviceCodeCredential")
    def test_init_creates_agents_client_with_correct_endpoint(
        self, mock_credential_class, mock_client_class
    ):
        """Verify __init__ creates AgentsClient with correct endpoint and credential."""
        mock_credential_instance = MagicMock()
        mock_credential_class.return_value = mock_credential_instance

        config = get_config()
        factory = AgentFactory(config)

        # Assert AgentsClient was called with endpoint and credential
        mock_client_class.assert_called_once_with(
            endpoint="https://test.ai.azure.com/api/projects/test",
            credential=mock_credential_instance,
        )


class TestAgentFactoryGetOrCreate:
    """Tests for get-or-create logic across all 4 agents."""

    @pytest.mark.parametrize(
        "agent_id,method_name,agent_name,model_attr,prompt",
        [
            (
                "classifier",
                "get_classifier_agent",
                CLASSIFIER_AGENT_NAME,
                "CLASSIFIER_MODEL",
                CLASSIFIER_SYSTEM_PROMPT,
            ),
            (
                "act",
                "get_act_agent",
                ACT_AGENT_NAME,
                "ACT_MODEL",
                ACT_SYSTEM_PROMPT,
            ),
            (
                "escalate",
                "get_escalate_agent",
                ESCALATE_AGENT_NAME,
                "ESCALATE_MODEL",
                ESCALATE_SYSTEM_PROMPT,
            ),
            (
                "respond",
                "get_respond_agent",
                RESPOND_AGENT_NAME,
                "RESPOND_MODEL",
                RESPOND_SYSTEM_PROMPT,
            ),
        ],
    )
    @patch("src.orchestrator.agents.factory.AgentsClient")
    @patch("src.orchestrator.agents.factory.DeviceCodeCredential")
    def test_get_agent_creates_new_when_not_found(
        self,
        mock_credential_class,
        mock_client_class,
        agent_id,
        method_name,
        agent_name,
        model_attr,
        prompt,
    ):
        """Verify get_<agent>_agent creates new agent when not found in list."""
        # Setup: list_agents returns empty iterator (agent not found)
        mock_client_instance = mock_client_class.return_value
        mock_client_instance.list_agents.return_value = iter([])

        # Setup: create_agent returns new agent
        fake_agent = MagicMock()
        fake_agent.name = agent_name
        mock_client_instance.create_agent.return_value = fake_agent

        config = get_config()
        factory = AgentFactory(config)

        # Call the method
        method = getattr(factory, method_name)
        agent = method()

        # Assert create_agent was called with correct arguments
        mock_client_instance.create_agent.assert_called_once()
        call_kwargs = mock_client_instance.create_agent.call_args.kwargs
        assert call_kwargs["name"] == agent_name
        assert call_kwargs["model"] == getattr(config, model_attr)
        assert call_kwargs["instructions"] is not None
        assert len(call_kwargs["instructions"]) > 0  # Non-empty string

        # Assert returned agent is the created one
        assert agent == fake_agent

    @pytest.mark.parametrize(
        "agent_id,method_name,agent_name,model_attr,prompt",
        [
            (
                "classifier",
                "get_classifier_agent",
                CLASSIFIER_AGENT_NAME,
                "CLASSIFIER_MODEL",
                CLASSIFIER_SYSTEM_PROMPT,
            ),
            (
                "act",
                "get_act_agent",
                ACT_AGENT_NAME,
                "ACT_MODEL",
                ACT_SYSTEM_PROMPT,
            ),
            (
                "escalate",
                "get_escalate_agent",
                ESCALATE_AGENT_NAME,
                "ESCALATE_MODEL",
                ESCALATE_SYSTEM_PROMPT,
            ),
            (
                "respond",
                "get_respond_agent",
                RESPOND_AGENT_NAME,
                "RESPOND_MODEL",
                RESPOND_SYSTEM_PROMPT,
            ),
        ],
    )
    @patch("src.orchestrator.agents.factory.AgentsClient")
    @patch("src.orchestrator.agents.factory.DeviceCodeCredential")
    def test_get_agent_returns_existing_when_found(
        self,
        mock_credential_class,
        mock_client_class,
        agent_id,
        method_name,
        agent_name,
        model_attr,
        prompt,
    ):
        """Verify get_<agent>_agent returns existing agent when found in list."""
        # Setup: list_agents returns existing agent
        existing_agent = MagicMock()
        existing_agent.name = agent_name

        mock_client_instance = mock_client_class.return_value
        mock_client_instance.list_agents.return_value = iter([existing_agent])

        config = get_config()
        factory = AgentFactory(config)

        # Call the method
        method = getattr(factory, method_name)
        agent = method()

        # Assert create_agent was NOT called
        mock_client_instance.create_agent.assert_not_called()

        # Assert returned agent is the existing one
        assert agent == existing_agent
        assert agent.name == agent_name


class TestAgentFactoryHelperLogic:
    """Tests for internal helper method logic."""

    @patch("src.orchestrator.agents.factory.AgentsClient")
    @patch("src.orchestrator.agents.factory.DeviceCodeCredential")
    def test_get_or_create_uses_list_agents_with_limit_100(
        self, mock_credential_class, mock_client_class
    ):
        """Verify _get_or_create_agent calls list_agents with limit=100."""
        # Setup: list_agents returns empty iterator
        mock_client_instance = mock_client_class.return_value
        mock_client_instance.list_agents.return_value = iter([])

        # Setup: create_agent returns new agent
        fake_agent = MagicMock()
        fake_agent.name = CLASSIFIER_AGENT_NAME
        mock_client_instance.create_agent.return_value = fake_agent

        config = get_config()
        factory = AgentFactory(config)

        # Call get_classifier_agent (which calls _get_or_create_agent)
        factory.get_classifier_agent()

        # Assert list_agents was called with limit=100
        mock_client_instance.list_agents.assert_called_once_with(limit=100)

    @patch("src.orchestrator.agents.factory.AgentsClient")
    @patch("src.orchestrator.agents.factory.DeviceCodeCredential")
    def test_get_or_create_creates_with_correct_model(
        self, mock_credential_class, mock_client_class
    ):
        """Verify each get method uses the correct model from config."""
        # Setup: list_agents returns empty iterator (agent not found)
        mock_client_instance = mock_client_class.return_value

        # Setup: create_agent returns new agent
        fake_agent = MagicMock()
        mock_client_instance.create_agent.return_value = fake_agent

        config = get_config()
        factory = AgentFactory(config)

        # Call get_classifier_agent
        mock_client_instance.list_agents.return_value = iter([])
        factory.get_classifier_agent()
        call_kwargs = mock_client_instance.create_agent.call_args.kwargs
        assert call_kwargs["model"] == "gpt-4o-mini"  # CLASSIFIER_MODEL default

        # Call get_act_agent
        mock_client_instance.list_agents.return_value = iter([])
        factory.get_act_agent()
        call_kwargs = mock_client_instance.create_agent.call_args.kwargs
        assert call_kwargs["model"] == "gpt-4o"  # ACT_MODEL default


class TestAgentFactoryErrorHandling:
    """Tests for error propagation."""

    @patch("src.orchestrator.agents.factory.AgentsClient")
    @patch("src.orchestrator.agents.factory.DeviceCodeCredential")
    def test_create_agent_failure_propagates(
        self, mock_credential_class, mock_client_class
    ):
        """Verify HttpResponseError from create_agent is propagated."""
        # Setup: list_agents returns empty iterator (triggers create path)
        mock_client_instance = mock_client_class.return_value
        mock_client_instance.list_agents.return_value = iter([])

        # Setup: create_agent raises HttpResponseError
        mock_client_instance.create_agent.side_effect = HttpResponseError(
            "Agent creation failed"
        )

        config = get_config()
        factory = AgentFactory(config)

        # Assert HttpResponseError is raised (factory does not swallow SDK errors)
        with pytest.raises(HttpResponseError):
            factory.get_classifier_agent()
