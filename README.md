# TelSano Customer Service Copilot

[![Tests](https://github.com/Git-Hub-Ran/telecom-ops-copilot/actions/workflows/tests.yml/badge.svg?branch=Main)](https://github.com/Git-Hub-Ran/telecom-ops-copilot/actions/workflows/tests.yml)

TelSano Copilot is a customer service AI agent for a US telecom provider. It handles
inbound customer queries across four domains (billing, account management, technical
support, and general information) through a deterministic 5-state pipeline backed by
Azure AI Foundry agents. Routing, tool execution, escalation, and response generation
are fully automated; a Streamlit chat interface exposes the pipeline for direct
customer interaction.

The project demonstrates a deterministic single-orchestrator pipeline with a documented
path to production: strict separation between deterministic routing (pure Python) and
model-dependent work (Foundry agents), structured JSON logging throughout, and a
100-query golden set eval with measurable pass/fail criteria.

## Architecture

Each customer message passes through five states in sequence:

1. **ClassifyState** (gpt-4o-mini Foundry agent): detects intent (billing, technical,
   account, info, escalate, or unknown), confidence score, detected emotion, and
   off-topic flag.
2. **RouteState** (pure Python, no LLM): maps ClassifyOutput to a RoutingDecision
   enum value using priority rules. Unknown intent routes to a clarifying question.
   Injection attempts do not follow a single path. Of the five in the golden set,
   two route to escalation, one is refused by the off-topic rule, and two
   (ADV-002, ADV-004) classify as `unknown` and receive a clarifying question;
   see Known constraints below.
3. **ActState**: calls Python tool functions directly for billing, account, and
   technical paths; invokes a gpt-4o Foundry agent with file_search for info queries.
4. **EscalateState** (gpt-4o Foundry agent): assembles and persists a human handoff
   ticket when ActState returns unresolved or when routing bypasses Act entirely.
5. **RespondState** (gpt-4o Foundry agent): generates the final customer-facing
   message from the full context accumulated across prior states.

**Key technology choices:**
- Azure AI Foundry: agent hosting, runs, and file_search KB retrieval
- Azure OpenAI gpt-4o-mini: intent classification (latency-sensitive, lower cost)
- Azure OpenAI gpt-4o: act, escalate, and respond agents
- Streamlit: chat UI with session state and conversation history
- Pydantic v2: data models and config validation
- DeviceCodeCredential: interactive auth that works in all environments

RouteState is the only stateless, model-free component. It applies priority rules
to map ClassifyOutput to a RoutingDecision enum value. Unknown intent routes to a
clarifying question. Injection attempts do not follow a single path: of the five in
the golden set, two route to escalation, one is refused because the off-topic rule
outranks intent, and two (ADV-002, ADV-004) classify as `unknown` and receive a
clarifying question. No path complies with the injection, and a regression test pins
that for both classifier outcomes.

## Quick start

**Requirements:** Python 3.12+

```bash
pip install -r requirements.txt
```

Create a `.env` file in the project root:

```
AZURE_FOUNDRY_PROJECT_ENDPOINT=https://<project>.api.azureml.ms/...
AZURE_TENANT_ID=<your-tenant-id>
VECTOR_STORE_ID=<your-vector-store-id>
```

All other settings have defaults. See `src/config.py` for the full config schema.

**First run:** On startup, AgentFactory creates the four Foundry agents automatically
using get-or-create semantics (list agents by name; create only if absent). No manual
agent provisioning is required. Authentication uses Device Code flow; follow the
terminal prompt to sign in.

```bash
streamlit run src/ui/app.py
```

**Updating prompts:** Foundry agents are retrieved by name. After changing a system
prompt in `src/orchestrator/agents/prompts.py`, delete the corresponding agent in the
Azure Foundry portal so it is recreated with the updated instructions on the next run.
Agent names: `classifier-agent`, `act-agent`, `escalate-agent`, `respond-agent`.

**Tests:** No Azure credentials required. Every test uses mocks.

```bash
pytest tests/
```

## Screenshots

**Welcome screen**
![Welcome](docs/screenshots/welcome.png)

**KB-grounded answer with citations**
![KB answer](docs/screenshots/info_kb.png)

**Billing query with formatted amounts**
![Billing](docs/screenshots/billing.png)

**Escalation with ticket reference**
![Escalation](docs/screenshots/escalation.png)

## Eval results

Baseline evaluation against a 100-query golden set (standard and adversarial queries).
Full analysis in [`eval/BASELINE_NOTES.md`](eval/BASELINE_NOTES.md).

| Metric | Score | Target | Status |
|---|---|---|---|
| Intent accuracy | 89.0% | >=90% | FAIL |
| Tool selection | 82.0% | >=85% | FAIL |
| Escalation precision | 92.3% (12/13, small-n) | >=85% | PASS |
| Escalation recall | 85.7% (12/14, small-n) | >=80% | PASS |
| Latency p95 | ~16s | <=5s | FAIL (structural, see below) |
| Deflection rate | 92.9% | 30-40% | -- |

Figures are from run 9 (2026-08-29), the first run in which all four deployed Foundry
agents matched their committed prompts. Its scored metrics are identical to run 8.
The committed notebook holds this run's outputs, so its cells show the same figures.
See [`eval/BASELINE_NOTES.md`](eval/BASELINE_NOTES.md) for the run history and the
variance discussion.

Intent accuracy uses exact label matching. Of the five injection attempts, two route
directly to a human agent and one is refused as off-topic. Two (ADV-002, ADV-004)
are classified as `intent="unknown"` in every run measured so far and route to
a clarifying question instead. A third (ADV-001) classified as `unknown` in the
2026-08-11 run and `escalate` in every run since, on identical input, which is
why escalation recall moved from 78.6% (FAIL) to 85.7% (PASS) between the first two
runs with no code or prompt change. No route complies with the injection, so the
operational outcome is safe either way, but on a 14-row escalation sample a single
classification flip moves recall by roughly 7 points. See
[`eval/BASELINE_NOTES.md`](eval/BASELINE_NOTES.md) for the run-to-run variance
discussion before citing these figures.

Remaining intent failures are hard adversarial cases (extreme vagueness,
multi-intent queries, abusive phrasing) and genuine boundary ambiguities between
`info`, `account` and `billing`, which are the rows that flip between runs. Tool
selection failures follow directly from intent misclassification. Full analysis in
[`eval/BASELINE_NOTES.md`](eval/BASELINE_NOTES.md).

## Known constraints

**Latency:** p50 is approximately 8s; p95 is approximately 16s. A turn requires one
to four sequential Foundry agent runs depending on the path, and each run involves
polling until completion (create thread, post message, start run, poll, fetch
response). The spread is what separates p50 from p95: a refusal or clarifying
question needs only the classifier and returns in about 3s, inside the target, while
an unresolved KB query runs four agents in sequence. The 5s p95 target
requires replacing the polling Agents API with streaming Azure OpenAI Chat Completions
for agents that do not use file_search. This is a documented architectural tradeoff,
not a tuning problem.

**Model deprecation:** gpt-4o and gpt-4o-mini retire October 1 2026. Before that
date, update `CLASSIFIER_MODEL`, `ACT_MODEL`, `ESCALATE_MODEL`, and `RESPOND_MODEL`
in `.env` to point to supported model deployments.

**Intent accuracy ceiling:** Further refinement of the classifier prompt risks
regressions on boundary cases. Injection attempts are never complied with: they
route to escalation, to a refusal, or to a clarifying question, and a regression test
pins this for both classifier outcomes. The cases that route to clarification rather
than escalation are counted as escalation-recall false negatives; that count was 3 on
2026-08-11 and 2 in every run since, because ADV-001 flipped from `unknown` to
`escalate` and has stayed there. Recall should still be read as a range given the
sample size.

**No identity verification:** account IDs are accepted from customer messages without authentication.

## Project structure

```
src/
  config.py                    Pydantic settings, loaded from .env
  orchestrator/
    state_machine.py           5-state pipeline coordinator
    states/                    One module per state (classify, route, act, escalate, respond)
    agents/
      factory.py               Get-or-create Foundry agent provisioning
      prompts.py               System prompts for all four agents
    models/                    Pydantic data models (StateContext, SessionState, etc.)
    observability/
      structured.py            Structured JSON logging to stdout (FR-047 to FR-052)
  tools/                       Python tool functions (billing, account, diagnostic, outage, escalation)
  data/
    billing_data_source.py     BillingDataSource Protocol, with JSON and SQLite implementations
  ui/
    app.py                     Streamlit chat interface

tests/                         Unit test suite, no Azure dependency
eval/
  golden_set.csv               100-query evaluation set
  BASELINE_NOTES.md            Eval scores and failure analysis
  results_*.csv                Committed results, one per run
kb/                            Knowledge base searched by the info path (17 documents, 4 folders)
scripts/
  score_eval.py                Scores a results CSV against thresholds or a prior run
  check_style.py               Enforces the CLAUDE.md style rule, runs in CI
mock-data/                     JSON fixture files for tool functions
notebooks/
  03-evaluation.ipynb          End-to-end eval runner
.github/workflows/tests.yml    CI: tests, style check, eval scoring integrity
docs/
  ARCHITECTURE.md
  BUSINESS_CASE.md
  CAPSTONE_ASSESSMENT.md
  DEPLOYMENT.md
  ESCALATION_SCHEMA.md
  EVAL.md
  KB_NOTES.md
  PLAN.md
  TROUBLESHOOTING.md
  WRITEUP.md
  screenshots/                 UI screenshots embedded above
```

**Documentation:** [ARCHITECTURE.md](docs/ARCHITECTURE.md) ·
[BUSINESS_CASE.md](docs/BUSINESS_CASE.md) ·
[CAPSTONE_ASSESSMENT.md](docs/CAPSTONE_ASSESSMENT.md) ·
[DEPLOYMENT.md](docs/DEPLOYMENT.md) ·
[ESCALATION_SCHEMA.md](docs/ESCALATION_SCHEMA.md) ·
[EVAL.md](docs/EVAL.md) ·
[KB_NOTES.md](docs/KB_NOTES.md) ·
[PLAN.md](docs/PLAN.md) ·
[TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) ·
[WRITEUP.md](docs/WRITEUP.md) ·
[screenshots/](docs/screenshots)
