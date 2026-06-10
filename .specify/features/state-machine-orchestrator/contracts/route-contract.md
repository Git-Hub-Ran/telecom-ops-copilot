# Contract: RouteState

**State**: Route  
**Purpose**: Pure Python routing logic (no LLM). Maps ClassifyOutput to RoutingDecision.

---

## Input

```python
classify_output: ClassifyOutput  # From ClassifyState
```

---

## Output

```python
class RoutingDecision(str, Enum):
    BILLING_PATH = "billing_path"
    TECHNICAL_PATH = "technical_path"
    ACCOUNT_PATH = "account_path"
    INFO_PATH = "info_path"
    SKIP_TO_ESCALATE = "skip_to_escalate"
    ASK_CLARIFYING_QUESTION = "ask_clarifying_question"
    REFUSE_OFF_TOPIC = "refuse_off_topic"
```

---

## Routing Logic

```python
def route(classify_output: ClassifyOutput) -> RoutingDecision:
    if classify_output.off_topic:
        return RoutingDecision.REFUSE_OFF_TOPIC
    
    if classify_output.confidence < 0.6:
        return RoutingDecision.ASK_CLARIFYING_QUESTION
    
    if classify_output.intent == "escalate":
        return RoutingDecision.SKIP_TO_ESCALATE
    
    if classify_output.intent == "unknown":
        return RoutingDecision.SKIP_TO_ESCALATE
    
    # Map intent to path
    intent_map = {
        "billing": RoutingDecision.BILLING_PATH,
        "technical": RoutingDecision.TECHNICAL_PATH,
        "account": RoutingDecision.ACCOUNT_PATH,
        "info": RoutingDecision.INFO_PATH,
    }
    return intent_map[classify_output.intent]
```

---

## Testing

Unit tests must cover all 9 routing paths (100% branch coverage).
