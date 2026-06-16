# Research: State Machine Orchestrator Technical Decisions

**Feature**: State Machine Orchestrator  
**Date**: 2026-06-10  
**Status**: Complete

This document consolidates all technical decisions made during Phase 0 research for the state machine orchestrator implementation.

---

## 1. Microsoft Agent Framework Integration

**Decision**: Use `azure-ai-projects` SDK's Agent class as the orchestration layer.

**Rationale**:
- Per docs/PLAN.md section 3 and FR-005, we must use Microsoft Agent Framework for orchestration with Foundry SDK underneath
- The `azure-ai-projects` SDK provides the Agent abstraction that wraps Foundry's agent CRUD
- MAF handles agent lifecycle, thread management, and run execution
- State machine logic lives in pure Python (StateMachine class), MAF is invoked per-state

**Alternatives considered**:
- Pure Foundry SDK without MAF: Rejected per FR-005 requirement
- LangChain/LangGraph: Rejected, adds unnecessary abstraction over MAF
- Custom orchestration: Would duplicate MAF's thread/run management

**Implementation notes**:
- `StateMachine` class holds the 5-state flow logic
- Each state invokes a Foundry agent via MAF SDK
- RouteState is pure Python (no agent call)
- Agent responses are parsed into Pydantic models for type safety

---

## 2. Async vs Sync Orchestrator

**Decision**: Async orchestrator with `asyncio`.

**Rationale**:
- Foundry SDK agent calls are I/O-bound (HTTP to Azure)
- Tool calls are I/O-bound (Azure Functions)
- Async allows concurrent tool calls when Act state needs multiple tools
- Streamlit supports async handlers via `@st.cache_resource`
- p95 latency target (5s) requires efficient I/O

**Alternatives considered**:
- Sync orchestrator: Simpler but slower; agent calls would block sequentially
- Threading: More complex than async, no benefit for I/O-bound work

**Implementation notes**:
- All state `run()` methods are async
- `StateMachine.process_turn()` is async
- Streamlit UI uses `asyncio.run()` or async wrapper
- Tool functions remain sync (wrapped in `asyncio.to_thread()` if needed)

---

## 3. State Implementation Pattern

**Decision**: Each state is a class inheriting from `BaseState` with a `run()` method.

**Rationale**:
- Clear interface contract (input/output via Pydantic models)
- Easy to test in isolation (mock agent responses)
- Supports dependency injection (AgentFactory passed to constructor)
- Follows Single Responsibility Principle

**Alternatives considered**:
- Functions instead of classes: Harder to inject dependencies, less extensible
- State machine DSL/framework: Overkill for 5 states with clear linear flow

**Implementation notes**:
```python
class BaseState(ABC):
    @abstractmethod
    async def run(self, context: StateContext) -> StateOutput:
        pass

class ClassifyState(BaseState):
    def __init__(self, agent_factory: AgentFactory):
        self.agent = agent_factory.create_classifier_agent()
    
    async def run(self, context: StateContext) -> ClassifyOutput:
        # Invoke Foundry agent, parse JSON, return Pydantic model
        ...
```

---

## 4. Error Handling Strategy

**Decision**: Three-tier error handling: error code differentiation (FR-044), retry with backoff (FR-035), structured logging (FR-043).

**Rationale**:
- Tool errors have different severities (invalid_format is user error, data_unavailable is system error)
- Transient errors (HTTP 503) should retry once with 250ms backoff
- All errors log to structured JSON with correlation_id for tracing

**Alternatives considered**:
- Generic error handling: Too coarse, fails FR-044 requirement
- No retry logic: Fails FR-035, increases false escalations
- Application Insights SDK: FR-050 scope decision is stdout-only for now

**Implementation notes**:
- Tool wrapper checks `error_code` field in result
- `invalid_format` → return to Respond with clarification prompt, no escalation
- `not_found` → return to Respond with "not found" + offer escalation option
- Other errors after retry → escalate with error details
- All exceptions caught at state boundary, logged with stack trace

---

## 5. Configuration Management

**Decision**: Use `python-dotenv` for .env file, Pydantic Settings for validation.

**Rationale**:
- Existing project uses .env pattern (see .gitignore line 151)
- Pydantic Settings provides type-safe config with validation
- Azure deployment injects env vars, .env is local development only

**Alternatives considered**:
- ConfigParser: Less type-safe than Pydantic Settings
- Hardcoded values: Fails deployment flexibility requirement

**Configuration location**: Single project config at `src/config.py` (not `src/orchestrator/config.py`)

**Configuration schema**:
```python
# src/config.py
from pydantic_settings import BaseSettings
from pydantic import SecretStr

class Config(BaseSettings):
    # Azure AI Foundry
    FOUNDRY_PROJECT_ID: str
    FOUNDRY_ENDPOINT: str
    FOUNDRY_API_KEY: SecretStr
    
    # Agent model assignments
    CLASSIFIER_MODEL: str = "gpt-4o-mini"
    ACT_MODEL: str = "gpt-4o"
    ESCALATE_MODEL: str = "gpt-4o"
    RESPOND_MODEL: str = "gpt-4o"
    
    # Thresholds
    CLASSIFICATION_CONFIDENCE_THRESHOLD: float = 0.6
    RETRY_BACKOFF_MS: int = 250
    MAX_CONTEXT_TURNS: int = 5
    
    # Mock data paths (for existing tools)
    MOCK_DATA_DIR: str = "mock-data"
    
    class Config:
        env_file = ".env"
        case_sensitive = True

# Global config instance
config = Config()
```

**Usage in orchestrator**:
```python
from src.config import get_config

# In AgentFactory
self.classifier_model = get_config().CLASSIFIER_MODEL
```

---

## 6. Session State Schema

**Decision**: Pydantic model `SessionState` with conversation history (last 5 turns), extracted entities, correlation_id.

**Rationale**:
- FR-053: session state must persist account_id, detected_emotion, conversation history
- FR-054: conversation history includes last 5 turns (message + response pairs)
- Pydantic ensures type safety at state boundaries (FR-046)

**Alternatives considered**:
- Dict-based state: Less type-safe, fails FR-046
- Database-backed state: Overkill for session-scoped data, adds latency

**Schema**:
```python
class ConversationTurn(BaseModel):
    role: Literal["customer", "agent"]
    content: str
    timestamp: str  # ISO 8601

class SessionState(BaseModel):
    session_id: str
    correlation_id: str  # Unique per turn (FR-051)
    account_id: Optional[str] = None
    detected_emotion: Optional[str] = None
    conversation_history: list[ConversationTurn] = []  # Last 5 turns
    started_at: str
    last_updated: str
```

---

## 7. Foundry Agent Creation Strategy

**Decision**: AgentFactory singleton creates 4 agents at startup, reuses them across turns.

**Rationale**:
- Agent creation is expensive (Azure API call)
- Agents are stateless (thread and run are turn-scoped)
- Factory pattern allows easy mocking in tests

**Alternatives considered**:
- Create agent per turn: Wasteful, adds latency
- Single multi-purpose agent: Harder to tune prompts per state

**Implementation**:
```python
class AgentFactory:
    def __init__(self, config: OrchestratorConfig):
        self.config = config
        self._agents = {}
    
    def create_classifier_agent(self) -> Agent:
        if "classifier" not in self._agents:
            self._agents["classifier"] = Agent(
                model=self.config.CLASSIFIER_MODEL,
                instructions=CLASSIFIER_SYSTEM_PROMPT,
                # ... Foundry SDK config
            )
        return self._agents["classifier"]
    
    # Similar methods for act_agent, escalate_agent, respond_agent
```

---

## 8. Logging Format

**Decision**: Structured JSON to stdout, one event per line.

**Rationale**:
- FR-050: stdout logging for portability
- JSON allows ingestion by any log aggregator (Application Insights, CloudWatch, Datadog)
- One-line-per-event format works with `docker logs` and Azure monitoring

**Alternatives considered**:
- Python logging with JSON formatter: Works, chosen approach uses `logging.info()` + custom formatter
- Application Insights SDK direct integration: Out of scope per FR-050, deferred to later

**Event schema**:
```json
{
  "timestamp": "2026-06-10T14:25:00Z",
  "level": "INFO",
  "correlation_id": "uuid",
  "session_id": "SESS-123",
  "event_type": "state_transition",
  "from_state": "classify",
  "to_state": "route",
  "duration_ms": 340,
  "decision_reason": "intent=billing, confidence=0.92"
}
```

---

## Dependencies

All dependencies are compatible with existing project:

```toml
[project.dependencies]
# Existing
pydantic = "^2.0"
streamlit = "^1.28"
pytest = "^9.0"

# New (to be added)
azure-ai-projects = "^1.0"  # Microsoft Agent Framework + Foundry SDK
azure-identity = "^1.14"     # Azure authentication
python-dotenv = "^1.0"       # .env file loading
```

**Version compatibility**: All packages support Python 3.11 (existing project standard).

---

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Foundry SDK breaking changes | Medium | High | Pin `azure-ai-projects` version, test upgrades in isolation |
| Agent response parsing failures | Low | Medium | Catch-all error handling + fallback intent="unknown" |
| Async integration with Streamlit | Low | Medium | Use `asyncio.run()` wrapper, test with Streamlit testing framework |
| Configuration mistakes in production | Medium | High | Pydantic Settings validates at startup, fail fast on missing config |

---

## Open Questions

**None**. All clarifications resolved.

---

## Approval

**Research complete**: 2026-06-10  
**Approved by**: [Pending user review]  
**Ready for Phase 1**: Yes
