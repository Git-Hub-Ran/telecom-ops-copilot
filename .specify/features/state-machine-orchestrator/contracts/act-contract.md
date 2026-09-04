# Contract: ActState

**State**: Act  
**Purpose**: Execute actions (call tools, retrieve KB) based on routing decision.

---

## Input

```python
routing_decision: RoutingDecision
customer_message: str
session_state: SessionState
```

---

## Output

```python
class ActOutput(BaseModel):
    resolution_status: Literal["resolved", "partial", "unresolved"]
    tools_called: list[ToolCallRecord]
    kb_citations: list[KBCitation]
    error_details: Optional[str]
```

---

## Agent Configuration

**Model**: `gpt-4o` (quality matters for tool use)

**Tools registered**:
- `get_customer_account(account_id: str)`
- `get_billing_info(account_id: str, months: int)`
- `check_network_outage(zip_code: str)`
- `run_speed_diagnostic(account_id: str)`

**File search enabled**: Yes (16 KB documents)

---

## Tool Error Handling (FR-044)

| Error Code | Handling |
|------------|----------|
| `invalid_format` | Return `resolution_status="partial"`, include error in `error_details`, do NOT escalate |
| `not_found` | Return `resolution_status="partial"`, include error in `error_details`, do NOT escalate |
| `data_unavailable`, `data_invalid`, other errors | Retry once with 250ms backoff (FR-035). If still fails, return `resolution_status="unresolved"` for escalation |
| Tool exception | Catch, log stack trace, retry once. If still fails, return `unresolved` |

---

## Logging (FR-048)

Log each tool call:
```json
{
  "event_type": "tool_call",
  "tool_name": "get_billing_info",
  "input": {"account_id": "ACC-10001", "months": 3},
  "output_summary": "Retrieved 3 bills",
  "success": true,
  "duration_ms": 450,
  "called_at": "2026-06-10T14:25:30Z"
}
```
