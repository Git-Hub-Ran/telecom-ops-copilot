# Telecom Operations Copilot - Capstone Plan

> Built on Azure, with my earlier RAG work as a reference: [rag-api-azure](https://github.com/Git-Hub-Ran/rag-api-azure)

---

## Project summary

| Field | Decision |
|---|---|
| **Domain** | Telecom customer service |
| **Company** | TelSano (fictional) |
| **Language** | English only |
| **Frontend** | Streamlit on Hugging Face Spaces (free) |
| **Backend** | Azure (Functions + Blob + OpenAI + Chroma) |
| **Memory** | Session based (Streamlit session_state) |
| **Daily effort** | 3 to 4 hours per day for 14 days, around 50 hours total |
| **Cost** | Effectively zero. HF Spaces free, Azure free tier plus minimal token usage |

---

## 1. Problem framing

Telecom support reps spend hours daily on repetitive tasks: account lookups, bill explanations, outage checks, basic troubleshooting. Customers wait long for simple answers, and every escalation forces them to re-explain context.

The agent solves this by:

- Handling routine inquiries autonomously
- Calling internal tools to fetch real data
- Citing policy when answering questions
- Escalating only when needed, with structured context so humans do not start cold

Why it is a strong capstone:

- Requires more than one prompt
- Forces real architectural decisions (when to retrieve, when to call a tool, when to stop)
- Bounded domain (telecom only)
- Measurable success metrics

---

## 2. User workflow

1. Customer opens Streamlit chat
2. Sends a message (optionally with account ID)
3. Agent classifies intent, decides routing, executes, and responds
4. UI sidebar shows in real time: classification, tools called, citations, escalation status
5. Session memory persists across turns. Customer says "I am John, account 12345" once, agent remembers

---

## 3. Architecture

```
Customer
   |
   v
Streamlit chat UI (Hugging Face Spaces)
   |
   | HTTPS POST /ask
   v
+----------- Azure Function backend ------------+
|                                                |
|   Intent classifier (gpt-4o-mini)              |
|        |                                       |
|        v                                       |
|   +--------+-------------+-------------+      |
|   |        |             |             |      |
|   v        v             v             v      |
|  RAG    Tool calls   Escalation               |
|   |        |             |                    |
|   +--------+-------------+                    |
|        |                                       |
|        v                                       |
|   Response generator (gpt-4o)                  |
|                                                |
+------------------------------------------------+
   |
   | JSON response
   v
Customer
```

---

## 4. Models and tools

### LLM choices

- **gpt-4o-mini** for intent classification. Cheap, fast (around 50ms)
- **gpt-4o** for final response generation. Quality matters here

### Orchestration

Use **native Azure OpenAI function calling**, not LangChain agents. Less magic, more control, much easier to evaluate.

### Tool list (6 functions)

| Tool | Input | Output |
|---|---|---|
| `search_kb(query)` | string | top k chunks plus sources |
| `get_customer_account(account_id)` | string | profile, plan, status |
| `get_billing_info(account_id, months)` | string, int | charges, due dates |
| `check_network_outage(zip_code)` | string | active outages |
| `run_speed_diagnostic(account_id)` | string | mock test result |
| `create_escalation_ticket(account_id, issue, priority)` | string, string, enum | ticket ID, ETA |

---

## 5. Data layer

### Knowledge base (Azure Blob to Chroma)

About 30 to 50 markdown documents covering:

- 5 to 7 plan offerings (price, features, fair use)
- Billing policies (late fees, autopay, prorated bills)
- Troubleshooting guides (internet, mobile, TV, voicemail)
- Cancellation and retention policy
- Roaming and international rates
- Equipment guides (modems, routers)

### Mock databases (JSON in Function App)

- **20 customer accounts** with varied scenarios (new, long tenure, late payment, premium, suspended)
- **60 billing records**: 3 months times 20 customers
- **5 to 10 active outages** keyed by zip code
- **Diagnostic results** as predefined response sets

All synthetic but realistic. Generated with Claude or GPT, then reviewed manually.

---

## 6. Evaluation framework

### Golden test set

80 to 100 tickets in CSV with ground truth columns:

- `query` (natural language)
- `expected_intent`
- `expected_tool` (or "rag" or "escalate")
- `expected_escalation` (bool)
- `gold_answer_summary` (for faithfulness check)

### Metrics

| Metric | Target | How |
|---|---|---|
| Intent classification accuracy | over 90 percent | Exact match vs ground truth |
| Tool selection accuracy | over 85 percent | Right tool called for right query |
| Answer faithfulness (RAG) | over 90 percent | RAGAS in Colab |
| Escalation precision and recall | over 85 percent / over 80 percent | Confusion matrix |
| Average response latency | under 5 seconds | End to end timing |

The Colab notebook becomes the evaluation artifact for the capstone deliverable.

---

## 7. Failure cases. Test these deliberately

- **Multi-intent**: "lower my bill AND my internet is slow". Should handle both
- **Off-topic**: "what is the weather?". Should refuse gracefully
- **Hallucination**: question about a non existent plan. Should say "no such plan"
- **Wrong account_id format**: should ask for clarification, not crash
- **Memory failure**: forgets info from earlier in conversation. Known anti pattern to test
- **Empty RAG**: no good match in KB. Should admit "I do not know" instead of fabricating

> The capstone brief says: *"At this stage, you should already know where the system breaks. If you do not, you are not testing hard enough."*

---

## 8. Roadmap. 2 weeks, around 50 hours

### Week 1: Foundation

**Day 1 to 2 (6 to 8 hours): Data generation**

- Write 30 to 50 KB markdown files (generate with AI, review manually)
- Build 20 account mock customer DB as JSON
- Create outage and diagnostic mock data
- Upload to Azure Blob

**Day 3 (3 to 4 hours): Adapt existing RAG**

- Fork or extend `shared_rag.py` to telecom domain
- Test retrieval on 10 sample queries
- Verify chunk quality and citation accuracy

**Day 4 to 5 (6 to 8 hours): Orchestration core**

- Intent classifier function (gpt-4o-mini)
- Tool definitions in OpenAI function calling format
- Mock tool implementations
- Routing logic. Classifier output to tool selection
- Integrate with existing Function App

**Day 6 to 7 (6 to 8 hours): Streamlit UI**

- Chat interface with message history
- Sidebar showing classification, tools called, citations
- Session state for memory
- Deploy to Hugging Face Spaces
- Connect to Azure Function endpoint
- End to end smoke test

### Week 2: Refinement

**Day 8 to 9 (6 to 8 hours): Multi-turn and escalation**

- Session memory across turns (Streamlit state)
- Escalation flow with structured context
- Handle multi-intent queries
- Edge cases (ambiguous account ID, partial info)

**Day 10 to 11 (6 to 8 hours): Evaluation**

- Build 80 to 100 golden test set CSV
- Colab evaluation notebook
- Run baseline metrics
- Identify top failure modes

**Day 12 to 13 (6 to 8 hours): Iteration**

- Fix top 3 to 5 failure modes
- Improve prompts based on eval results
- RAG tuning (chunk size, k, reranking)
- Re-run evals. Show improvement curve

**Day 14 (3 to 4 hours): Polish**

- README with architecture diagram
- Demo screenshots or video
- Project Update document (the capstone deliverable)

---

## Deliverable at end of Week 2

Per the capstone brief, the Project Update covers:

1. The problem being solved
2. The user workflow
3. The architecture
4. The model and tool choices
5. The data or retrieval layer
6. Early results
7. Early failure cases

All seven sections are covered by the work above.

---

## Open questions to revisit during build

- Whether to add cross-session memory (user specific) as a bonus in week 2
- Whether to add a "supervisor" LLM that double checks escalation decisions
- Whether to expose the orchestrator's decisions in the UI for transparency (recommended)
- Whether to add a feedback widget (thumbs up or down) to start gathering eval data live
