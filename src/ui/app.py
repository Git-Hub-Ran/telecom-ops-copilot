"""Streamlit chat UI for the TelSano customer service orchestrator.

Provides a single-page chat interface that wires StateMachine into a
customer-facing conversational experience. The UI layer owns all
Streamlit state management and Pydantic serialization; the orchestrator
knows nothing about Streamlit.

Per FR-053, session state is stored in st.session_state under the key
"orchestrator_state" as a JSON-compatible dict.
Per FR-056, Pydantic model instances are never stored in st.session_state.
model_validate() is called before each process_turn call and model_dump()
is called after.
Per FR-057 and FR-058, UI events are lightweight dicts appended to
st.session_state["ui_events"] after each turn completes.
Per FR-059, st.session_state["current_state"] is updated at the start and
end of each turn for UI progress display.
"""

import asyncio
import re
from datetime import datetime, timezone
from uuid import uuid4

import streamlit as st

from src.config import get_config
from src.orchestrator.agents.factory import AgentFactory
from src.orchestrator.models.session import ConversationTurn, SessionState
from src.orchestrator.state_machine import StateMachine


# Any Markdown image: inline ![alt](url), full reference ![alt][ref], collapsed
# ![alt][], and shortcut ![alt]. The alt text is kept.
_MD_IMAGE = re.compile(r"!\[([^\]]*)\](?:\([^)]*\)|\[[^\]]*\])?")

# Reference definitions. These render as nothing on their own, but they are what
# makes ![alt][ref] resolve to a URL, so stripping images is incomplete without
# them. Removing these also breaks reference-style links, which degrade to plain
# text; inline links are untouched.
#
# The line must be a definition and nothing else: a destination, then at most a
# title. An earlier version ended in `.*$`, which swallowed any trailing prose
# and so deleted an ordinary sentence such as "[Note]: payment is due on the
# 15th." from a customer reply. Prose after the destination means the line is
# not a definition, and CommonMark renders it as the text it is.
_MD_REF_DEF = re.compile(
    r"(?m)^[ \t]*\[[^\]]+\]:[ \t]*"
    r"(?:<[^>\n]*>|\S+)"
    r"(?:[ \t]+(?:\"[^\"\n]*\"|'[^'\n]*'|\([^)\n]*\)))?"
    r"[ \t]*$\n?"
)


def _strip_images(text: str) -> str:
    """Collapse Markdown images to their alt text until none is left.

    One pass is not enough. Against a nested image the pattern consumes the
    inner brackets and can leave a live image behind: `![![x](in.png)](out.png)`
    becomes `![x](out.png)`, which still fetches. Each pass removes at least the
    `![` and `]` of one image, so the text strictly shortens and this ends.
    """
    while True:
        collapsed = _MD_IMAGE.sub(r"\1", text)
        if collapsed == text:
            return collapsed
        text = collapsed


def _render_agent_text(text: str) -> str:
    """Prepare agent output for Markdown rendering.

    Escapes $ so amounts are not parsed as LaTeX, and strips Markdown image
    syntax, which Streamlit renders as an <img> that fetches its URL on display.
    All four image forms are covered (inline, full reference, collapsed, and
    shortcut), nested to any depth, along with the reference definitions that
    resolve them. The alt text is kept so nothing silently disappears from the
    reply. Inline links and the rest of the Markdown are preserved: KB answers
    use bullets and bold.
    """
    stripped = _MD_REF_DEF.sub("", _strip_images(text))
    return stripped.replace("$", r"\$")


@st.cache_resource(show_spinner=False)
def get_state_machine(_version: int = 1) -> StateMachine:
    """Create and cache a StateMachine for the lifetime of the server process.

    Uses @st.cache_resource so the StateMachine (and the AgentFactory and
    Foundry SDK client it contains) is constructed once and reused across
    all reruns and all user sessions. Safe to share because StateMachine
    holds no per-turn mutable state.

    Increment _version to force cache invalidation when code changes require
    a fresh StateMachine instance.

    Returns:
        StateMachine instance backed by a real AgentFactory and Config.
    """
    return StateMachine(AgentFactory(get_config()))


def _init_session() -> None:
    """Initialize st.session_state keys on first load.

    Creates orchestrator_state (serialized SessionState dict), ui_events
    list, and current_state string if they do not already exist. Idempotent:
    safe to call on every rerun; only writes on the very first run.

    Returns:
        None. Mutates st.session_state in place.
    """
    if "orchestrator_state" not in st.session_state:
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        welcome = ConversationTurn(
            role="agent",
            content="Hello! I am TelSano's support assistant. How can I help you today?",
            timestamp=now,
        )
        session = SessionState(
            session_id=str(uuid4()),
            correlation_id=str(uuid4()),
            conversation_history=[welcome],
            started_at=now,
            last_updated=now,
        )
        st.session_state["orchestrator_state"] = session.model_dump()

    if "ui_events" not in st.session_state:
        st.session_state["ui_events"] = []

    if "current_state" not in st.session_state:
        st.session_state["current_state"] = "idle"


def _render_history() -> None:
    """Render conversation_history from the stored orchestrator_state dict.

    Reads the conversation_history list from st.session_state and renders
    each turn as a Streamlit chat message. Customer turns use the "user"
    role; agent turns use the "assistant" role.

    Returns:
        None. Renders Streamlit elements.
    """
    history = st.session_state["orchestrator_state"].get("conversation_history", [])
    for turn in history:
        role = "user" if turn["role"] == "customer" else "assistant"
        with st.chat_message(role):
            if turn["role"] == "agent":
                st.write(_render_agent_text(turn["content"]))
            else:
                st.text(turn["content"])


def _handle_input(user_message: str, machine: StateMachine) -> None:
    """Process one conversation turn and render the agent response.

    Renders the user message immediately, then deserializes SessionState
    (FR-056), calls process_turn inside a spinner, serializes the mutated
    session back to st.session_state (FR-056), appends a UI event dict
    (FR-057, FR-058), and renders the agent response with optional
    citations and escalation notice.

    Args:
        user_message: The text submitted by the customer via st.chat_input.
        machine: The cached StateMachine instance from get_state_machine().

    Returns:
        None. Mutates st.session_state and renders Streamlit elements.
    """
    with st.chat_message("user"):
        st.text(user_message)

    st.session_state["current_state"] = "processing"

    session = SessionState.model_validate(st.session_state["orchestrator_state"])

    with st.spinner("Processing..."):
        result = asyncio.run(machine.process_turn(user_message, session))

    st.session_state["orchestrator_state"] = session.model_dump()

    st.session_state["ui_events"].append({
        "type": "turn_complete",
        "escalation_offered": result.metadata.get("escalation_offered", False),
        "kb_docs_used": result.metadata.get("kb_docs_used", 0),
        "citations": result.citations,
    })

    st.session_state["current_state"] = "done"

    with st.chat_message("assistant"):
        st.write(_render_agent_text(result.message))

        if result.citations:
            with st.expander("Sources"):
                for citation in result.citations:
                    st.markdown(f"- {citation}")

        if result.metadata.get("escalation_offered"):
            st.info("A support specialist can assist you further with this.")


def main() -> None:
    """Entry point for the Streamlit application.

    Sets page config, renders the title and status caption, initializes
    session state, renders conversation history, and handles new input.

    Returns:
        None. Streamlit re-executes this function on every user interaction.
    """
    st.set_page_config(page_title="TelSano Support", layout="centered")
    st.title("TelSano Customer Support")
    st.caption(f"Status: {st.session_state.get('current_state', 'idle')}")

    _init_session()
    _render_history()

    if user_message := st.chat_input("Type your message..."):
        machine = get_state_machine(_version=2)
        _handle_input(user_message, machine)


main()
