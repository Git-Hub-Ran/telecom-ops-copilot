# Business Case: Telecom Operations Copilot

This document answers the question: why is this project worth doing? An agentic system has to target a real business problem, not just demonstrate that the technology works.

## The problem in operational terms

US telecom carriers run customer support at a scale that makes it a primary cost center. Sourced from public industry data (Gartner, Zendesk benchmarks, Salesforce State of Service reports):

- Average handle time (AHT) per support contact: 6 to 12 minutes
- Cost per contact: $5 to $15, depending on channel (voice is more expensive than chat)
- 60 to 70 percent of contacts are tier 1: billing questions, account lookups, simple troubleshooting
- 30 to 40 percent of tier 1 contacts can theoretically be deflected to AI assistance

Translated: a mid-size US telecom (50,000 subscribers, around 5,000 monthly support contacts) spends approximately $30,000 to $50,000 per month on tier 1 customer support alone. Even modest improvements in deflection or AHT compound to meaningful annual savings.

## Who is the user

The primary user of the Operations Copilot is the **support team at a mid-size US telecom**, not the end customer.

This is a deliberate scoping choice:

- The agent is a "copilot" for human reps, not a customer-facing chatbot
- Lower risk: a human is in the loop for any consequential action
- Easier to measure: existing AHT and deflection metrics give a clean baseline
- Faster iteration: reps can give structured feedback that a customer would not

The future expansion path is a customer-facing version with stricter safety controls. That is out of scope for this initial release.

## Target KPIs

These numbers are locked before optimization starts. Targets are calibrated against industry benchmarks for AI-assisted customer support deflection and handle-time reduction.

| KPI | Target | Justification |
|---|---|---|
| Deflection rate on simple queries | 30 to 40 percent | Industry benchmark range for AI-assisted tier 1 workloads (Gartner, Zendesk) |
| Handle time reduction on escalated cases | 20 percent | Typical impact of structured handoff and pre-fetched data |
| Intent classification accuracy | over 90 percent | Floor for reliable deflection: if classification is wrong, downstream routing fails |
| Tool selection correctness | over 85 percent | Once classification is right, the right tool must be called |
| Grounding faithfulness (RAGAS) | over 0.90 average | Customers and reviewers need to trust the answer |
| Escalation precision | over 85 percent | Avoid escalating cases the agent should handle |
| Escalation recall | over 80 percent | Catch the cases that need a human |
| Average response latency | under 5 seconds | UX threshold for chat-based support |

### What these numbers mean in practice

- 30 to 40 percent deflection on simple queries means: out of 100 routine tier 1 contacts, the copilot fully resolves 30 to 40 without human involvement. The remaining 60 to 70 go to humans, possibly with the agent having pre-fetched data and a summary.
- 20 percent AHT reduction on escalated cases means: the average resolution time on the cases that do reach a human drops from 8 minutes to 6.4 minutes, because the rep starts with context already gathered.

## ROI sketch (illustrative, not audited)

For a mid-size telecom with 50,000 subscribers receiving 5,000 monthly support contacts:

**Tier 1 contacts**: 65 percent of total = 3,250 monthly

**Direct deflection (35 percent of tier 1)**:
- 1,138 contacts handled by the copilot without human involvement
- At 8 minutes average human handling time, that is 9,100 minutes saved per month
- At a fully-loaded rep cost of $25 per hour, that is ~$3,800 per month

**AHT reduction on remaining contacts** (4,000 contacts at 8 minutes, 20 percent reduction):
- 1.6 minutes saved per contact = 6,400 minutes saved per month
- At $25 per hour, that is ~$2,700 per month

**Combined**: ~$6,500 per month, or **~$78,000 per year** in support cost reduction for a single mid-size telecom.

This is back of the envelope. Real ROI depends on call mix, channel costs, and rep utilization. The point of the math is that the order of magnitude justifies the project. A typical AI-assist initiative for a mid-size telecom would target this kind of impact.

## Why an agentic approach (not chatbot, not RAG)

The problem cannot be solved by simpler architectures:

- **A FAQ chatbot** cannot look up customer-specific data. It can answer "how does autopay work" but not "is my autopay set up correctly".
- **Pure RAG over a KB** cannot call tools. It cannot fetch the customer's current bill or check for an active outage in their area.
- **A single big prompt** cannot reliably produce structured escalation payloads or maintain multi-turn state. It also has no clear stop condition.
- **An IVR or rule-based workflow** cannot handle the variability of natural customer input. Customers write things like "my net's busted lol can u just fix it pls" and the system has to figure out what is being asked.

Agentic systems combine: classification + retrieval + tool calling + decision making + structured output. Managed agent platforms (Foundry, OpenAI Agents) provide the runtime for this combination. The project uses one (Azure AI Foundry Agent Service) so it can focus on the orchestration and evaluation rather than building the runtime from scratch.

## Scope boundaries

### In scope

- 5 intent categories: info, account, billing, technical, escalation
- 1 built-in retrieval tool (Foundry file search) + 5 custom Azure Functions
- Single-session memory (no cross-session persistence)
- English language only
- US-style telecom (fictional company TelSano)
- Synthetic customer data, 20 accounts
- One human escalation path (mocked, not connected to a real ticketing system)
- Chat channel only

### Out of scope (acknowledged limitations)

- Voice channel
- Multilingual support
- Long-term user memory across sessions
- Authentication beyond a self-declared account_id (no real identity verification)
- Real CRM or ticketing integration (escalations go to a mock destination)
- Compliance and PII redaction beyond what Foundry content safety provides
- Active learning from rep feedback (this version delivers one-shot eval, not a learning loop)
- Multi-specialist routing (escalations all go to one queue, not split across billing vs technical reps)

### What this means for the demo

The demo is a working agent that handles the in-scope cases, with the eval suite showing measured performance against the locked KPIs. The out-of-scope items are documented but not implemented. Reviewers can see clearly what was built and what is a known limitation.
