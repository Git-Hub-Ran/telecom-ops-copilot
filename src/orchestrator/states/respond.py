"""RespondState implementation for final customer-facing message generation.

Invokes RespondAgent for resolved, unresolved+escalated, and direct
escalation paths. Returns Python-assembled canned messages for
REFUSE_OFF_TOPIC and ASK_CLARIFYING_QUESTION without an agent call.

Per FR-045, if RespondAgent fails the state returns a hardcoded fallback
message with escalation_offered=True so the customer is never left with
a silent failure.

RespondState is the terminal state. There is no respond_output slot on
StateContext; the StateMachine returns RespondOutput directly to the caller.
"""

import asyncio
import json
from typing import Any

from azure.ai.agents.models import MessageRole

from src.orchestrator.agents.factory import AgentFactory
from src.orchestrator.models import RespondOutput, RoutingDecision, StateContext
from src.orchestrator.observability.structured import StructuredLogger
from src.orchestrator.states.base import BaseState

_REFUSE_MESSAGE = (
    "I can only assist with TelSano telecom service questions. "
    "Is there something else I can help you with?"
)

_CLARIFY_MESSAGE = (
    "Could you tell me a bit more about your issue so I can point you to the right place?"
)

_FALLBACK_MESSAGE = "I'm sorry, I encountered an issue. Let me connect you with support."

_BYPASS_DECISIONS = frozenset({
    RoutingDecision.REFUSE_OFF_TOPIC,
    RoutingDecision.ASK_CLARIFYING_QUESTION,
})


class RespondState(BaseState[StateContext, RespondOutput]):
    """Terminal state that generates the final customer-facing response.

    Handles four incoming state branches:
    - Resolved (act_output.resolution_status == "resolved"): invoke
      RespondAgent with act results and KB citations.
    - Unresolved + escalated (escalate_output populated, act_output
      populated): invoke RespondAgent with escalation context;
      escalation_offered=True.
    - Direct escalation (act_output is None, escalate_output populated):
      invoke RespondAgent; escalation_offered=True; tools_called=0.
    - Bypass (REFUSE_OFF_TOPIC or ASK_CLARIFYING_QUESTION): return
      Python-assembled canned message without invoking RespondAgent.

    On any RespondAgent failure, returns the FR-045 fallback message with
    escalation_offered=True in metadata.

    Does not mutate context. The StateMachine returns this state's
    RespondOutput directly to the caller.
    """

    def __init__(self, agent_factory: AgentFactory) -> None:
        """Initialize with an agent factory.

        Args:
            agent_factory: AgentFactory for retrieving the respond agent and
                          its underlying AgentsClient.
        """
        self.factory = agent_factory
        self._logger = StructuredLogger()

    async def run(self, context: StateContext) -> RespondOutput:
        """Generate the final customer-facing response.

        Returns a canned message immediately for REFUSE_OFF_TOPIC and
        ASK_CLARIFYING_QUESTION. For all other routing decisions, invokes
        RespondAgent and parses its JSON response. Returns the FR-045
        fallback on any agent failure.

        Args:
            context: StateContext with routing_decision, act_output,
                     escalate_output, and customer_message populated as
                     appropriate for the current flow.

        Returns:
            RespondOutput with message, citations, and metadata.
        """
        correlation_id = context.session_state.correlation_id
        decision = context.routing_decision

        if decision == RoutingDecision.REFUSE_OFF_TOPIC:
            return RespondOutput(
                message=_REFUSE_MESSAGE,
                citations=[],
                metadata={"escalation_offered": False},
            )

        if decision == RoutingDecision.ASK_CLARIFYING_QUESTION:
            return RespondOutput(
                message=_CLARIFY_MESSAGE,
                citations=[],
                metadata={"escalation_offered": False},
            )

        content = self._build_agent_prompt(context)

        raw_json = ""
        try:
            raw_json = await asyncio.to_thread(self._invoke_agent, content)
            data = json.loads(raw_json)
            return self._build_output(context, data)
        except Exception as exc:
            self._logger.log_event(
                event_type="respond_agent_error",
                state_name="respond",
                correlation_id=correlation_id,
                level="error",
                error=str(exc),
                error_type=type(exc).__name__,
                raw_response_snippet=raw_json[:200],
            )
            return RespondOutput(
                message=_FALLBACK_MESSAGE,
                citations=[],
                metadata={"escalation_offered": True},
            )

    def _build_agent_prompt(self, context: StateContext) -> str:
        """Build the structured text prompt sent to RespondAgent.

        Formats routing_decision, act_output fields, escalation flag, and
        the original customer_message into a single prompt string. Instructs
        the agent to return JSON with message, citations, and metadata.

        Args:
            context: StateContext with all fields relevant to the current
                     flow populated.

        Returns:
            Formatted prompt string for the RespondAgent user message.
        """
        lines: list[str] = ["Generate a customer-facing response for TelSano support.", ""]

        decision = context.routing_decision
        if decision is not None:
            lines.append(f"Routing decision: {decision.value}")

        act_output = context.act_output
        if act_output is not None and act_output.prepared_response:
            lines.append(
                "A pre-formatted response has been prepared. Use EXACTLY this text as your "
                f"message field, word for word, with no changes: {act_output.prepared_response}"
            )
        if act_output is not None:
            lines.append(f"Resolution status: {act_output.resolution_status}")
            if act_output.error_details:
                lines.append(f"Error details: {act_output.error_details}")
            if act_output.tool_results_json:
                lines.append("Tool result data (use this to answer the customer):")
                lines.append(act_output.tool_results_json)
            if act_output.kb_citations:
                lines.append("KB citations available:")
                for citation in act_output.kb_citations:
                    lines.append(
                        f"  - {citation.doc_id} / {citation.section}: {citation.relevance}"
                    )
                    if citation.text_content:
                        lines.append(f"  Content: {citation.text_content}")
        else:
            lines.append("Resolution status: not attempted")

        escalated = context.escalate_output is not None
        lines.append(f"Escalation to human agent: {'yes' if escalated else 'no'}")

        lines.append("")
        lines.append(f"Customer message: {context.customer_message}")

        lines.append("")
        lines.append(
            "Return JSON with exactly three fields: "
            '"message" (string, customer-facing response text), '
            '"citations" (list of KB doc_id strings, empty list if none used), '
            '"metadata" (dict, may include escalation_offered bool and other analytics).'
        )

        return "\n".join(lines)

    def _invoke_agent(self, content: str) -> str:
        """Invoke RespondAgent synchronously and return its JSON response text.

        Designed to run inside asyncio.to_thread. Uses the respond agent
        configured in AgentFactory with RESPOND_SYSTEM_PROMPT (FR-037 guard
        included).

        Args:
            content: Formatted prompt string from _build_agent_prompt.

        Returns:
            Raw JSON string from the respond agent response.

        Raises:
            RuntimeError: If no assistant text response is found in the thread.
            azure.core.exceptions.HttpResponseError: If a Foundry API call fails.
        """
        client = self.factory.agents_client
        agent = self.factory.get_respond_agent()
        thread = client.threads.create()
        client.messages.create(thread_id=thread.id, role="user", content=content)
        client.runs.create_and_process(thread_id=thread.id, agent_id=agent.id)
        msg = client.messages.get_last_message_text_by_role(
            thread_id=thread.id, role=MessageRole.AGENT
        )
        if msg is None:
            raise RuntimeError("No assistant text response found in respond agent thread.")
        text = msg.text.value.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1]
            text = text.rsplit("```", 1)[0].strip()
        return text

    def _build_output(self, context: StateContext, data: dict[str, Any]) -> RespondOutput:
        """Assemble RespondOutput from parsed agent response and context.

        Extracts message, citations, and metadata from the agent response dict,
        then merges computed metadata fields derived from context. Computed
        fields overwrite any agent-provided values for the same keys.

        Args:
            context: StateContext providing act_output and escalate_output
                     for metadata computation.
            data: Parsed JSON dict from the RespondAgent response, expected
                  to contain "message", "citations", and "metadata" keys.

        Returns:
            RespondOutput with message, citations list, and merged metadata.
        """
        message: str = data.get("message", _FALLBACK_MESSAGE)
        citations: list[str] = data.get("citations", [])
        metadata: dict[str, Any] = dict(data.get("metadata", {}))

        act_output = context.act_output
        escalate_output = context.escalate_output

        metadata["kb_docs_used"] = len(act_output.kb_citations) if act_output else 0
        metadata["tools_called"] = len(act_output.tools_called) if act_output else 0

        if act_output is not None and act_output.error_details is not None:
            metadata["error_code"] = act_output.error_details

        metadata["escalation_offered"] = (
            True if escalate_output is not None
            else metadata.get("escalation_offered", False)
        )

        return RespondOutput(message=message, citations=citations, metadata=metadata)
