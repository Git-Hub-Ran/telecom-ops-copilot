# Contract: RespondState

**State**: Respond  
**Purpose**: Generate final customer-facing response with citations.

---

## Input

```python
act_output: ActOutput
routing_decision: RoutingDecision
customer_message: str
```

---

## Output

```python
class RespondOutput(BaseModel):
    message: str  # Customer-facing text
    citations_included: bool
    escalation_offered: bool
    metadata: dict
```

---

## Agent Configuration

**Model**: `gpt-4o`

**System Prompt**:
- Enforce citations for policy answers (FR-032)
- Handle special cases from FR-044:
  - `invalid_format` error → "Please provide your account ID in format ACC-XXXXX"
  - `not_found` error → "I couldn't find that account. Would you like me to connect you with a representative?"
- If routing_decision is `REFUSE_OFF_TOPIC` → polite refusal without escalation

---

## Fallback (FR-045)

If RespondAgent fails: "I'm sorry, I encountered an issue. Let me connect you with support."

---

## Citation Example

Input KB citation:
```json
{
  "doc_id": "kb/policies/02-late-fees.md",
  "section": "Grace period",
  "relevance": "Defines late fee policy"
}
```

Output message:
```
"According to kb/policies/02-late-fees.md, the grace period for late payments is 5 business days."
```
