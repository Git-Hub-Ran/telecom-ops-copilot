# Quickstart: State Machine Orchestrator Validation

**Feature**: State Machine Orchestrator  
**Purpose**: Runnable validation scenarios to prove the feature works end-to-end  
**Date**: 2026-06-10

This guide provides step-by-step validation scenarios. It does NOT include implementation code (see `plan.md` Phase 2 for implementation order).

---

## Prerequisites

1. **Azure AI Foundry project created**:
   - Project ID, endpoint, API key available
   - 16 KB documents uploaded to file_search resource

2. **Environment configured**:
   ```bash
   cp .env.example .env
   # Edit .env with your Foundry credentials
   ```

3. **Dependencies installed**:
   ```bash
   pip install -r requirements.txt
   # Should include: azure-ai-projects, azure-identity, pydantic, python-dotenv, streamlit
   ```

4. **Existing tools verified**:
   ```bash
   pytest tests/test_tools_*.py -v
   # Should show: 112 passed
   ```

---

## Validation Scenario 1: Happy Path Billing Query (P1)

**Objective**: Verify full state flow works: Classify → Route → Act → Respond

**Input**:
```python
customer_message = "What is my current bill for account ACC-10001?"
session_state = SessionState(
    session_id="SESS-test-001",
    correlation_id="uuid-001",
    conversation_history=[],
    started_at="2026-06-10T14:00:00Z",
    last_updated="2026-06-10T14:00:00Z"
)
```

**Run**:
```bash
pytest tests/orchestrator/test_integration/test_happy_path.py::test_billing_query -v
```

**Expected Results**:

1. **ClassifyState** returns:
   ```json
   {
     "intent": "billing",
     "confidence": 0.92,
     "detected_emotion": "neutral",
     "off_topic": false
   }
   ```

2. **RouteState** returns:
   ```
   RoutingDecision.BILLING_PATH
   ```

3. **ActState** calls `get_billing_info(account_id="ACC-10001", months=3)`:
   ```json
   {
     "resolution_status": "resolved",
     "tools_called": [{"tool_name": "get_billing_info", "success": true}],
     "kb_citations": [],
     "error_details": null
   }
   ```

4. **RespondState** returns:
   ```json
   {
     "message": "Your current bill for account ACC-10001 is $89.99, due on June 15, 2026. The bill includes...",
     "citations_included": false,
     "escalation_offered": false
   }
   ```

5. **Logs emitted** (verify in stdout):
   - `state_transition` event: classify → route
   - `classification_result` event
   - `state_transition` event: route → act
   - `tool_call` event: get_billing_info
   - `state_transition` event: act → respond
   - `total_turn_duration_ms` metric

**Success Criteria**:
- Full flow completes without errors
- Tool is called correctly
- Response is customer-facing and accurate
- All logs are valid JSON

---

## Validation Scenario 2: Tool Failure → Escalation (P1)

**Objective**: Verify error handling per FR-044

**Input**:
```python
customer_message = "Show me account ACC-99999"  # Non-existent account
```

**Run**:
```bash
pytest tests/orchestrator/test_integration/test_tool_failure.py::test_not_found_error -v
```

**Expected Results**:

1. **ActState** calls `get_customer_account(account_id="ACC-99999")`:
   - Tool returns: `{"success": false, "error_code": "not_found"}`

2. **ActState** does NOT escalate automatically:
   ```json
   {
     "resolution_status": "partial",
     "error_details": "Account ACC-99999 not found"
   }
   ```

3. **RespondState** offers escalation:
   ```json
   {
     "message": "I couldn't find an account with ID ACC-99999. Would you like me to connect you with a representative to verify your account information?",
     "escalation_offered": true
   }
   ```

4. **Escalation is NOT triggered** (verify no `escalation_triggered: true` metric)

**Success Criteria**:
- `not_found` error does not auto-escalate
- Customer gets helpful message + escalation option
- Logs include error details

---

## Validation Scenario 3: Multi-Turn Context (P2)

**Objective**: Verify session state persists account_id across turns

**Input (Turn 1)**:
```python
customer_message = "Hi, I'm John. My account is ACC-10001."
```

**Input (Turn 2)**:
```python
customer_message = "What is my bill?"
# session_state.account_id should now be "ACC-10001" from turn 1
```

**Run**:
```bash
pytest tests/orchestrator/test_integration/test_multi_turn.py::test_context_persistence -v
```

**Expected Results**:

1. **Turn 1**: ClassifyState extracts account_id, stores in session_state
2. **Turn 2**: ActState uses session_state.account_id without asking again
3. **Turn 2 tool call**: `get_billing_info(account_id="ACC-10001")`

**Success Criteria**:
- account_id persists between turns
- Customer does not need to repeat account ID
- Conversation history includes last 5 turns

---

## Validation Scenario 4: Off-Topic Query → Polite Refusal (P2)

**Objective**: Verify off-topic handling per FR-018 to FR-023

**Input**:
```python
customer_message = "What is the weather like in San Francisco?"
```

**Run**:
```bash
pytest tests/orchestrator/test_integration/test_escalation.py::test_off_topic_refusal -v
```

**Expected Results**:

1. **ClassifyState** returns:
   ```json
   {
     "intent": "escalate",
     "confidence": 0.85,
     "off_topic": true
   }
   ```

2. **RouteState** returns:
   ```
   RoutingDecision.REFUSE_OFF_TOPIC
   ```

3. **ActState is skipped** (no tools called)

4. **RespondState** returns polite refusal:
   ```json
   {
     "message": "I can only help with telecom-related questions about your service, billing, or account. For weather information, please use a weather service.",
     "escalation_offered": false
   }
   ```

5. **Escalation is NOT triggered** (verify `expected_escalation=false` per EVAL.md ADV-006)

**Success Criteria**:
- Off-topic query is detected
- Customer gets polite refusal
- No escalation occurs

---

## Validation Scenario 5: Low Confidence → Clarification (P3)

**Objective**: Verify clarification flow per FR-044

**Input**:
```python
customer_message = "It's not working"  # Ambiguous
```

**Expected Results**:

1. **ClassifyState** returns:
   ```json
   {
     "intent": "technical",
     "confidence": 0.45
   }
   ```

2. **RouteState** returns:
   ```
   RoutingDecision.ASK_CLARIFYING_QUESTION
   ```

3. **RespondState** asks for clarification:
   ```json
   {
     "message": "I'd like to help with your service issue. Could you please tell me: Is this about your internet connection, mobile service, or TV service?"
   }
   ```

**Success Criteria**:
- Low confidence triggers clarification
- No tools are called prematurely
- Customer gets helpful prompt

---

## Golden Test Set Evaluation

**Objective**: Run full evaluation per docs/EVAL.md

**Prerequisites**:
- Golden test set exists at `eval/golden_set.csv` (100 queries)
- All states implemented and passing unit tests

**Run**:
```bash
python notebooks/02-evaluation.ipynb
# Or: pytest tests/orchestrator/test_golden_set.py
```

**Expected Output**:
```
Results Summary (eval/results_20260610.csv):
- Intent accuracy: 92.0% (target: >= 90%)
- Tool selection: 87.5% (target: >= 85%)
- Grounding faithfulness: 0.91 (target: >= 0.90)
- Escalation precision: 88.0% (target: >= 85%)
- Escalation recall: 82.0% (target: >= 80%)
- Deflection rate (standard set): 35% (target: 30-40%)
- Response latency p95: 4.2s (target: <= 5s)

✅ ALL METRICS PASS
```

**Success Criteria**: All 7 metrics meet or exceed thresholds.

---

## Streamlit UI Validation

**Objective**: Verify full integration with UI

**Run**:
```bash
streamlit run src/ui/streamlit_app.py
```

**Manual Test**:
1. Open browser to http://localhost:8501
2. Send message: "What is my bill for ACC-10001?"
3. Observe:
   - Live state transitions displayed
   - Tools called shown in sidebar
   - Final response appears
   - Escalation status shown if applicable

**Success Criteria**:
- UI displays all state transitions
- Tools called are visible
- Response is customer-facing
- Session persists across page refreshes

---

## Logging Validation

**Objective**: Verify structured JSON logs per FR-050

**Run**:
```bash
pytest tests/orchestrator/test_state_machine.py::test_logging -v 2>&1 | grep '{"timestamp"'
```

**Expected Output** (sample):
```json
{"timestamp":"2026-06-10T14:25:00Z","level":"INFO","event_type":"state_transition","from_state":"classify","to_state":"route","duration_ms":340}
{"timestamp":"2026-06-10T14:25:10Z","level":"INFO","event_type":"classification_result","intent":"billing","confidence":0.92}
{"timestamp":"2026-06-10T14:25:20Z","level":"INFO","event_type":"tool_call","tool_name":"get_billing_info","success":true,"duration_ms":450}
{"timestamp":"2026-06-10T14:25:30Z","level":"INFO","event_type":"state_transition","to_state":"respond","duration_ms":1200}
```

**Success Criteria**:
- All logs are valid JSON (parsable by `jq`)
- Logs include all required fields per FR-047 to FR-052
- correlation_id appears in all logs for a turn

---

## Configuration Validation

**Objective**: Verify .env config loading works

**Setup**:
```bash
cat > .env <<EOF
FOUNDRY_PROJECT_ID=test-project-123
FOUNDRY_ENDPOINT=https://test.api.azure.com
FOUNDRY_API_KEY=test-key-456
CLASSIFIER_MODEL=gpt-4o-mini
ACT_MODEL=gpt-4o
CLASSIFICATION_CONFIDENCE_THRESHOLD=0.6
EOF
```

**Run**:
```python
from src.orchestrator.config import OrchestratorConfig

config = OrchestratorConfig()
assert config.FOUNDRY_PROJECT_ID == "test-project-123"
assert config.CLASSIFIER_MODEL == "gpt-4o-mini"
assert config.CLASSIFICATION_CONFIDENCE_THRESHOLD == 0.6
```

**Success Criteria**: Config loads from .env, Pydantic validates all fields.

---

## Deployment Readiness Checklist

Before deploying to Azure:

- [ ] All 112 tool tests pass
- [ ] All orchestrator unit tests pass (states, models)
- [ ] All integration tests pass (4 user stories)
- [ ] Golden test set evaluation passes (7 metrics)
- [ ] Streamlit UI works locally
- [ ] Logs are valid JSON and parsable
- [ ] Configuration loads from Azure env vars (not .env)
- [ ] Azure credentials work (service principal or managed identity)
- [ ] KB documents uploaded to Foundry file_search resource
- [ ] 4 Foundry agents created (ClassifierAgent, ActAgent, EscalateAgent, RespondAgent)

---

**Quickstart complete**: 2026-06-10  
**Validation scenarios**: 5 core + 1 full evaluation  
**Ready for implementation**: Yes (see `plan.md` Phase 2)
