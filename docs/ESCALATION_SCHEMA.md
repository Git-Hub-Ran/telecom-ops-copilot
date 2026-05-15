# Escalation Payload Schema

When the agent decides to escalate a customer interaction to a human, it produces a structured JSON payload. This is the **contract between the AI agent and the human support rep**.

The goal is that the human picks up the conversation already oriented: they know who the customer is, what they were asking about, what the agent tried, what evidence the agent used, and how the customer was feeling. No more "cold handoffs" where the customer has to explain everything again.

## When the agent escalates

The agent escalates in any of these cases:

1. **Tool failure** - a needed tool returned an error or empty result and the agent has no fallback
2. **Out-of-scope intent** - the customer asked for something the agent is not authorized to do (e.g. modify account ownership, waive a charge above $50)
3. **Repeated frustration signal** - the customer expresses anger, mentions cancellation threat, or asks for a human
4. **Ambiguous after multiple turns** - the agent could not classify the intent after 3 turns
5. **Safety trip** - the conversation triggered a content safety filter or prompt injection defense

## Schema

```json
{
  "escalation_id": "ESC-YYYYMMDD-HHMMSS-XXXX",
  "created_at": "2026-05-13T14:30:00Z",
  "reason_code": "tool_failure | out_of_scope | customer_frustration | unresolved_ambiguity | safety_trip",
  "priority": "low | medium | high | urgent",

  "customer": {
    "account_id": "ACC-10001 | null",
    "phone_contact": "+1-555-100-0001 | null",
    "name_on_file": "John Smith | null",
    "verified": true | false
  },

  "session": {
    "session_id": "SESS-uuid",
    "started_at": "2026-05-13T14:25:00Z",
    "channel": "chat | voice | email",
    "language": "en"
  },

  "intent": {
    "primary": "billing | technical | account | info | unknown",
    "secondary": ["..."],
    "confidence": 0.0
  },

  "summary": "1-3 sentence plain-English summary of what the customer was trying to do and why we are handing off.",

  "tools_called": [
    {
      "tool_name": "get_customer_account",
      "input": {"account_id": "ACC-10001"},
      "result_summary": "Account found, status active, on Essential plan",
      "called_at": "2026-05-13T14:26:00Z"
    }
  ],

  "kb_citations": [
    {
      "doc_id": "kb/policies/02-late-fees.md",
      "section": "Disputing a late fee",
      "relevance": "Customer is asking about a fee that may be disputable"
    }
  ],

  "customer_emotion": {
    "sentiment": "neutral | mildly_frustrated | frustrated | angry",
    "indicators": ["mentioned cancellation", "all caps used", "second call this week"]
  },

  "transcript": [
    {"role": "customer", "content": "My bill is wrong this month", "at": "2026-05-13T14:25:10Z"},
    {"role": "agent", "content": "I'd be happy to help. Can I have your account ID?", "at": "2026-05-13T14:25:15Z"}
  ],

  "agent_attempts": [
    "Looked up the account and found the latest bill",
    "Checked late fees policy in KB",
    "Could not determine if the customer's case qualifies for waiver under the 1-per-year rule, need human judgment"
  ],

  "suggested_next_action": "Review the customer's waiver history in the back office system and decide whether to grant a one-time courtesy credit."
}
```

## Field-by-field description

### `escalation_id`
Unique identifier for this handoff. Used to correlate logs across systems (agent, ticketing, CRM).

### `reason_code`
Machine-readable reason for escalation. Drives routing to the right human queue (technical, billing, retention, etc.).

### `priority`
Severity:
- `low` - informational, no SLA pressure
- `medium` - standard ticket
- `high` - customer frustrated, repeated issue, or revenue-impacting
- `urgent` - safety issue, suspected fraud, or active service outage affecting the customer

### `customer.verified`
Whether the customer's identity was verified during the session (e.g. account_id confirmed against email or phone). Important for sensitive actions.

### `intent.confidence`
The classifier's confidence in the primary intent, scale 0.0 to 1.0. Helps the human judge how much to trust the routing.

### `summary`
The most important field. A short, plain-English description of the situation. The human should be able to read just this and the customer emotion and start helping in 10 seconds.

### `tools_called`
Every tool the agent invoked, in order, with abbreviated input and result. Lets the human see what data the agent already gathered without re-fetching it.

### `kb_citations`
Which knowledge base documents the agent retrieved and considered relevant. Helps the human cite the same source when responding.

### `customer_emotion.indicators`
Concrete signals the agent observed, not just a label. "Mentioned cancellation" is more useful than "frustrated."

### `transcript`
Full conversation history, oldest to newest. The human can scan or expand as needed.

### `agent_attempts`
A narrative list of what the agent tried, in plain English. Different from `tools_called` because this includes reasoning steps, not just API calls.

### `suggested_next_action`
The agent's best guess at what the human should do next. Sometimes wrong, but acts as a starting point.

## Example payload (real scenario)

A frustrated customer disputes a late fee, the agent looks up the account and the policy, but the case requires human judgment on a waiver:

```json
{
  "escalation_id": "ESC-20260513-143023-A7F2",
  "created_at": "2026-05-13T14:30:23Z",
  "reason_code": "out_of_scope",
  "priority": "medium",
  "customer": {
    "account_id": "ACC-10003",
    "phone_contact": "+1-555-100-0003",
    "name_on_file": "Maria Garcia",
    "verified": true
  },
  "session": {
    "session_id": "SESS-b3a7f9c1",
    "started_at": "2026-05-13T14:26:00Z",
    "channel": "chat",
    "language": "en"
  },
  "intent": {
    "primary": "billing",
    "secondary": ["dispute"],
    "confidence": 0.92
  },
  "summary": "Customer disputes a $10 late fee on the May bill. Says the email notification went to spam and she did not see it. Requesting a waiver. Her billing history is mostly on-time, but a waiver decision is above the agent's authority.",
  "tools_called": [
    {
      "tool_name": "get_customer_account",
      "input": {"account_id": "ACC-10003"},
      "result_summary": "Active customer since 2022, Connect plan, manual pay",
      "called_at": "2026-05-13T14:26:30Z"
    },
    {
      "tool_name": "get_billing_info",
      "input": {"account_id": "ACC-10003", "months": 3},
      "result_summary": "2 of 3 bills paid on time, current bill paid 7 days late with $10 late fee added",
      "called_at": "2026-05-13T14:27:10Z"
    }
  ],
  "kb_citations": [
    {
      "doc_id": "kb/policies/02-late-fees.md",
      "section": "Disputing a late fee",
      "relevance": "Policy allows one fee waiver per 12 months at agent's discretion. Customer's history qualifies. Decision deferred to human."
    }
  ],
  "customer_emotion": {
    "sentiment": "mildly_frustrated",
    "indicators": ["used the phrase 'this is the first time I've ever been late'", "polite but firm"]
  },
  "transcript": [
    {"role": "customer", "content": "Why is there a $10 charge on my bill?", "at": "2026-05-13T14:26:10Z"},
    {"role": "agent", "content": "I can help with that. Can you confirm your account ID?", "at": "2026-05-13T14:26:15Z"},
    {"role": "customer", "content": "ACC-10003", "at": "2026-05-13T14:26:40Z"},
    {"role": "agent", "content": "Thanks Maria. The $10 charge is a late fee from your May bill, which was paid 7 days after the due date.", "at": "2026-05-13T14:27:30Z"},
    {"role": "customer", "content": "But your email went to spam! This is the first time I've ever been late, can you remove it?", "at": "2026-05-13T14:28:15Z"}
  ],
  "agent_attempts": [
    "Verified the customer's identity by account ID",
    "Looked up account profile and 3 months of billing history",
    "Found the late fee charge and confirmed it was correctly applied per policy",
    "Confirmed the customer is eligible for a one-time courtesy waiver per the late fee policy, but waiver decisions require human approval"
  ],
  "suggested_next_action": "Apply a one-time courtesy waiver of the $10 late fee. Customer history is clean (2 of 3 recent bills on time, first late payment), and the dispute reason (spam folder) is reasonable. After waiver, suggest enrolling in autopay to prevent recurrence and save $5 per month."
}
```

## What this schema enables

- **Faster human handoff.** The rep does not start at zero.
- **Auditing.** Every escalation is a complete record. Patterns in `reason_code` and `priority` reveal where the agent struggles.
- **Evaluation.** The eval suite can grade escalation quality on whether the summary, citations, and suggested_next_action are useful, not just whether the escalation happened.
- **Continuous improvement.** When the agent escalates an `unresolved_ambiguity`, that becomes a training signal for the classifier.
