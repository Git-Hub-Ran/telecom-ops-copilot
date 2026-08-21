"""ClassifyState implementation for intent classification.

Invokes the ClassifierAgent (Foundry) to classify customer intent, confidence,
emotion, and off-topic flag from the current message and conversation history.

Per FR-008, ClassifyState reads session_state and customer_message from context.
Per FR-009, ClassifyOutput includes intent, confidence, detected_emotion, off_topic.
Per FR-042 to FR-046, errors return a safe fallback (intent="unknown", confidence=0.0)
rather than propagating exceptions.
"""

import asyncio
import json

from azure.ai.agents.models import MessageRole

from src.orchestrator.agents.factory import AgentFactory
from src.orchestrator.models import ClassifyOutput, ConversationTurn, StateContext
from src.orchestrator.observability.structured import (
    StructuredLogger,
    log_classification_result,
)
from src.orchestrator.states.base import BaseState


def _fallback_output() -> ClassifyOutput:
    """Return a safe fallback ClassifyOutput for error cases.

    Per the classify contract, unknown intent triggers escalation via RouteState,
    which is safer than propagating the error to the caller.
    """
    return ClassifyOutput(
        intent="unknown",
        confidence=0.0,
        detected_emotion=None,
        off_topic=False,
    )


def _build_prompt_content(customer_message: str, history: list[ConversationTurn]) -> str:
    """Build the full prompt content to send to the classifier agent.

    Formats the conversation history (if any) followed by the current message.
    The classifier agent uses history to resolve ambiguous pronouns and references.

    Args:
        customer_message: The current customer message to classify.
        history: Up to 5 prior conversation turns from SessionState.

    Returns:
        Formatted string combining history and the current message.
    """
    lines: list[str] = []
    if history:
        lines.append("Conversation history (most recent last):")
        for turn in history:
            lines.append(f"  [{turn.role}]: {turn.content}")
        lines.append("")
    lines.append(f"Current customer message: {customer_message}")
    return "\n".join(lines)



class ClassifyState(BaseState[StateContext, ClassifyOutput]):
    """Foundry-backed intent classification state.

    Sends the customer message and conversation history to the ClassifierAgent,
    parses the JSON response into ClassifyOutput, and handles errors with a
    safe fallback (intent="unknown", confidence=0.0).

    On error (timeout, malformed JSON, Pydantic validation failure), logs the
    error and returns the fallback so RouteState can escalate safely.

    Agent invocation pattern:
    1. Get (or create) the classifier agent via AgentFactory
    2. Build prompt content with conversation history
    3. Create a Foundry thread, post the message, run the agent
    4. Extract JSON from the assistant response
    5. Validate JSON into ClassifyOutput via Pydantic
    """

    def __init__(self, agent_factory: AgentFactory) -> None:
        """Initialize with an agent factory.

        Args:
            agent_factory: AgentFactory for retrieving the classifier agent
                          and its underlying AgentsClient.
        """
        self.factory = agent_factory
        self._logger = StructuredLogger()

    async def run(self, context: StateContext) -> ClassifyOutput:
        """Execute intent classification against the ClassifierAgent.

        Builds a prompt from customer_message and conversation history, invokes
        the classifier agent in a thread pool (non-blocking), and parses the
        JSON response. Returns the fallback on any failure.

        Args:
            context: StateContext with session_state and customer_message populated.

        Returns:
            ClassifyOutput with intent, confidence, detected_emotion, and off_topic.

        Raises:
            ValueError: If customer_message is empty.
        """
        if not context.customer_message:
            raise ValueError(
                "ClassifyState requires a non-empty customer_message in context."
            )

        correlation_id = context.session_state.correlation_id
        history = context.session_state.conversation_history
        content = _build_prompt_content(context.customer_message, history)
        agent = self.factory.get_classifier_agent()

        try:
            raw_json = await asyncio.to_thread(self._invoke_agent, agent.id, content)
            raw_json = raw_json.strip()
            if raw_json.startswith("```"):
                raw_json = raw_json.split("\n", 1)[1]
                raw_json = raw_json.rsplit("```", 1)[0].strip()
            result = ClassifyOutput.model_validate_json(raw_json)
        except Exception as exc:
            self._logger.log_event(
                event_type="classification_error",
                state_name="classify",
                correlation_id=correlation_id,
                level="error",
                error=str(exc),
                error_type=type(exc).__name__,
            )
            return _fallback_output()

        log_classification_result(
            logger=self._logger,
            correlation_id=correlation_id,
            intent=result.intent,
            confidence=result.confidence,
            detected_emotion=result.detected_emotion or "",
            off_topic=result.off_topic,
            message_length=len(context.customer_message),
        )
        return result

    def _invoke_agent(self, agent_id: str, content: str) -> str:
        """Invoke the classifier agent synchronously and return JSON response text.

        Creates a Foundry thread, posts the user message, runs the agent to
        completion (blocking poll), then extracts the assistant's text response.

        This method is designed to run inside asyncio.to_thread so it does not
        block the event loop during the agent polling wait.

        Args:
            agent_id: Foundry agent ID for the classifier agent.
            content: Formatted prompt with history and current customer message.

        Returns:
            Raw JSON string from the classifier agent's response.

        Raises:
            RuntimeError: If no assistant text response is found.
            azure.core.exceptions.HttpResponseError: If a Foundry API call fails.
        """
        client = self.factory.agents_client
        thread = client.threads.create()
        client.messages.create(thread_id=thread.id, role="user", content=content)
        client.runs.create_and_process(thread_id=thread.id, agent_id=agent_id)
        msg = client.messages.get_last_message_text_by_role(
            thread_id=thread.id, role=MessageRole.AGENT
        )
        if msg is None:
            raise RuntimeError("No assistant text response found in thread messages.")
        return msg.text.value
