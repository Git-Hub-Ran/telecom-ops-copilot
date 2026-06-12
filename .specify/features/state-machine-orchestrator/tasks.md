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
  - `src/orchestrator/logging/` with `__init__.py`
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

**Validation**: `from src.config import config` works, config loads from .env

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

- [ ] T006 Create `src/orchestrator/logging/structured.py` with StructuredLogger class
  - Import: logging, json, datetime
  - Method: `log_event(event_type: str, **kwargs)` 
  - Output format: one JSON object per line to stdout
  - Required fields: timestamp (ISO 8601), level (INFO/ERROR), event_type
  - Optional fields: correlation_id, session_id, duration_ms, any kwargs
  - Use `print()` for stdout output (not logging.StreamHandler to avoid framework overhead)

- [ ] T007 Create convenience functions in `src/orchestrator/logging/structured.py`
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
  - Test: Import structured logging from src.orchestrator.logging.structured works
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
- `src/orchestrator/logging/structured.py` (JSON logging utility)
- `.env.example` (config template)
- 5 test files with ~15-20 passing tests
