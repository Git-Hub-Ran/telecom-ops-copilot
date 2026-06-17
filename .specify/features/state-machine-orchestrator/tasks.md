# Tasks: State Machine Orchestrator - Phase 2.1 (Scaffolding)

**Input**: Design documents from `.specify/features/state-machine-orchestrator/`

**Scope**: Phase 2.1 (Scaffolding) only - Foundation for orchestrator implementation

**Prerequisites**: plan.md, research.md, data-model.md

**Organization**: Tasks are listed in execution order with clear dependencies

## Format: `[ID] [P?] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- Include exact file paths in descriptions

---

## Phase 1: Directory Structure

**Purpose**: Set up the orchestrator module structure

- [ ] T001 Create orchestrator directory structure with all subdirectories and `__init__.py` files
  - `src/orchestrator/` with `__init__.py`
  - `src/orchestrator/states/` with `__init__.py`
  - `src/orchestrator/models/` with `__init__.py`
  - `src/orchestrator/agents/` with `__init__.py`
  - `src/orchestrator/observability/` with `__init__.py`
  - `tests/orchestrator/` with `__init__.py`

- [ ] T002 Verify directory structure and Python package recognition
  - Run `python -c "import src.orchestrator; import tests.orchestrator"` to confirm packages are recognized
  - Verify all `__init__.py` files exist

**Validation**: All directories exist, Python recognizes them as packages

---

## Phase 2: Configuration (src/config.py)

**Purpose**: Single project config using Pydantic Settings

**Dependencies**: Phase 1 complete

- [ ] T003 Create `src/config.py` with Config class using pydantic-settings
  - Fields per research.md: FOUNDRY_PROJECT_ID, FOUNDRY_ENDPOINT, FOUNDRY_API_KEY (SecretStr)
  - Model assignments: CLASSIFIER_MODEL, ACT_MODEL, ESCALATE_MODEL, RESPOND_MODEL
  - Thresholds: CLASSIFICATION_CONFIDENCE_THRESHOLD (0.6), RETRY_BACKOFF_MS (250), MAX_CONTEXT_TURNS (5)
  - Paths: MOCK_DATA_DIR (default "mock-data")
  - Config: env_file=".env", case_sensitive=True
  - Export global instance: `config = Config()`

- [ ] T004 Create `.env.example` template file at project root
  - Document all required env vars with example values (non-sensitive)
  - Include comments explaining each variable
  - Add note: "Copy to .env and fill in real values"

**Validation**: `from src.config import get_config` works, config loads from .env

---

## Phase 3: Base State Abstract Class

**Purpose**: Abstract base class for all 5 states to inherit from

**Dependencies**: Phase 1 complete, config exists (T003)

- [ ] T005 Create `src/orchestrator/states/base.py` with BaseState abstract class
  - Import: ABC, abstractmethod from abc
  - Abstract async method: `async def run(self, context: Any) -> Any`
  - Add docstring explaining state contract (input via context, output as return value)
  - No concrete implementation (pure abstract class)

**Validation**: Cannot instantiate BaseState directly, subclasses must implement `run()`

---

## Phase 4: Structured JSON Logging

**Purpose**: Logging utility that emits structured JSON events to stdout

**Dependencies**: Phase 1 complete, config exists (T003)

- [ ] T006 Create `src/orchestrator/observability/structured.py` with StructuredLogger class
  - Import: logging, json, datetime
  - Method: `log_event(event_type: str, **kwargs)` 
  - Output format: one JSON object per line to stdout
  - Required fields: timestamp (ISO 8601), level (INFO/ERROR), event_type
  - Optional fields: correlation_id, session_id, duration_ms, any kwargs
  - Use `print()` for stdout output (not logging.StreamHandler to avoid framework overhead)

- [ ] T007 Create convenience functions in `src/orchestrator/observability/structured.py`
  - `log_state_transition(from_state, to_state, decision_reason, duration_ms, **kwargs)`
  - `log_tool_call(tool_name, success, duration_ms, **kwargs)`
  - `log_classification_result(intent, confidence, **kwargs)`
  - All functions call `log_event()` internally with correct event_type

**Validation**: Calling log functions emits valid JSON to stdout, parsable by `jq`

---

## Phase 5: Tests for Scaffolding

**Purpose**: Unit tests for config and logging utilities

**Dependencies**: Phases 2, 3, 4 complete

### Config Tests

- [ ] T008 Create `tests/orchestrator/test_config.py` with 5 tests
  - Test: Config loads from .env file (mock .env with test values)
  - Test: Config validates required fields (FOUNDRY_PROJECT_ID, FOUNDRY_ENDPOINT, FOUNDRY_API_KEY)
  - Test: Config uses default values for optional fields (CLASSIFIER_MODEL, thresholds)
  - Test: Config fails with clear error if required field missing
  - Test: SecretStr hides API key in repr/str output

**Validation**: All config tests pass

### BaseState Tests

- [ ] T009 Create `tests/orchestrator/test_states/test_base.py` with 4 tests
  - Create `tests/orchestrator/test_states/` directory and `__init__.py` if needed
  - Test: Cannot instantiate BaseState directly (raises TypeError)
  - Test: Concrete subclass without `run()` raises TypeError
  - Test: Concrete subclass with `run()` can be instantiated
  - Test: `run()` method is async (inspect.iscoroutinefunction)

**Validation**: All BaseState tests pass

### Logging Tests

- [ ] T010 Create `tests/orchestrator/test_logging.py` with 7 tests
  - Test: `log_event()` emits valid JSON to stdout (capture stdout, parse with json.loads)
  - Test: JSON includes required fields (timestamp, level, event_type)
  - Test: JSON includes optional kwargs
  - Test: Timestamp is ISO 8601 format
  - Test: `log_state_transition()` emits correct event_type
  - Test: `log_tool_call()` emits correct event_type
  - Test: `log_classification_result()` emits correct event_type

**Validation**: All logging tests pass

---

## Phase 6: Integration Validation

**Purpose**: Verify all scaffolding pieces work together

**Dependencies**: All previous phases complete

- [ ] T011 Create `tests/orchestrator/test_scaffolding_integration.py` with 5 tests
  - Test: Import config from src.config works
  - Test: Import BaseState from src.orchestrator.states.base works
  - Test: Import structured logging from src.orchestrator.observability.structured works
  - Test: Create concrete state subclass, verify it can access config
  - Test: Log event with correlation_id, verify JSON output contains it

**Validation**: All integration tests pass, no import errors

---

## Completion Checklist

Phase 2.1 (Scaffolding) is complete when:

- [ ] All directory structure created (T001-T002)
- [ ] `src/config.py` exists and loads from .env (T003-T004)
- [ ] `BaseState` abstract class exists (T005)
- [ ] Structured logging utility exists (T006-T007)
- [ ] All tests pass (T008-T011)
- [ ] No import errors when importing from src.orchestrator
- [ ] Running `pytest tests/orchestrator/` shows all scaffolding tests passing

**Expected test count**: 21 tests (5 config, 4 BaseState, 7 logging, 5 integration)

---

## Next Phase

After Phase 2.1 is complete and committed:
- Run `/speckit-tasks` again scoped to Phase 2.2 (Pydantic Data Contracts)
- Phase 2.2 will implement the 7 Pydantic models defined in data-model.md

---

## Dependencies

```
Phase 1 (Directory Structure)
  ↓
Phase 2 (Config) ←─┐
  ↓                │
Phase 3 (BaseState) (depends on config for typing hints if needed)
  ↓                │
Phase 4 (Logging) ←┘
  ↓
Phase 5 (Tests)
  ↓
Phase 6 (Integration)
```

**Parallel opportunities**:
- T003-T004 (config, .env.example) can run in parallel after T001-T002
- T005-T007 (BaseState, logging) can run in parallel after T003 (config exists)
- T008-T010 (test files) can run in parallel once implementation is done

---

**Total tasks**: 11 tasks
**Estimated effort**: 1 day (per plan.md Phase 2.1)
**Deliverables**:
- `src/config.py` (single project config)
- `src/orchestrator/states/base.py` (BaseState abstract class)
- `src/orchestrator/observability/structured.py` (JSON logging utility)
- `.env.example` (config template)
- 5 test files with ~15-20 passing tests

---

# Phase 2.2: Pydantic Data Contracts (T012-T026)

**Input**: `.specify/features/state-machine-orchestrator/data-model.md`

**Scope**: Phase 2.2 (Pydantic Data Contracts) only - 7 Pydantic models with full validation

**Prerequisites**: Phase 2.1 complete (config, BaseState, structured logging, tests passing)

**Organization**: Tasks listed in dependency order (models that depend on others come later)

---

## Session State Models (FR-007, FR-053, FR-054)

**Purpose**: Multi-turn conversation persistence models

**Dependencies**: Phase 2.1 complete

- [ ] T012 Create `src/orchestrator/models/session.py` with ConversationTurn and SessionState
  - Import: `from typing import Optional, Literal` and `from pydantic import BaseModel, Field`
  - Class: `ConversationTurn` with 3 fields (role, content, timestamp)
    - `role`: Literal["customer", "agent"]
    - `content`: str
    - `timestamp`: str (ISO 8601)
  - Class: `SessionState` with 7 fields
    - `session_id`: str (SESS-* format, enforced by caller)
    - `correlation_id`: str (unique per turn)
    - `account_id`: Optional[str] = None (ACC-* format if present)
    - `detected_emotion`: Optional[str] = None
    - `conversation_history`: list[ConversationTurn] = Field(default_factory=list)
    - `started_at`: str (ISO 8601)
    - `last_updated`: str (ISO 8601)
  - Add module docstring explaining session state persistence
  - Add class docstrings with field descriptions

- [ ] T013 Create `tests/orchestrator/test_models/test_session.py` with 8 tests
  - Create `tests/orchestrator/test_models/` directory with `__init__.py` if needed
  - Test: ConversationTurn accepts valid role "customer"
  - Test: ConversationTurn accepts valid role "agent"
  - Test: ConversationTurn rejects invalid role value (raises ValidationError)
  - Test: SessionState accepts all required fields
  - Test: SessionState missing session_id raises ValidationError
  - Test: SessionState account_id can be None (optional field)
  - Test: SessionState conversation_history defaults to empty list
  - Test: SessionState accepts list of ConversationTurn objects
  - Run pytest on test_session.py, verify 8 tests pass

**Validation**: 8 tests pass, SessionState and ConversationTurn models work

---

## Classification Models (FR-008, FR-009)

**Purpose**: Classification output from ClassifyState

**Dependencies**: Phase 2.1 complete (no model dependencies)

- [ ] T014 [P] Create `src/orchestrator/models/classify.py` with ClassifyOutput
  - Import: `from typing import Optional, Literal` and `from pydantic import BaseModel, Field`
  - Class: `ClassifyOutput` with 4 fields
    - `intent`: Literal["billing", "technical", "account", "info", "escalate", "unknown"]
    - `confidence`: float = Field(ge=0.0, le=1.0)
    - `detected_emotion`: Optional[str] = None
    - `off_topic`: bool = False
  - Add module docstring explaining classification output
  - Add class docstring with validation rules
  - Example in docstring showing JSON output

- [ ] T015 [P] Create `tests/orchestrator/test_models/test_classify.py` with 7 tests
  - Test: ClassifyOutput accepts valid intent "billing"
  - Test: ClassifyOutput accepts valid intent "escalate"
  - Test: ClassifyOutput rejects invalid intent value (raises ValidationError)
  - Test: ClassifyOutput confidence=0.92 is valid
  - Test: ClassifyOutput confidence=-0.1 raises ValidationError (below ge=0.0)
  - Test: ClassifyOutput confidence=1.5 raises ValidationError (above le=1.0)
  - Test: ClassifyOutput off_topic defaults to False
  - Run pytest on test_classify.py, verify 7 tests pass

**Validation**: 7 tests pass, ClassifyOutput model works

---

## Routing Models (FR-010, FR-011, FR-012)

**Purpose**: Routing decision enum

**Dependencies**: Phase 2.1 complete (no model dependencies)

- [ ] T016 [P] Create `src/orchestrator/models/route.py` with RoutingDecision enum
  - Import: `from enum import Enum`
  - Class: `RoutingDecision(str, Enum)` with 7 values
    - BILLING_PATH = "billing_path"
    - TECHNICAL_PATH = "technical_path"
    - ACCOUNT_PATH = "account_path"
    - INFO_PATH = "info_path"
    - SKIP_TO_ESCALATE = "skip_to_escalate"
    - ASK_CLARIFYING_QUESTION = "ask_clarifying_question"
    - REFUSE_OFF_TOPIC = "refuse_off_topic"
  - Add module docstring explaining routing decision logic
  - Add table in docstring showing condition to decision mapping (from data-model.md)

- [ ] T017 [P] Create `tests/orchestrator/test_models/test_route.py` with 4 tests
  - Test: RoutingDecision.BILLING_PATH has value "billing_path"
  - Test: RoutingDecision.SKIP_TO_ESCALATE has value "skip_to_escalate"
  - Test: All 7 enum values are unique
  - Test: Can compare RoutingDecision values (e.g., decision == RoutingDecision.BILLING_PATH)
  - Run pytest on test_route.py, verify 4 tests pass

**Validation**: 4 tests pass, RoutingDecision enum works

---

## Act State Models (FR-013, FR-014, FR-015)

**Purpose**: Tool call records, KB citations, and Act state output

**Dependencies**: Phase 2.1 complete (no model dependencies)

- [ ] T018 Create `src/orchestrator/models/act.py` with ToolCallRecord, KBCitation, ActOutput
  - Import: `from typing import Optional, Literal` and `from pydantic import BaseModel, Field`
  - Class: `ToolCallRecord` with 6 fields
    - `tool_name`: str
    - `input`: dict (tool arguments)
    - `result_summary`: str
    - `called_at`: str (ISO 8601)
    - `success`: bool
    - `error_code`: Optional[str] = None
  - Class: `KBCitation` with 3 fields
    - `doc_id`: str (e.g., kb/policies/02-late-fees.md)
    - `section`: str (section title)
    - `relevance`: str (why relevant)
  - Class: `ActOutput` with 4 fields
    - `resolution_status`: Literal["resolved", "partial", "unresolved"]
    - `tools_called`: list[ToolCallRecord] = Field(default_factory=list)
    - `kb_citations`: list[KBCitation] = Field(default_factory=list)
    - `error_details`: Optional[str] = None
  - Add module docstring explaining Act state output
  - Add class docstrings with validation rules
  - Add example in ActOutput docstring showing JSON with tool call

- [ ] T019 Create `tests/orchestrator/test_models/test_act.py` with 10 tests
  - Test: ToolCallRecord accepts all required fields
  - Test: ToolCallRecord missing tool_name raises ValidationError
  - Test: ToolCallRecord error_code can be None
  - Test: KBCitation accepts all required fields
  - Test: KBCitation missing doc_id raises ValidationError
  - Test: ActOutput accepts valid resolution_status "resolved"
  - Test: ActOutput rejects invalid resolution_status value (raises ValidationError)
  - Test: ActOutput tools_called defaults to empty list
  - Test: ActOutput kb_citations defaults to empty list
  - Test: ActOutput accepts list of ToolCallRecord and list of KBCitation
  - Run pytest on test_act.py, verify 10 tests pass

**Validation**: 10 tests pass, ToolCallRecord, KBCitation, ActOutput models work

---

## Response Models (FR-017)

**Purpose**: Final customer-facing response

**Dependencies**: Phase 2.1 complete (no model dependencies)

- [ ] T020 [P] Create `src/orchestrator/models/respond.py` with RespondOutput
  - Import: `from pydantic import BaseModel, Field`
  - Class: `RespondOutput` with 4 fields
    - `message`: str (customer-facing response)
    - `citations_included`: bool
    - `escalation_offered`: bool = False
    - `metadata`: dict = Field(default_factory=dict)
  - Add module docstring explaining final response output
  - Add class docstring with validation rules (citations required for policy answers, etc.)
  - Add two examples in docstring: one with citations, one with not_found error

- [ ] T021 [P] Create `tests/orchestrator/test_models/test_respond.py` with 5 tests
  - Test: RespondOutput accepts all required fields
  - Test: RespondOutput missing message raises ValidationError
  - Test: RespondOutput escalation_offered defaults to False
  - Test: RespondOutput metadata defaults to empty dict
  - Test: RespondOutput message cannot be empty string (add validation if needed)
  - Run pytest on test_respond.py, verify 5 tests pass

**Validation**: 5 tests pass, RespondOutput model works

---

## State Context Model (Internal)

**Purpose**: Shared context passed between states

**Dependencies**: SessionState (T012), ClassifyOutput (T014), RoutingDecision (T016), ActOutput (T018)

- [ ] T022 Create `src/orchestrator/models/context.py` with StateContext
  - Import: `from typing import Optional` and `from pydantic import BaseModel`
  - Import models: `from .session import SessionState`
  - Import models: `from .classify import ClassifyOutput`
  - Import models: `from .route import RoutingDecision`
  - Import models: `from .act import ActOutput`
  - Class: `StateContext` with 5 fields
    - `session_state`: SessionState
    - `customer_message`: str
    - `routing_decision`: Optional[RoutingDecision] = None (set by RouteState)
    - `classify_output`: Optional[ClassifyOutput] = None (set by ClassifyState)
    - `act_output`: Optional[ActOutput] = None (set by ActState)
  - Add module docstring explaining StateContext usage
  - Add class docstring explaining how StateMachine builds this context

- [ ] T023 Create `tests/orchestrator/test_models/test_context.py` with 6 tests
  - Test: StateContext accepts session_state and customer_message (required fields)
  - Test: StateContext missing session_state raises ValidationError
  - Test: StateContext routing_decision can be None (optional)
  - Test: StateContext classify_output can be None (optional)
  - Test: StateContext act_output can be None (optional)
  - Test: StateContext accepts all fields populated (full context)
  - Run pytest on test_context.py, verify 6 tests pass

**Validation**: 6 tests pass, StateContext model works

---

## Models Package Exports

**Purpose**: Clean public API for importing models

**Dependencies**: All model files created (T012, T014, T016, T018, T020, T022)

- [ ] T024 Update `src/orchestrator/models/__init__.py` to export all models
  - Import and re-export: `ConversationTurn`, `SessionState` from `.session`
  - Import and re-export: `ClassifyOutput` from `.classify`
  - Import and re-export: `RoutingDecision` from `.route`
  - Import and re-export: `ToolCallRecord`, `KBCitation`, `ActOutput` from `.act`
  - Import and re-export: `RespondOutput` from `.respond`
  - Import and re-export: `StateContext` from `.context`
  - Add module docstring: "Pydantic data contracts for state machine orchestrator."
  - Add `__all__` list with all exported names

**Validation**: `from src.orchestrator.models import SessionState, ClassifyOutput` works

---

## Integration Tests

**Purpose**: Verify all models work together

**Dependencies**: All models and tests complete (T012-T024)

- [ ] T025 Create `tests/orchestrator/test_models/test_models_integration.py` with 5 tests
  - Test: Import all models from src.orchestrator.models works
  - Test: Create SessionState with ConversationTurn objects
  - Test: Create StateContext with SessionState and ClassifyOutput
  - Test: Create ActOutput with ToolCallRecord and KBCitation lists
  - Test: All model __repr__ outputs are readable (no Pydantic internal details leak)
  - Run pytest on test_models_integration.py, verify 5 tests pass

**Validation**: 5 tests pass, all models integrate correctly

---

## Full Test Suite Validation

**Purpose**: Verify all Phase 2.2 tests pass together

**Dependencies**: All tests created (T013, T015, T017, T019, T021, T023, T025)

- [ ] T026 Run full Phase 2.2 test suite
  - Run `pytest tests/orchestrator/test_models/ -v`
  - Verify all 45 tests pass (8 + 7 + 4 + 10 + 5 + 6 + 5 = 45 tests)
  - Verify no import errors
  - Verify test output is clean (no warnings)

**Validation**: 45 tests pass, no errors or warnings

---

## Phase 2.2 Completion Checklist

Phase 2.2 (Pydantic Data Contracts) is complete when:

- [ ] All 7 model files created (session, classify, route, act, respond, context)
- [ ] All 6 test files created with passing tests
- [ ] `src/orchestrator/models/__init__.py` exports all models
- [ ] Running `pytest tests/orchestrator/test_models/` shows 45 passing tests
- [ ] No import errors when importing from src.orchestrator.models
- [ ] All models have docstrings and field descriptions
- [ ] EscalationPayload from src.tools.escalation is documented as reusable (no new implementation needed)

**Expected test count**: 45 tests (8 session + 7 classify + 4 route + 10 act + 5 respond + 6 context + 5 integration)

**Note**: EscalationPayload is NOT implemented in Phase 2.2 because it already exists in `src/tools/escalation.py` with 24 passing tests. RouteState and EscalateState will import it directly.

---

## Phase 2.2 Next Steps

After Phase 2.2 is complete and committed:
- Phase 2.3 will implement the 5 state classes (ClassifyState, RouteState, ActState, EscalateState, RespondState)
- Each state will use the Pydantic models created in Phase 2.2

---

## Phase 2.2 Dependencies

```
Phase 2.1 (Scaffolding)
  ↓
Phase 2.2 (Pydantic Data Contracts)
  │
  ├─> T012-T013 (SessionState + tests)
  │     ↓
  ├─> T014-T015 (ClassifyOutput + tests)  [P]
  ├─> T016-T017 (RoutingDecision + tests) [P]
  ├─> T018-T019 (ActOutput + tests)       [P]
  ├─> T020-T021 (RespondOutput + tests)   [P]
  │     ↓
  ├─> T022-T023 (StateContext + tests) (depends on all models above)
  │     ↓
  ├─> T024 (Package exports) (depends on all models)
  │     ↓
  ├─> T025 (Integration tests)
  │     ↓
  └─> T026 (Full test suite)
```

**Parallel opportunities**:
- T014-T015, T016-T017, T018-T019, T020-T021 can all run in parallel after T012-T013 (no dependencies between them)
- Each model + test pair can be implemented together

---

**Phase 2.2 Total tasks**: 15 tasks (T012-T026)
**Estimated effort**: 1 day (per plan.md Phase 2.2)
**Deliverables**:
- 7 Pydantic model files in `src/orchestrator/models/`
- 6 test files in `tests/orchestrator/test_models/` with 45 passing tests
- Clean package exports via `__init__.py`
- Full validation coverage (required fields, enums, ranges, optional fields)
