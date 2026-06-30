"""Foundry agent factory for creating and retrieving agents by name.

This module implements the AgentFactory class, which provides get-or-create
semantics for the 4 Foundry agents used by the state machine. The factory
ensures idempotent agent creation: running the application multiple times
does not create duplicate agents.

Get-or-create pattern:
1. List all agents in the Foundry project (up to 100)
2. Search for an agent with the target name
3. If found, return the existing agent
4. If not found, create a new agent with the current system prompt and model

This approach provides zero-setup operation: the first run auto-creates the
4 required agents, and subsequent runs retrieve them by name. No manual
agent ID configuration is needed.

Agent names are stable constants defined in this module (e.g., "classifier-agent").
Changing a prompt requires manually deleting the agent in Foundry and re-running
the application to create a fresh agent with the updated prompt.

Per FR-030, agents are initialized at application startup (via this factory)
and reused across all customer conversation turns. Each agent is stateless;
conversation state is managed via thread and run objects.
"""

from azure.ai.agents import AgentsClient
from azure.ai.agents.models import Agent, FileSearchTool, ToolDefinition, ToolResources
from azure.identity import DeviceCodeCredential

from src.config import Config
from src.orchestrator.agents.prompts import (
    ACT_SYSTEM_PROMPT,
    CLASSIFIER_SYSTEM_PROMPT,
    ESCALATE_SYSTEM_PROMPT,
    RESPOND_SYSTEM_PROMPT,
)

# Agent name constants (stable identifiers for get-or-create lookups)
CLASSIFIER_AGENT_NAME = "classifier-agent"
ACT_AGENT_NAME = "act-agent"
ESCALATE_AGENT_NAME = "escalate-agent"
RESPOND_AGENT_NAME = "respond-agent"


class AgentFactory:
    """Factory for creating and retrieving Foundry agents by name.

    This factory implements idempotent agent creation using get-or-create semantics.
    Each agent has a stable name (e.g., "classifier-agent") and is created on first
    run, then retrieved by name on subsequent runs.

    The factory uses DeviceCodeCredential for authentication, which prompts the user
    to sign in via a device code flow. This works across all environments (local dev,
    Colab, Codespaces, etc.) and gives the user explicit control over which Azure
    account to use.

    Usage:
        config = get_config()
        factory = AgentFactory(config)
        classifier = factory.get_classifier_agent()
        # First run: creates "classifier-agent" in Foundry
        # Subsequent runs: retrieves existing "classifier-agent"

    Attributes:
        config: OrchestratorConfig instance with Azure endpoint and tenant ID
        agents_client: Authenticated AgentsClient for Foundry API calls
    """

    def __init__(self, config: Config) -> None:
        """Initialize the factory with Foundry client authentication.

        Creates a DeviceCodeCredential using the tenant ID from config, then
        builds an AgentsClient authenticated to the Foundry project endpoint.
        The device code flow will prompt the user to sign in on first use.

        Args:
            config: OrchestratorConfig instance (must have AZURE_FOUNDRY_PROJECT_ENDPOINT
                   and AZURE_TENANT_ID set)

        Raises:
            azure.core.exceptions.ClientAuthenticationError: If device code flow fails
                or credentials are invalid
            azure.core.exceptions.HttpResponseError: If the Foundry endpoint is invalid
                or unreachable
        """
        self.config = config

        # Create device code credential for interactive authentication
        credential = DeviceCodeCredential(tenant_id=config.AZURE_TENANT_ID)

        # Build authenticated Foundry client
        self.agents_client = AgentsClient(
            endpoint=config.AZURE_FOUNDRY_PROJECT_ENDPOINT, credential=credential
        )

    def get_classifier_agent(self) -> Agent:
        """Get or create the classifier agent.

        Returns the "classifier-agent" from Foundry. If the agent does not exist,
        creates it with CLASSIFIER_SYSTEM_PROMPT and the configured model.

        Returns:
            Agent object for intent classification (gpt-4o-mini by default)

        Raises:
            azure.core.exceptions.HttpResponseError: If Foundry API call fails
        """
        return self._get_or_create_agent(
            name=CLASSIFIER_AGENT_NAME,
            model=self.config.CLASSIFIER_MODEL,
            instructions=CLASSIFIER_SYSTEM_PROMPT,
        )

    def get_act_agent(self) -> Agent:
        """Get or create the act agent.

        Returns the "act-agent" from Foundry. If the agent does not exist,
        creates it with ACT_SYSTEM_PROMPT, the configured model, and
        file_search enabled against Config.VECTOR_STORE_ID for KB retrieval.

        Returns:
            Agent object for tool-based action execution (gpt-4o by default)

        Raises:
            azure.core.exceptions.HttpResponseError: If Foundry API call fails
        """
        file_search = FileSearchTool(vector_store_ids=[self.config.VECTOR_STORE_ID])
        return self._get_or_create_agent(
            name=ACT_AGENT_NAME,
            model=self.config.ACT_MODEL,
            instructions=ACT_SYSTEM_PROMPT,
            tools=file_search.definitions,
            tool_resources=file_search.resources,
        )

    def get_escalate_agent(self) -> Agent:
        """Get or create the escalate agent.

        Returns the "escalate-agent" from Foundry. If the agent does not exist,
        creates it with ESCALATE_SYSTEM_PROMPT and the configured model.

        Returns:
            Agent object for escalation payload generation (gpt-4o by default)

        Raises:
            azure.core.exceptions.HttpResponseError: If Foundry API call fails
        """
        return self._get_or_create_agent(
            name=ESCALATE_AGENT_NAME,
            model=self.config.ESCALATE_MODEL,
            instructions=ESCALATE_SYSTEM_PROMPT,
        )

    def get_respond_agent(self) -> Agent:
        """Get or create the respond agent.

        Returns the "respond-agent" from Foundry. If the agent does not exist,
        creates it with RESPOND_SYSTEM_PROMPT and the configured model.

        Returns:
            Agent object for customer-facing response generation (gpt-4o by default)

        Raises:
            azure.core.exceptions.HttpResponseError: If Foundry API call fails
        """
        return self._get_or_create_agent(
            name=RESPOND_AGENT_NAME,
            model=self.config.RESPOND_MODEL,
            instructions=RESPOND_SYSTEM_PROMPT,
        )

    def _get_or_create_agent(
        self,
        name: str,
        model: str,
        instructions: str,
        tools: list[ToolDefinition] | None = None,
        tool_resources: ToolResources | None = None,
    ) -> Agent:
        """Get an existing agent by name, or create if not found.

        This method implements idempotent agent creation:
        1. List all agents in the Foundry project (up to 100 agents)
        2. Search for an agent with the target name
        3. If found, return the existing agent
        4. If not found, create a new agent and return it

        The limit of 100 agents is a defensive upper bound. For this project
        (4 agents total), pagination is not needed, but the limit prevents
        unbounded API calls if the Foundry project contains many agents.

        Args:
            name: Agent name to search for (e.g., "classifier-agent")
            model: Model deployment name (e.g., "gpt-4o-mini")
            instructions: System prompt for the agent
            tools: Optional tool definitions to register on the agent (e.g.,
                  file_search). None for agents that don't need tools.
            tool_resources: Optional tool resources (e.g., vector store IDs
                           for file_search). Must be paired with tools.

        Returns:
            Agent object (either existing or newly created)

        Raises:
            azure.core.exceptions.HttpResponseError: If Foundry API call fails
                (list or create)
        """
        # List all agents, up to 100 (defensive limit for pagination)
        agents = self.agents_client.list_agents(limit=100)

        # Search for existing agent by name
        for agent in agents:
            if agent.name == name:
                return agent

        # Agent not found, create new agent
        return self.agents_client.create_agent(
            model=model,
            name=name,
            instructions=instructions,
            tools=tools,
            tool_resources=tool_resources,
        )
