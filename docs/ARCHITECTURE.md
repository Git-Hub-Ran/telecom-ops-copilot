# Architecture

## System overview

TelSano Copilot is an AI-assisted customer service agent for a US telecom
provider. It handles inbound customer queries across four domains: billing,
account management, technical support, and general information. Each query
passes through a deterministic five-state pipeline backed by Azure AI Foundry
agents. The system is designed for single-session, single-user interactions:
a customer types a query, the pipeline processes it, and the agent replies.
Escalation to a human agent is handled automatically when the pipeline cannot
resolve the query or when the customer's intent signals that a human is needed.

---

## The five-state pipeline

Each customer message passes through exactly these states in sequence. States
do not loop or branch back; the pipeline is a directed graph with one path
per routing decision.

### ClassifyState

**Input:** Raw customer message, conversation history (rolling window of up
to 10 turns).

**Output:** `ClassifyOutput`: intent label (`billing`, `technical`,
`account`, `info`, `escalate`, or `unknown`), confidence score (0.0-1.0),
detected emotion, and an off-topic flag.

**Technology:** gpt-4o-mini Foundry agent. The classifier runs a structured
JSON prompt that enforces a single-label intent decision and a numeric
confidence score. Boundary rules in the system prompt handle the most common
ambiguous cases (e.g. eligibility questions, policy questions).

**Why this state exists:** Downstream states need to know which tool to call
and whether the query should bypass the standard flow entirely. Separating
classification from routing makes both independently testable.

---

### RouteState

**Input:** `ClassifyOutput` from ClassifyState.

**Output:** `RoutingDecision` enum value: one of `BILLING_PATH`,
`TECHNICAL_PATH`, `ACCOUNT_PATH`, `INFO_PATH`, `SKIP_TO_ESCALATE`,
`ASK_CLARIFYING_QUESTION`, or `REFUSE_OFF_TOPIC`.

**Technology:** Pure Python. No LLM involved.

**Priority rules (applied in order):**
1. Off-topic flag set: route to `REFUSE_OFF_TOPIC`.
2. Intent is `escalate`: route to `SKIP_TO_ESCALATE`. This ensures explicit
   escalation requests and prompt injection attempts (classified as `escalate`
   by the classifier) always reach a human agent before the confidence gate.
3. Intent is `unknown`: route to `ASK_CLARIFYING_QUESTION`. Unknown means the
   classifier could not determine what the customer wants.
4. Confidence below threshold (default 0.6): route to `ASK_CLARIFYING_QUESTION`.
5. Otherwise: route to the path matching the intent label.

**Why this state exists as pure Python:** Routing logic is policy, not
inference. It must be deterministic, auditable, and fast. Making it pure
Python means it can be unit-tested exhaustively without mocking an LLM, and
it adds zero latency.

---

### ActState

**Input:** `RoutingDecision`, original customer message, account context.

**Output:** Tool results and/or a structured `ActOutput` with resolution
status and any data retrieved.

**Technology:** Direct Python function calls for `BILLING_PATH`,
`TECHNICAL_PATH`, and `ACCOUNT_PATH`. For `INFO_PATH`, a gpt-4o Foundry
agent with `file_search` retrieves answers from the knowledge base vector
store. For `SKIP_TO_ESCALATE` and `REFUSE_OFF_TOPIC`, ActState is bypassed.

**Tools available:**
- `get_billing_info(account_id, months)`: retrieves billing history via
  the configured DataSource backend
- `get_customer_account(account_id)`: retrieves account details from mock data
- `run_speed_diagnostic(account_id)`: returns diagnostic results from mock data
- `check_network_outage(zip_code)`: checks for active outages by zip code
- `create_escalation_ticket(...)`: creates a structured handoff ticket

---

### EscalateState

**Input:** Full pipeline context accumulated so far.

**Output:** A persisted escalation ticket with account context, detected
intent, conversation summary, and a suggested action for the human agent.

**Technology:** gpt-4o Foundry agent. The escalation agent reads the full
context and writes a structured handoff summary. This state runs when
ActState returns unresolved, when RouteState sends `SKIP_TO_ESCALATE`, or
when the customer's intent is explicitly `escalate`.

---

### RespondState

**Input:** Full pipeline context including ActState results and any escalation
ticket.

**Output:** Final customer-facing message as plain text.

**Technology:** gpt-4o Foundry agent. The respond agent synthesizes the
context into a single coherent reply appropriate for the routing outcome:
either a data-driven answer (billing, account, technical), a knowledge base
citation (info), or an escalation confirmation.

---

## Key architectural decisions

### Single orchestrator vs multi-agent system

TelSano uses a single orchestrator with a deterministic state machine rather
than a multi-agent system. This was a deliberate choice based on the
characteristics of the problem.

**Why the state machine is correct here:**

A customer service query for a telecom provider follows a predictable
sequential flow: classify the intent, decide on a path, execute the relevant
tools or retrieve information, handle escalation if needed, reply. There is
no inherent parallelism in this flow. The classify step must complete before
routing is possible. The act step must complete before a coherent response
can be generated. Introducing parallel agents would add coordination overhead
without reducing latency or improving quality.

The routing logic itself is policy-driven and well-understood. The conditions
under which a query should escalate are known in advance and can be expressed
as priority rules in pure Python. Delegating this decision to an LLM planner
would introduce non-determinism in exactly the place where determinism matters
most: safety routing (prompt injection, unrecognized intents) must always
produce the same outcome.

The state machine also makes the system straightforward to test. Each state
has clearly defined inputs and outputs. RouteState is comprehensively unit
tested without a single LLM mock. ActState tool calls are pure Python
functions tested against fixture data.

**When a multi-agent architecture would be the right choice:**

A multi-agent system becomes appropriate when the problem has structural
parallelism or requires dynamic agent selection that cannot be specified in
advance.

Concrete examples where this would apply:

- *Parallel data retrieval:* A billing dispute that requires fetching the
  customer's bill, their account standing, and current network status
  simultaneously. A coordinator agent could fan out to three specialized
  agents and merge the results, reducing latency.

- *Specialized agent teams:* A support system that routes to fundamentally
  different agent implementations depending on product line (mobile vs home
  internet vs enterprise), where each specialist has different tools, a
  different knowledge base, and different escalation criteria.

- *Dynamic agent selection:* A system where the set of available agents
  changes at runtime (e.g. seasonal agents, A/B tested variants, agents with
  different capability tiers for different customer segments).

- *Long-running multi-step tasks:* An account migration workflow that spans
  multiple API calls, requires human approval at intermediate steps, and
  persists state across days. This is better modeled as an agent graph than
  a single sequential pipeline.

None of these apply to TelSano as currently scoped. The routing decision
space is known and finite. The tools are synchronous and fast relative to
the LLM latency. Parallelism would not materially improve the user-perceived
response time given that RespondState always needs the full context before
generating a reply.

---

### RouteState as pure Python

RouteState contains no LLM call. It applies a small set of priority rules
to map a `ClassifyOutput` to a `RoutingDecision`. The rules are expressed
as a series of `if` conditions ordered from highest to lowest priority.

This design has three advantages. First, it is fast: RouteState adds
effectively zero latency. Second, it is auditable: the routing decision for
any input can be derived by reading the code, without running an inference
call. Third, it is testable: RouteState has exhaustive unit tests covering
every combination of intent, confidence, and flag values. These tests run
in milliseconds with no external dependencies.

The most critical routing rule is that `escalate` intent routes to
`SKIP_TO_ESCALATE` before the confidence gate. Prompt injection attempts are
classified as `intent="escalate"` by the classifier and reach a human agent via
this path. `unknown` intent routes to `ASK_CLARIFYING_QUESTION`; the injection
defence relies on the classifier labelling attacks as `escalate`, not on the
unknown routing path. These properties would not be guaranteed if routing were
delegated to an LLM.

---

### gpt-4o-mini for classification, gpt-4o for other agents

ClassifyState uses gpt-4o-mini. All other agents use gpt-4o.

Classification is latency-sensitive (it is the first step) and the task is
structured: produce one of six intent labels and a numeric confidence score.
gpt-4o-mini handles structured JSON output reliably at roughly one-third the
cost and significantly lower latency than gpt-4o.

The other agents (act INFO_PATH, escalate, and respond) require more nuanced
generation: synthesizing knowledge base results, writing a structured
escalation summary, or generating a customer-facing reply that is appropriate
in tone for the routing outcome. These tasks benefit from gpt-4o's stronger
instruction following and generation quality. The latency difference matters
less here because these agents run later in the pipeline, after the
classification result is already in hand.

---

### DataSource abstraction for billing

`get_billing_info` reads billing records through a `BillingDataSource`
Protocol rather than directly from a file. Two implementations exist:
`JSONBillingDataSource` reads from `mock-data/billing.json` and
`SQLiteBillingDataSource` reads from `data/billing.db`. A factory function
in `billing.py` selects the implementation at runtime based on
`BILLING_DATA_SOURCE` in config.

The abstraction exists to separate the tool's public interface from its data
access mechanism. The `get_billing_info` function signature, return type, and
error behaviour are unchanged regardless of which backend is active.

In a production deployment, migrating from mock data to a real billing API
would mean adding a third implementation of the Protocol (for example,
`APIBillingDataSource` that calls a real billing service) and setting
`BILLING_DATA_SOURCE=api` in config. No changes to `get_billing_info`, its
callers, or its tests would be required. The existing JSON and SQLite
implementations remain available for local development and testing without
API credentials.

The same pattern can be applied to any tool that reads from external data:
account management, diagnostic history, outage data. The Protocol approach
(using `typing.Protocol` with `@runtime_checkable`) was chosen over ABC
because it imposes no inheritance requirement on implementing classes, making
it easier to mock in tests and easier to introduce new implementations
without modifying existing code.

---

## What this system does not do

These are deliberate scope boundaries, not implementation gaps.

**No cross-session memory.** Each conversation is stateless from the
pipeline's perspective. The rolling conversation window (up to 10 turns) is
maintained within a single Streamlit session but is not persisted. A
returning customer who starts a new session has no continuity with prior
interactions.

**No real customer database.** Account data (`get_customer_account`), diagnostic
results (`run_speed_diagnostic`), and outage data (`check_network_outage`) all read
from JSON fixture files in `mock-data/`. Billing data can optionally use a
local SQLite database seeded from the same fixtures. None of these connect to
a production system.

**No production authentication.** The app uses Azure Device Code flow, which
requires interactive browser sign-in on each startup. This is appropriate for
a development and demonstration environment. A production deployment would
replace this with a non-interactive credential (Managed Identity, client
secret, or workload identity federation) and would add customer-facing
authentication for the Streamlit interface.

**No identity verification.** Account IDs are extracted from customer
messages without any authentication check. The escalation ticket hardcodes
`verified=False` to reflect this honestly. A production deployment would
verify the customer against name, phone, or an authenticated session before
setting this field.

**Account ID extraction.** The pipeline extracts account IDs matching the
pattern ACC-XXXXX from each customer message and stores them in session state.
Once set, the account ID persists across turns and is not overwritten by
subsequent messages.

**Latency constraint from Foundry polling architecture.** The p95 latency is
approximately 20 seconds. Each Foundry agent run requires at minimum four
HTTP round trips: create thread, post message, start run, poll until complete,
fetch response. With two to three sequential agent runs per query, the latency
budget is dominated by this polling overhead. Reaching sub-5s p95 would
require replacing polling-based Foundry agents with streaming Azure OpenAI
Chat Completions for agents that do not use `file_search`, and a separate
vector search step for the INFO_PATH. This is a significant architectural
change and is deferred.

---

## Extension paths

### Adding a new tool domain

Add a new tool function in `src/tools/`, add the corresponding routing case
to RouteState, and wire it into ActState. The pipeline structure does not
change. Follow the DataSource pattern for any tool that reads external data
to keep the tool decoupled from its data access mechanism.

### Moving to a multi-agent architecture

If the problem evolves to require parallel data retrieval or dynamic agent
selection, the natural extension point is RouteState. RouteState currently
returns a single `RoutingDecision`; it could be extended to return a list of
decisions (for fan-out) or a coordinator agent specification (for dynamic
selection). The classify-then-route pattern at the front of the pipeline
would remain unchanged.

### Adopting the DataSource pattern for other tools

Any tool that currently reads directly from a file in `mock-data/` can adopt
the DataSource pattern by:

1. Defining a Protocol with a single `get_*` method returning `list[dict]`.
2. Implementing a `JSON*DataSource` that wraps the existing file read.
3. Implementing a production implementation (API, database, etc.).
4. Adding a factory function and config field to select the implementation.

This keeps mock data available for local development and tests while enabling
a clean production migration path.
