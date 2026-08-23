# Implementation Plan: State Machine Orchestrator

**Branch**: `Dev` (single working branch for this project) | **Date**: 2026-06-10 | **Spec**: [state-machine-orchestrator spec](./spec.md)

**Input**: Feature specification from `.specify/features/state-machine-orchestrator/spec.md`

## Summary

Build the state machine orchestrator that coordinates the 5-state flow (Classify → Route → Act → Escalate → Respond) using Microsoft Agent Framework with Azure AI Foundry SDK underneath. The orchestrator integrates 4 Foundry agents (ClassifierAgent, ActAgent, EscalateAgent, RespondAgent) with 5 existing Azure Functions tools, implements error handling by error code, supports multi-turn session state, and emits structured JSON logs for observability.

## Technical Context

**Language/Version**: Python 3.11 (existing project standard per pyproject.toml)

**Primary Dependencies**:
- `azure-ai-projects` (Azure AI Foundry SDK)
- `azure-identity` (authentication)
- `pydantic >= 2.0` (data contracts)
- `python-dotenv` (configuration)
- `streamlit` (existing UI framework for session state)

**Storage**: In-memory session state via Streamlit session_state (multi-turn context); no database required

**Testing**: pytest (existing framework, 112 passing tests in src/tools/)

**Target Platform**: Azure deployment (Function App + Streamlit on Hugging Face Spaces)

**Project Type**: Agent orchestration service with web UI

**Performance Goals**: 
- p95 response latency <= 5 seconds (per docs/EVAL.md)
- Support concurrent sessions (stateless orchestrator design)

**Constraints**:
- Must use Microsoft Agent Framework for orchestration (per docs/PLAN.md, FR-005)
- Must use Azure AI Foundry SDK for agent CRUD and file search (per FR-005)
- Must emit structured JSON logs to stdout (FR-050)
- Must handle tool errors by error_code (FR-044)

**Scale/Scope**: 
- 5 states
- 4 Foundry agents
- 5 tool integrations
- 7 Pydantic data contracts
- 100-query golden test set (per docs/EVAL.md)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Status**: Constitution file is template-only; no project-specific gates defined. Proceeding with standard software engineering principles:
- Clear separation of concerns (state, orchestrator, agents, tools)
- Type-safe contracts (Pydantic models per FR-007 to FR-017)
- Testability first (unit tests for states, integration tests for full flow)
- Observable by default (structured logging per FR-047 to FR-052)

## Project Structure

### Documentation (this feature)

```text
.specify/features/state-machine-orchestrator/
├── plan.md              # This file
├── research.md          # Phase 0 output (see below)
├── data-model.md        # Phase 1 output (Pydantic models)
├── quickstart.md        # Phase 1 output (validation guide)
├── contracts/           # Phase 1 output (state contracts)
└── spec.md              # Feature spec (input)
```

### Source Code (repository root)

```text
src/
├── config.py                     # Single project config (Pydantic Settings + .env)
│                                 # Contains: Foundry credentials, model assignments,
│                                 # thresholds, existing mock data paths
│
├── orchestrator/
│   ├── __init__.py
│   ├── state_machine.py         # Main StateMachine class (MAF orchestration)
│   ├── states/
│   │   ├── __init__.py
│   │   ├── base.py              # BaseState abstract class
│   │   ├── classify.py          # ClassifyState
│   │   ├── route.py             # RouteState (pure Python, no LLM)
│   │   ├── act.py               # ActState
│   │   ├── escalate.py          # EscalateState
│   │   └── respond.py           # RespondState
│   ├── models/
│   │   ├── __init__.py
│   │   ├── session.py           # SessionState, ConversationTurn
│   │   ├── classify.py          # ClassifyOutput
│   │   ├── route.py             # RoutingDecision enum
│   │   ├── act.py               # ActOutput, ToolCallRecord, KBCitation
│   │   ├── escalate.py          # (reuse existing EscalationPayload from src/tools/escalation.py)
│   │   └── respond.py           # RespondOutput
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── factory.py           # AgentFactory (creates Foundry agents)
│   │   └── prompts.py           # System prompts for 4 agents
│   └── logging/
│       ├── __init__.py
│       └── structured.py        # Structured JSON logging utilities
│
├── tools/                        # Existing (5 Azure Functions, already built)
│   ├── customer.py
│   ├── billing.py
│   ├── outage.py
│   ├── diagnostic.py
│   └── escalation.py
│
└── ui/
    └── streamlit_app.py          # Existing UI (integration point)

tests/
├── orchestrator/
│   ├── test_state_machine.py    # StateMachine orchestration tests
│   ├── test_states/
│   │   ├── test_classify.py
│   │   ├── test_route.py
│   │   ├── test_act.py
│   │   ├── test_escalate.py
│   │   └── test_respond.py
│   ├── test_models/             # Pydantic model validation tests
│   │   ├── test_session.py
│   │   ├── test_classify.py
│   │   ├── test_route.py
│   │   ├── test_act.py
│   │   └── test_respond.py
│   └── test_integration/
│       ├── test_happy_path.py   # User Story 1 (P1)
│       ├── test_tool_failure.py # User Story 2 (P1)
│       ├── test_multi_turn.py   # User Story 3 (P2)
│       └── test_escalation.py   # User Story 4 (P2)
│
└── test_tools_*.py               # Existing (112 passing tests, already built)
```

**Structure Decision**: Single-project layout. The orchestrator is a new top-level module (`src/orchestrator/`) that imports existing tools (`src/tools/`) and integrates with existing UI (`src/ui/`). No separate backend/frontend split needed; Streamlit UI and orchestrator run in the same Python process.

## Complexity Tracking

> No constitution violations requiring justification.

---

# Phase 0: Research & Technical Decisions

## Research Areas

### 1. Microsoft Agent Framework Integration

**Decision**: Use `azure-ai-projects` SDK's Agent class as the orchestration layer.

**Rationale**:
- Per docs/PLAN.md section 3 and FR-005, we must use Microsoft Agent Framework for orchestration with Foundry SDK underneath
- The `azure-ai-projects` SDK provides the Agent abstraction that wraps Foundry's agent CRUD
- MAF handles agent lifecycle, thread management, and run execution
- State machine logic lives in pure Python (StateMachine class), MAF is invoked per-state

**Implementation approach**:
- `StateMachine` class holds the 5-state flow logic
- Each state invokes a Foundry agent via MAF SDK
- RouteState is pure Python (no agent call)
- Agent responses are parsed into Pydantic models for type safety

**Alternatives considered**:
- Pure Foundry SDK without MAF: Rejected per FR-005 requirement
- LangChain/LangGraph: Rejected, adds unnecessary abstraction over MAF
- Custom orchestration: Would duplicate MAF's thread/run management

### 2. Async vs Sync Orchestrator

**Decision**: Async orchestrator with `asyncio`.

**Rationale**:
- Foundry SDK agent calls are I/O-bound (HTTP to Azure)
- Tool calls are I/O-bound (Azure Functions)
- Async allows concurrent tool calls when Act state needs multiple tools
- Streamlit supports async handlers via `@st.cache_resource`
- p95 latency target (5s) requires efficient I/O

**Implementation approach**:
- All state `run()` methods are async
- `StateMachine.process_turn()` is async
- Streamlit UI uses `asyncio.run()` or async wrapper
- Tool functions remain sync (wrapped in `asyncio.to_thread()` if needed)

**Alternatives considered**:
- Sync orchestrator: Simpler but slower; agent calls would block sequentially
- Threading: More complex than async, no benefit for I/O-bound work

### 3. State Implementation Pattern

**Decision**: Each state is a class inheriting from `BaseState` with a `run()` method.

**Rationale**:
- Clear interface contract (input/output via Pydantic models)
- Easy to test in isolation (mock agent responses)
- Supports dependency injection (AgentFactory passed to constructor)
- Follows Single Responsibility Principle

**Implementation approach**:
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

**Alternatives considered**:
- Functions instead of classes: Harder to inject dependencies, less extensible
- State machine DSL/framework: Overkill for 5 states with clear linear flow

### 4. Error Handling Strategy

**Decision**: Three-tier error handling: error code differentiation (FR-044), retry with backoff (FR-035), structured logging (FR-043).

**Rationale**:
- Tool errors have different severities (invalid_format is user error, data_unavailable is system error)
- Transient errors (HTTP 503) should retry once with 250ms backoff
- All errors log to structured JSON with correlation_id for tracing

**Implementation approach**:
- Tool wrapper checks `error_code` field in result
- `invalid_format` → return to Respond with clarification prompt, no escalation
- `not_found` → return to Respond with "not found" + offer escalation option
- Other errors after retry → escalate with error details
- All exceptions caught at state boundary, logged with stack trace

**Alternatives considered**:
- Generic error handling: Too coarse, fails FR-044 requirement
- No retry logic: Fails FR-035, increases false escalations
- Application Insights SDK: FR-050 scope decision is stdout-only for now

### 5. Configuration Management

**Decision**: Use `python-dotenv` for .env file, Pydantic Settings for validation.

**Rationale**:
- Existing project uses .env pattern (see the Environments section of .gitignore)
- Pydantic Settings provides type-safe config with validation
- Azure deployment injects env vars, .env is local development only

**Configuration needed**:
```python
class OrchestratorConfig(BaseSettings):
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
    
    class Config:
        env_file = ".env"
        case_sensitive = True
```

**Alternatives considered**:
- ConfigParser: Less type-safe than Pydantic Settings
- Hardcoded values: Fails deployment flexibility requirement

### 6. Session State Schema

**Decision**: Pydantic model `SessionState` with conversation history (last 5 turns), extracted entities, correlation_id.

**Rationale**:
- FR-053: session state must persist account_id, detected_emotion, conversation history
- FR-054: conversation history includes last 5 turns (message + response pairs)
- Pydantic ensures type safety at state boundaries (FR-046)

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

**Alternatives considered**:
- Dict-based state: Less type-safe, fails FR-046
- Database-backed state: Overkill for session-scoped data, adds latency

### 7. Foundry Agent Creation Strategy

**Decision**: AgentFactory singleton creates 4 agents at startup, reuses them across turns.

**Rationale**:
- Agent creation is expensive (Azure API call)
- Agents are stateless (thread and run are turn-scoped)
- Factory pattern allows easy mocking in tests

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

**Alternatives considered**:
- Create agent per turn: Wasteful, adds latency
- Single multi-purpose agent: Harder to tune prompts per state

### 8. Logging Format

**Decision**: Structured JSON to stdout, one event per line.

**Rationale**:
- FR-050: stdout logging for portability
- JSON allows ingestion by any log aggregator (Application Insights, CloudWatch, Datadog)
- One-line-per-event format works with `docker logs` and Azure monitoring

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

**Alternatives considered**:
- Python logging with JSON formatter: Works, chosen approach uses `logging.info()` + custom formatter
- Application Insights SDK direct integration: Out of scope per FR-050, deferred to later

---

# Phase 1: Design & Contracts

## Data Model

See `data-model.md` (generated separately, full Pydantic model definitions for all 7 contracts per FR-007 to FR-017).

## State Contracts

See `contracts/` directory:
- `classify-contract.md`: ClassifyState input/output
- `route-contract.md`: RouteState input/output
- `act-contract.md`: ActState input/output
- `escalate-contract.md`: EscalateState input/output
- `respond-contract.md`: RespondState input/output

Each contract defines:
- Input Pydantic model
- Output Pydantic model
- Error cases
- Validation rules
- Example JSON

## Quickstart Validation

See `quickstart.md` (generated separately, runnable end-to-end test scenarios).

---

# Phase 2: Implementation Order

## Phase 2.1: Scaffolding (Foundation)

**Goal**: Set up project structure, config, logging, base classes.

**Tasks**:
1. Create `src/orchestrator/` directory structure
2. Create `src/config.py` (single project config file using Pydantic Settings + .env loading)
   - Contains: Foundry credentials, model assignments, thresholds, mock data paths
   - All orchestrator components import from `src.config`
3. Implement `BaseState` abstract class in `src/orchestrator/states/base.py`
4. Implement structured JSON logging utility (`src/orchestrator/observability/structured.py`)
5. Write unit tests for config and logging

**Validation**: Config loads from .env, logging emits valid JSON to stdout.

**Estimated effort**: 1 day

---

## Phase 2.2: Pydantic Data Contracts

**Goal**: Define all 7 data models per spec FR-007 to FR-017.

**Tasks**:
1. Implement `SessionState` and `ConversationTurn` in `src/orchestrator/models/session.py`
2. Implement `ClassifyOutput` in `src/orchestrator/models/classify.py`
3. Implement `RoutingDecision` enum in `src/orchestrator/models/route.py`
4. Implement `ActOutput`, `ToolCallRecord`, `KBCitation` in `src/orchestrator/models/act.py`
5. Reuse `EscalationPayload` from `src/tools/escalation.py` (already built, 24 passing tests)
6. Implement `RespondOutput` in `src/orchestrator/models/respond.py`
7. Write validation unit tests for all models (cover FR-046 requirement)

**Validation**: All models accept valid input, reject invalid input with clear Pydantic errors.

**Estimated effort**: 2 days

---

## Phase 2.3: RouteState (Pure Python, No Agent)

**Goal**: Implement deterministic routing logic first (easiest state, no Foundry dependency).

**Tasks**:
1. Implement `RouteState` class in `src/orchestrator/states/route.py`
2. Routing logic per FR-010 and FR-011:
   - confidence < 0.6 → `ask_clarifying_question`
   - off_topic=True → `refuse_off_topic`
   - intent="escalate" → `skip_to_escalate`
   - intent="billing" → `billing_path`
   - intent="technical" → `technical_path`
   - intent="account" → `account_path`
   - intent="info" → `info_path`
   - intent="unknown" → `skip_to_escalate`
3. Write unit tests covering all 8 routing paths

**Validation**: All routing decisions match spec requirements, 100% branch coverage.

**Estimated effort**: 1 day

---

## Phase 2.4: AgentFactory and Prompts

**Goal**: Set up Foundry agent creation and system prompts.

**Tasks**:
1. Implement `AgentFactory` in `src/orchestrator/agents/factory.py`
2. Define system prompts in `src/orchestrator/agents/prompts.py`:
   - `CLASSIFIER_SYSTEM_PROMPT` (per FR-029, includes off-topic detection, ignore-instructions guard)
   - `ACT_SYSTEM_PROMPT` (per FR-030, includes ignore-instructions guard)
   - `ESCALATE_SYSTEM_PROMPT` (per FR-031, includes ignore-instructions guard)
   - `RESPOND_SYSTEM_PROMPT` (per FR-032, includes citation requirements, ignore-instructions guard)
3. Wire AgentFactory to import config from `src.config` (model assignments, Foundry endpoint)
4. Write unit tests for factory (mock Foundry SDK, verify agent creation)

**Validation**: Factory creates 4 agents with correct models and prompts.

**Estimated effort**: 2 days

---

## Phase 2.5: ClassifyState

**Goal**: Implement first Foundry-backed state.

**Tasks**:
1. Implement `ClassifyState` in `src/orchestrator/states/classify.py`
2. Invoke ClassifierAgent with customer message + last 5 turns of history
3. Parse agent JSON response into `ClassifyOutput` Pydantic model
4. Handle agent errors (timeout, malformed JSON) per FR-042 to FR-046
5. Emit state_transition log per FR-047
6. Write unit tests (mock agent responses, test error cases)

**Validation**: ClassifyState returns valid `ClassifyOutput`, logs correctly, handles errors.

**Estimated effort**: 2 days

---

## Phase 2.6: ActState

**Goal**: Implement tool-calling state.

**Tasks**:
1. Implement `ActState` in `src/orchestrator/states/act.py`
2. Register 5 existing tools (from `src/tools/`) with ActAgent
3. Invoke ActAgent with routing decision + customer message + history
4. Parse agent response (tools_called, kb_citations, resolution_status)
5. Implement tool error handling per FR-044:
   - `error_code="invalid_format"` → return to Respond with clarification (no escalation)
   - `error_code="not_found"` → return to Respond with "not found" + offer escalation
   - Other errors → mark `resolution_status="unresolved"` for escalation
6. Implement retry logic per FR-035 (single retry with 250ms backoff for transient errors)
7. Emit tool_call logs per FR-048
8. Write unit tests (mock tools, test all error codes, test retry logic)

**Validation**: ActState calls tools correctly, handles all error codes per FR-044, retries transient failures.

**Estimated effort**: 3 days

---

## Phase 2.7: EscalateState

**Goal**: Implement escalation payload generation.

**Tasks**:
1. Implement `EscalateState` in `src/orchestrator/states/escalate.py`
2. Invoke EscalateAgent with full session context (conversation history, tools_called, act result, error_details if any)
3. Generate escalation payload per `docs/ESCALATION_SCHEMA.md` (reuse `EscalationPayload` Pydantic model)
4. Call `create_escalation_ticket()` tool (already built, 24 passing tests)
5. Emit escalation_triggered metric per FR-052
6. Write unit tests (test all reason_codes, test payload structure)

**Validation**: EscalateState generates valid escalation payloads, calls create_escalation_ticket successfully.

**Estimated effort**: 2 days

---

## Phase 2.8: RespondState

**Goal**: Implement final customer-facing response generation.

**Tasks**:
1. Implement `RespondState` in `src/orchestrator/states/respond.py`
2. Invoke RespondAgent with act results + kb_citations + tools_called
3. Enforce citation requirements per FR-032 (policy answers must cite KB docs)
4. Handle special cases per FR-044:
   - `error_code="invalid_format"` from Act → prompt customer to clarify input
   - `error_code="not_found"` from Act → inform customer + offer escalation
5. Implement fallback response per FR-045 if RespondAgent fails
6. Emit final response log
7. Write unit tests (test citation enforcement, test fallback, test error cases)

**Validation**: RespondState generates customer-facing text with citations, handles fallbacks.

**Estimated effort**: 2 days

---

## Phase 2.9: StateMachine Orchestrator

**Goal**: Wire all 5 states into the main orchestration loop.

**Tasks**:
1. Implement `StateMachine` class in `src/orchestrator/state_machine.py`
2. Implement `process_turn()` method:
   - Initialize session state (or load from Streamlit session_state)
   - Run Classify → Route → Act (conditional) → Escalate (conditional) → Respond
   - Update session state (append conversation turn, update correlation_id)
   - Return final response + metadata (tools_called, escalation_triggered, kb_citations)
3. Implement state transition logging per FR-047 (from_state, to_state, decision_reason, duration_ms)
4. Implement end-to-end tracing per FR-051 (correlation_id propagates through all states)
5. Write integration tests covering 4 user stories from spec (P1 and P2 scenarios)

**Validation**: Full turn flows work, all states integrate correctly, logs are complete.

**Estimated effort**: 3 days

---

## Phase 2.10: Streamlit UI Integration

**Goal**: Connect orchestrator to existing Streamlit UI.

**Tasks**:
1. Update `src/ui/streamlit_app.py` to invoke `StateMachine.process_turn()`
2. Display state transitions in UI (live status per FR-057)
3. Display tools called, KB citations, escalation status per FR-058
4. Persist session state in `st.session_state` per FR-053
5. Handle async orchestrator (use `asyncio.run()` or Streamlit async support)
6. Write UI integration tests (use Streamlit testing framework)

**Validation**: UI shows live state transitions, full turn completes end-to-end from user input to response.

**Estimated effort**: 2 days

---

## Phase 2.11: Golden Test Set Evaluation

**Goal**: Run full evaluation per `docs/EVAL.md` against 100-query golden set.

**Tasks**:
1. Load golden test set from `eval/golden_set.csv`
2. Run each query through orchestrator
3. Compute 7 metrics per EVAL.md:
   - Intent accuracy
   - Tool selection correctness
   - Grounding faithfulness
   - Escalation precision
   - Escalation recall
   - Deflection rate
   - Response latency (p95)
4. Generate failure analysis report
5. Iterate on prompts if metrics miss thresholds

**Validation**: All 7 metrics meet or exceed EVAL.md thresholds.

**Estimated effort**: 3 days (includes iteration on prompts if needed)

---

## Phase 2.12: Observability and Final Polish

**Goal**: Complete logging, tracing, and documentation.

**Tasks**:
1. Verify all FR-047 to FR-052 logging requirements are met
2. Add docstrings to all public classes and methods
3. Write architecture documentation (how MAF + Foundry SDK integrate)
4. Write deployment guide (.env setup, Azure credentials)
5. Write troubleshooting guide (common errors, how to read logs)
6. Final code review and cleanup

**Validation**: Logs are complete and parsable, documentation is clear, no TODOs remain.

**Estimated effort**: 2 days

---

## Phase 2.13: Wire One Tool to Real Data Source

**Goal**: Demonstrate database integration pattern by migrating `get_billing_info` from JSON file to SQLite, while keeping other tools on mock JSON.

**Rationale**: 
- Billing data is time-series (multiple records per customer), demonstrating the most data engineering value
- SQLite is file-based, simple, zero Azure cost, but same code pattern works with Azure SQL Database in production
- Introduces DataSource abstraction for swappable backends (JSON vs SQLite vs future Azure SQL)
- Validates that the tool integration pattern supports real databases without breaking existing tools

**Tasks**:

1. **Create DataSource abstraction** in `src/data/base.py`:
   - Define `DataSource` abstract base class with `get_billing_records(account_id, months)` method
   - Allows swapping between JSON and database implementations

2. **Implement JSON DataSource** in `src/data/json_source.py`:
   - `JSONDataSource` class reads from `mock-data/billing.json`
   - Maintains current behavior (default for other 4 tools)

3. **Implement SQLite DataSource** in `src/data/sqlite_source.py`:
   - `SQLiteDataSource` class reads from `data/billing.db`
   - Schema: `billing_records` table with columns: account_id, bill_month, amount_due, due_date, status, line_items (JSON)
   - Uses Python `sqlite3` module (built-in, no new dependencies)

4. **Create SQLite schema and seed data** in `scripts/setup_billing_db.py`:
   - Read `mock-data/billing.json`
   - Create `data/billing.db` with schema
   - Insert all billing records from JSON into SQLite
   - Script is idempotent (drop and recreate on each run)

5. **Update `src/tools/billing.py`**:
   - Import `DataSource` abstraction
   - Load data source from config: `config.BILLING_DATA_SOURCE` (default "json", optional "sqlite")
   - Factory pattern: `get_data_source()` returns `JSONDataSource` or `SQLiteDataSource` based on config
   - No changes to tool function signature or output format

6. **Add config field** in `src/config.py`:
   - `BILLING_DATA_SOURCE: str = "json"` (default JSON for backward compatibility)
   - `BILLING_DB_PATH: str = "data/billing.db"` (SQLite path if enabled)

7. **Update tests** in `tests/test_tools_billing.py`:
   - Add test for SQLite data source (create temp SQLite DB, insert test data, verify tool reads correctly)
   - Existing JSON tests continue to pass (default behavior unchanged)
   - Add integration test that runs same query against both data sources, verifies identical output

8. **Documentation**:
   - Add `docs/DATA_SOURCES.md` explaining the DataSource pattern
   - Document migration path: SQLite locally → Azure SQL Database in production (same code, different connection string)
   - Explain why other 4 tools stay on JSON (simple lookups, no time-series data)

**Validation**: 
- All existing billing tests pass
- New SQLite tests pass
- `get_billing_info` works with both JSON and SQLite data sources
- Config switch controls which source is used
- No changes required to orchestrator or other tools

**Estimated effort**: 2-3 days

**Migration path to production**:
```python
# Local development (SQLite):
BILLING_DATA_SOURCE=sqlite
BILLING_DB_PATH=data/billing.db

# Production (Azure SQL Database):
BILLING_DATA_SOURCE=azure_sql
AZURE_SQL_CONNECTION_STRING=<connection-string>
# Code: Same DataSource abstraction, new AzureSQLDataSource class
```

---

# Total Estimated Effort

**27 days** (assumes 1 developer, 8-hour days, includes testing and iteration).

**Critical path**: Phase 2.9 (StateMachine) depends on all prior phases. Phases 2.3 to 2.8 can proceed in parallel after 2.4 (AgentFactory) is complete. Phase 2.13 (SQLite integration) can proceed in parallel with Phase 2.10-2.12.

---

# Testing Strategy

## Unit Tests (per-state)

- Each state class has isolated unit tests
- Mock Foundry agent responses (use fixture JSONs)
- Mock tool responses (use existing test fixtures from `tests/test_tools_*.py`)
- Test all error paths (FR-042 to FR-046)
- Test Pydantic validation (FR-046)

## Integration Tests (multi-state)

- Test User Story 1 (P1): Happy path billing query
- Test User Story 2 (P1): Tool failure → escalation
- Test User Story 3 (P2): Multi-turn session context
- Test User Story 4 (P2): Explicit escalation request
- Test User Story 5 (P3): Low confidence → clarification

## Golden Test Set (full evaluation)

- 100 queries from `eval/golden_set.csv`
- Compute all 7 metrics per `docs/EVAL.md`
- Generate per-query results CSV
- Generate failure analysis report

## Acceptance Criteria (from spec)

All acceptance criteria from spec FR-390 to FR-396 must pass:
- Intent accuracy >= 90%
- Tool selection >= 85%
- Grounding faithfulness >= 0.90
- Escalation precision >= 85%
- Escalation recall >= 80%
- Deflection rate 30-40%
- Response latency p95 <= 5s

---

# Open Questions

**None**. All technical decisions resolved in Phase 0 research.

---

# Dependencies

**External**:
- Azure AI Foundry project must exist (created via Azure portal or Foundry SDK)
- KB documents must be uploaded to Foundry file_search resource (16 markdown files)
- Azure credentials must be configured (service principal or managed identity)

**Internal**:
- Existing tools in `src/tools/` (5 Azure Functions, already built, 112 passing tests)
- Existing UI in `src/ui/streamlit_app.py` (basic Streamlit chat, needs orchestrator integration)

---

# Risk Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| Foundry SDK breaking changes | High | Pin `azure-ai-projects` version in pyproject.toml, test upgrades in isolation |
| Agent response parsing failures | Medium | FR-042 catch-all error handling + fallback intent="unknown" |
| Tool timeout under load | Medium | FR-035 retry logic + FR-044 escalation on timeout |
| p95 latency exceeds 5s | Medium | Async orchestrator + concurrent tool calls + agent streaming if needed |
| Classification accuracy < 90% | High | Golden test set evaluation in Phase 2.11, iterate on prompts before declaring done |

---

# Next Steps

1. **Phase 0 complete**: This plan document finalizes research decisions
2. **Phase 1 next**: Generate `data-model.md`, `contracts/`, `quickstart.md`
3. **Phase 2 starts**: Begin implementation with Phase 2.1 (scaffolding)

---

**Plan approved by**: [Pending user review]

**Implementation start date**: [To be scheduled after plan approval]
