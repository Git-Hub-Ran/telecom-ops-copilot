# Data Model: State Machine Orchestrator

**Feature**: State Machine Orchestrator  
**Date**: 2026-06-10  
**Source**: Spec FR-007 to FR-017

This document defines all Pydantic data contracts used by the state machine orchestrator.

---

## 1. Session State (FR-007, FR-053, FR-054)

**Purpose**: Persist multi-turn conversation context in Streamlit session_state.

```python
from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel, Field

class ConversationTurn(BaseModel):
    """A single turn in the conversation (customer message + agent response)."""
    role: Literal["customer", "agent"] = Field(description="Who sent the message")
    content: str = Field(description="Message content")
    timestamp: str = Field(description="ISO 8601 timestamp")

class SessionState(BaseModel):
    """Multi-turn session state persisted across conversation turns."""
    session_id: str = Field(description="Unique session identifier (SESS-*)")
    correlation_id: str = Field(description="Unique ID for current turn (for tracing)")
    account_id: Optional[str] = Field(None, description="Extracted customer account ID (ACC-*)")
    detected_emotion: Optional[str] = Field(None, description="Detected customer emotion")
    conversation_history: list[ConversationTurn] = Field(
        default_factory=list,
        description="Last 5 turns (customer + agent pairs)"
    )
    started_at: str = Field(description="Session start timestamp (ISO 8601)")
    last_updated: str = Field(description="Last activity timestamp (ISO 8601)")
```

**Validation rules**:
- `session_id` format: `SESS-*` (enforced by caller, not Pydantic)
- `conversation_history` max length: 5 turns (enforced by `StateMachine` when appending)
- `account_id` format if present: `ACC-\d{5}` (matches existing tool validation)

---

## 2. ClassifyOutput (FR-008, FR-009)

**Purpose**: Output from ClassifyState, input to RouteState.

```python
class ClassifyOutput(BaseModel):
    """Classification result from ClassifierAgent."""
    intent: Literal["billing", "technical", "account", "info", "escalate", "unknown"] = Field(
        description="Classified intent category"
    )
    confidence: float = Field(ge=0.0, le=1.0, description="Classification confidence score")
    detected_emotion: Optional[str] = Field(
        None,
        description="Customer emotion if detected (neutral, mildly_frustrated, frustrated, angry)"
    )
    off_topic: bool = Field(
        default=False,
        description="True if query is off-topic (not telecom-related)"
    )
```

**Validation rules**:
- `intent` must be one of 6 literal values
- `confidence` must be between 0.0 and 1.0 (enforced by Pydantic `ge`/`le`)
- `off_topic=True` typically pairs with `intent="escalate"` (but escalation is not automatic)

**Example**:
```json
{
  "intent": "billing",
  "confidence": 0.92,
  "detected_emotion": "neutral",
  "off_topic": false
}
```

---

## 3. RoutingDecision (FR-010, FR-011)

**Purpose**: Output from RouteState, determines next action.

```python
from enum import Enum

class RoutingDecision(str, Enum):
    """Routing decision enumeration."""
    BILLING_PATH = "billing_path"
    TECHNICAL_PATH = "technical_path"
    ACCOUNT_PATH = "account_path"
    INFO_PATH = "info_path"
    SKIP_TO_ESCALATE = "skip_to_escalate"
    ASK_CLARIFYING_QUESTION = "ask_clarifying_question"
    REFUSE_OFF_TOPIC = "refuse_off_topic"
```

**Routing logic** (implemented in `RouteState`):

| Condition | Decision |
|-----------|----------|
| `off_topic=True` | `REFUSE_OFF_TOPIC` |
| `confidence < 0.6` | `ASK_CLARIFYING_QUESTION` |
| `intent="escalate"` | `SKIP_TO_ESCALATE` |
| `intent="billing"` | `BILLING_PATH` |
| `intent="technical"` | `TECHNICAL_PATH` |
| `intent="account"` | `ACCOUNT_PATH` |
| `intent="info"` | `INFO_PATH` |
| `intent="unknown"` | `SKIP_TO_ESCALATE` |

---

## 4. ActOutput (FR-013, FR-014, FR-015)

**Purpose**: Output from ActState, contains tool results and KB citations.

```python
class ToolCallRecord(BaseModel):
    """Record of a single tool call made by ActAgent."""
    tool_name: str = Field(description="Tool function name (e.g., get_customer_account)")
    input: dict = Field(description="Tool input arguments as dict")
    result_summary: str = Field(description="Human-readable summary of tool result")
    called_at: str = Field(description="ISO 8601 timestamp of tool call")
    success: bool = Field(description="True if tool returned success=True")
    error_code: Optional[str] = Field(None, description="Error code if success=False")

class KBCitation(BaseModel):
    """Citation from knowledge base file search."""
    doc_id: str = Field(description="KB document ID (e.g., kb/policies/02-late-fees.md)")
    section: str = Field(description="Section title or heading")
    relevance: str = Field(description="Why this citation is relevant to the query")

class ActOutput(BaseModel):
    """Result from ActState after tool calls and KB retrieval."""
    resolution_status: Literal["resolved", "partial", "unresolved"] = Field(
        description="Whether the query was fully resolved"
    )
    tools_called: list[ToolCallRecord] = Field(
        default_factory=list,
        description="List of tools called (empty if info-only query)"
    )
    kb_citations: list[KBCitation] = Field(
        default_factory=list,
        description="KB documents retrieved and used"
    )
    error_details: Optional[str] = Field(
        None,
        description="Error details if resolution_status=unresolved"
    )
```

**Validation rules**:
- If `resolution_status="resolved"`, `error_details` must be None
- If `resolution_status="unresolved"`, `error_details` should be populated
- `tools_called` can be empty for info-only queries (FR-014)
- `kb_citations` can be empty if no KB retrieval occurred

**Example**:
```json
{
  "resolution_status": "resolved",
  "tools_called": [
    {
      "tool_name": "get_billing_info",
      "input": {"account_id": "ACC-10001", "months": 3},
      "result_summary": "Retrieved 3 months of billing history",
      "called_at": "2026-06-10T14:25:30Z",
      "success": true,
      "error_code": null
    }
  ],
  "kb_citations": [],
  "error_details": null
}
```

---

## 5. EscalationPayload (FR-016)

**Purpose**: Structured escalation ticket payload.

**Note**: This model is already implemented in `src/tools/escalation.py` with 24 passing tests. We reuse it directly.

**Import**:
```python
from src.tools.escalation import EscalationPayload
```

**Schema reference**: See `docs/ESCALATION_SCHEMA.md` for full details.

**Key fields**:
- `escalation_id`: Auto-generated (ESC-YYYYMMDD-HHMMSS-XXXX)
- `reason_code`: One of 5 literal values (tool_failure, out_of_scope, customer_frustration, unresolved_ambiguity, safety_trip)
- `priority`: One of 4 levels (low, medium, high, urgent)
- `customer`: CustomerInfo (account_id, phone, name, verified)
- `session`: SessionInfo (session_id, started_at, channel, language)
- `intent`: IntentInfo (primary, secondary, confidence)
- `summary`: Human-readable escalation summary
- `tools_called`: List of tools attempted
- `kb_citations`: List of KB docs referenced
- `customer_emotion`: EmotionInfo (sentiment, indicators)
- `transcript`: List of conversation turns
- `agent_attempts`: List of what the agent tried
- `suggested_next_action`: Recommendation for human agent

---

## 6. RespondOutput (FR-017)

**Purpose**: Final customer-facing response from RespondState.

```python
class RespondOutput(BaseModel):
    """Final response to customer from RespondAgent."""
    message: str = Field(description="Customer-facing response text")
    citations_included: bool = Field(
        description="True if response includes KB citations (required for policy answers)"
    )
    escalation_offered: bool = Field(
        default=False,
        description="True if response offers escalation as an option (not_found errors)"
    )
    metadata: dict = Field(
        default_factory=dict,
        description="Optional metadata (tools_called count, kb_docs_used count, etc.)"
    )
```

**Validation rules**:
- If query was info-related and KB was used, `citations_included` must be True (FR-032)
- If tool returned `error_code="not_found"`, `escalation_offered` should be True (FR-044)
- `message` must not be empty

**Example (with citations)**:
```json
{
  "message": "According to kb/policies/02-late-fees.md, the grace period for late payments is 5 business days. Your bill is due on June 15th, so the grace period extends to June 22nd.",
  "citations_included": true,
  "escalation_offered": false,
  "metadata": {
    "kb_docs_used": 1,
    "tools_called": 0
  }
}
```

**Example (not_found error)**:
```json
{
  "message": "I couldn't find an account with ID ACC-99999. Would you like me to connect you with a representative to verify your account information?",
  "citations_included": false,
  "escalation_offered": true,
  "metadata": {
    "error_code": "not_found"
  }
}
```

---

## 7. State Context (Internal, not in spec)

**Purpose**: Shared context passed between states.

```python
class StateContext(BaseModel):
    """Context passed to each state's run() method."""
    session_state: SessionState
    customer_message: str
    routing_decision: Optional[RoutingDecision] = None  # Set by RouteState
    classify_output: Optional[ClassifyOutput] = None     # Set by ClassifyState
    act_output: Optional[ActOutput] = None               # Set by ActState
```

**Usage**: `StateMachine` builds this context and passes it through the state chain.

---

## Model Dependency Graph

```
SessionState (root)
    │
    ├─> ClassifyOutput  (Classify state output)
    │       │
    │       └─> RoutingDecision  (Route state output)
    │               │
    │               ├─> ActOutput  (Act state output)
    │               │       │
    │               │       ├─> ToolCallRecord (list)
    │               │       └─> KBCitation (list)
    │               │
    │               └─> EscalationPayload  (Escalate state output, reused from src/tools/escalation.py)
    │
    └─> RespondOutput  (Respond state output)
```

---

## Validation Testing Requirements

Per FR-046, all Pydantic models must have unit tests covering:

1. **Valid input acceptance**: Model accepts well-formed data
2. **Invalid input rejection**: Model rejects malformed data with clear errors
3. **Enum validation**: Literal fields reject invalid enum values
4. **Range validation**: Numeric fields respect `ge`/`le` constraints
5. **Required field enforcement**: Missing required fields trigger ValidationError
6. **Optional field handling**: Optional fields can be None or omitted

**Test file locations**:
- `tests/orchestrator/test_models/test_session.py`
- `tests/orchestrator/test_models/test_classify.py`
- `tests/orchestrator/test_models/test_route.py`
- `tests/orchestrator/test_models/test_act.py`
- `tests/orchestrator/test_models/test_respond.py`

Escalation model tests already exist: `tests/test_tools_escalation.py` (24 passing tests).

---

## JSON Schema Export

For API documentation or external integrations, Pydantic models can export JSON schemas:

```python
print(ClassifyOutput.model_json_schema())
print(ActOutput.model_json_schema())
# ... etc
```

This allows automatic API documentation generation if needed.

---

**Data model complete**: 2026-06-10  
**Approved by**: [Pending user review]  
**Ready for contract generation**: Yes
