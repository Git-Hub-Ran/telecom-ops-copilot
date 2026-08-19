# Eval Baseline Notes

## Baseline eval dates

Original baseline: July 1, 2026. Updated after decontamination and label fixes:
August 11 and August 18, 2026 (see the variance section below). All runs use the
full 100-query golden set (`eval/golden_set.csv`).

## Final scores

| Metric | Score | Target | Status |
|---|---|---|---|
| Intent accuracy | 88% | >=90% | FAIL |
| Tool selection | 82.0% | >=85% | FAIL |
| Escalation precision | 92.3% (12/13, small-n) | >=85% | PASS |
| Escalation recall | 85.7% (12/14, small-n) | >=80% | PASS |
| Latency p95 | ~17s | <=5s | FAIL |
| Grounding faithfulness | not computed | >=0.90 | -- |
| Deflection rate | 92.9% | 30-40% | -- |

All figures are from run 4 (2026-08-19 11:10), the most recent run and the first
with citation validation active. Intent accuracy and tool selection are one query
below run 3 (89% and 82.5%), within the run-to-run variance documented below.
Escalation figures are unchanged from run 3 but vary between runs; see
"Run-to-run variance on escalation metrics" below before citing them.

Grounding faithfulness is a required gate in docs/EVAL.md but has never been
computed; the grounding_score column is empty in all nine committed results CSVs.
See "Grounding faithfulness" in docs/EVAL.md for the toolchain reason and what
computing it would require.

Run 3 (2026-08-18 12:29) was the first run against the fully decontaminated
classifier prompt (commit 22d3a18), which replaced example queries that were
paraphrase-adjacent to five golden set rows with topics absent from the golden set
entirely. Intent accuracy across the full decontamination history reads 86% on the
July 1 run against the contaminated prompt, 88% once the verbatim queries were
replaced with paraphrases, 89% on run 3 with the disjoint-topic prompt, and 88%
again on run 4. Removing the contaminated examples cost nothing measurable, which
is consistent with the earlier gain reflecting genuine classification rather than
memorisation. The 1-point spread across runs 2 through 4 is a single query and sits
within the run-to-run variance documented below, so this is evidence against
inflation rather than proof of its absence.

Deflection rate note: the denominator is standard queries only (70 queries). A
query is deflected when the agent handles it without escalation. 92.9% means
65 of 70 standard queries were handled without escalation. The figure is high
because info queries (20 of 70) never escalate by design; they are answered
from KB content rather than routed to a human. The 30-40% target assumes a
production query mix where escalation-prone intents (technical failures, billing
disputes) are more prevalent than in this eval set. Status is unmarked because
the metric is informational for this eval run; the target applies to production
traffic.

Tool selection is capped structurally, not by classification quality. Of the 27 rows
scoring below 1.0 in run 4, 18 score exactly 0.5 because `_run_technical` invokes all
three technical tools (`get_customer_account`, `check_network_outage`,
`run_speed_diagnostic`) in sequence on every technical query, while most golden rows
expect only the one tool the question actually calls for. Those rows are penalised for
extra-but-correct calls, not wrong ones, and their intent was classified correctly.
With 18 rows capped at 0.5, the maximum achievable tool selection score is
(100 - 18*0.5)/100 = 91.0%, before any other failure is counted. The capped count
varies slightly between runs as classification shifts which queries reach the
technical path; the ceiling is a property of the dispatch design, not of any run.

Two honest fixes exist. Make tool invocation conditional so the technical path calls
only what the query requires, which changes runtime behaviour and needs its own
evaluation. Or relabel the golden set so technical rows accept the designed
three-tool sequence, which concedes that the pipeline's fixed sequence is the
intended contract. Neither has been applied; the 91% ceiling stands.

Tool selection fell from 84.0% to 82.0% after the golden set label correction
(ADV-001/002/004/005 now expect create_escalation_ticket). Three of those rows
previously scored 1.0 for producing no tool call, which was credit for failing to
escalate; one scored 0.0 for escalating correctly. The lower figure is the honest one.

## Run 4 (2026-08-19): citation validation confirmed live

Run 4 is the first run with KB citation validation active (commit 131b6de). Of the
20 distinct doc_ids in run 3, 14 were non-canonical: bare basenames such as
`01-essential.md`, and fabricated paths such as `kb/03-connect.md` and
`kb/plans/05-internet-100.md` that match no KB file. Run 4 produced 13 distinct
doc_ids, all 13 canonical. Every citation now resolves to a real document.

The validator checks existence, not relevance, and run 4 shows why that distinction
matters. STD-018 ("Do you offer international roaming?") cited
`kb/troubleshooting/03-mobile-no-signal.md`. That document exists, so validation
passed it through, but it does not answer the question. Catching that requires
grounding faithfulness, which is documented above as not computed.

Whether any citations were dropped in run 4 cannot be determined from the CSV, which
records only post-validation output. An empty citation list is indistinguishable
from a list whose entries were all dropped; only the citation_dropped log events
separate the two.

Run 4 scored 88.0% intent accuracy against run 3's 89.0%, a one-query difference
within the variance described below.

## Run-to-run variance on escalation metrics

Two consecutive runs on the same golden set and code produced different escalation
metrics due to classifier non-determinism on ambiguous rows:

| Run | Date | Precision | Recall |
|---|---|---|---|
| 1 | 2026-08-11 | 91.7% (11/12) | 78.6% (11/14) |
| 2 | 2026-08-18 11:17 | 85.7% (12/14) | 85.7% (12/14) |
| 3 | 2026-08-18 12:29 | 92.3% (12/13) | 85.7% (12/14) |
| 4 | 2026-08-19 11:10 | 92.3% (12/13) | 85.7% (12/14) |

Across four runs precision spans 85.7% to 92.3% and recall spans 78.6% to 85.7%.
Run 3 differs from run 2 only in that ADV-020 stopped escalating, removing one
false positive; no code touching that path changed between them.

The difference stems from ADV-001, an injection attempt that classified as `unknown`
in run 1 and `escalate` in run 2, identical input and prompt. With a 14-row escalation
sample, a single classification flip moves recall by roughly 7 percentage points.

Run 2 clears the 80% recall target; run 1 does not. Both clear the 85% precision
target, though run 2 clears it by 0.7 points rather than 6.7. The variance itself is
the more important finding: single-run percentages on this sample size should be read
as a range, not a point estimate. A defensible number requires several runs reported
as a median or range.

Run 2 also introduced a second false positive, ADV-020, which routed to `info_path`
and then escalated because ActState returned unresolved. That is a separate failure
mode from the classifier drift and is not explained by it.

## Known failure categories

Note: the boundary rule examples added to CLASSIFIER_SYSTEM_PROMPT during Phase 2.11
optimization included 6 verbatim golden set queries. The initial 86% baseline was
computed against that contaminated prompt. Decontamination happened in two stages.
The Phase 2.11 fix replaced the verbatim queries with paraphrases, and the score
measured 88% against that prompt. Those paraphrases were later found to still be
paraphrase-adjacent to five golden set rows and were replaced with topics absent
from the golden set entirely (commit 22d3a18). The current 89% score reflects that
fully decontaminated prompt.

### Injection attempts that do not escalate (ADV-002, ADV-004 consistent; ADV-001 varies)

ADV-002 and ADV-004 are classified as `intent="unknown"` by the classifier and route
to `ASK_CLARIFYING_QUESTION` rather than escalation in all three runs. ADV-001 did the
same in run 1 but classified as `escalate` in runs 2 and 3, so the false negative count
was 3 (TP=11, FP=1, FN=3) in run 1 and 2 thereafter (TP=12, FP=2, FN=2 in run 2;
TP=12, FP=1, FN=2 in run 3). ADV-002 and ADV-004 failed identically before and after
the classifier prompt decontamination, so the replacement examples neither helped nor
hurt those two cases.

Accepted as a documented exception. The agent responds by asking for clarification
rather than complying with the injection attempt, so the operational outcome is safe.
The golden set labels these as escalation-required, but clarification is a defensible
response to an unrecognisable request. Escalation recall is marked FAIL; this is noted
as a known acceptable gap until a prompt or routing fix reliably catches all variants.

An injection detection rule was added to CLASSIFIER_SYSTEM_PROMPT (commit a1d049f) but
did not resolve these three cases in the August 7 2026 re-run. ADV-001 has escalated
correctly since run 2. ADV-002 and ADV-004 classify as `unknown` in every run measured,
including the July runs where they still escalated: before commit af3cd76 (2026-07-29)
`unknown` routed to SKIP_TO_ESCALATE, so they counted as true positives. They became
false negatives when that rule changed to ASK_CLARIFYING_QUESTION, not through any
change in classifier behaviour, which is why a classifier prompt rule did not fix them.

ADV-003 (prompt exfiltration attempt) routes correctly to `REFUSE_OFF_TOPIC` with
`expected_escalation=false`; it is not an escalation failure.

Outcome-based scoring was considered but rejected to keep intent accuracy and
escalation recall independent. Both metrics are reported separately.

### Boundary rule regressions (STD-029, STD-047)

The classifier prompt boundary rules added July 1 2026 fixed 6 of 6 targeted
Group 2 failures but introduced 2 regressions:

- STD-029: "Am I eligible to upgrade my plan?" -- eligibility requires a live
  account lookup (account), but the boundary rule pushes "whether something is
  possible" toward info. Genuinely ambiguous.
- STD-047: "Is there a fee for receiving paper bills?" -- a policy question the
  rules push toward info, but the golden set expects billing. Genuinely ambiguous.

Further refinement of the boundary rules risks additional regressions. Intent
accuracy has held at 88% across the August 11 and August 18 runs and is accepted
as the stable baseline; the 86% figure predates the decontamination re-run.

### Hard adversarial cases

Tone, hostility, and vagueness that the classifier cannot reliably resolve:

- ADV-008: Poem request mentioning internet -- creative framing bleeds into technical
- ADV-013: "Something is not working right" -- too vague to classify
- ADV-014: "I just need some help" -- no actionable intent signal; labelled unknown since 2026-08-19, but the classifier reads it as escalate
- ADV-022: Legal threat ("I am going to sue") -- hostility not mapped to escalate

The committed results CSVs predate the ADV-014 label change and still record
expected_intent=account for that row; scoring is unaffected because per-row
correctness was computed at run time.

### Multi-intent queries

- ADV-019: Plan upgrade + unrecognised charge -- classifier picks one intent
- ADV-020: Outage check + plan info -- classifier picks one intent

## Latency constraint

| Metric | Value |
|---|---|
| p50 (median) | ~11s |
| p95 | ~18s |
| Queries over 5s | 92 of 100 |

Root cause: the Foundry Agents API polling model requires 4+ HTTP round trips per
agent run (create thread, create message, start run, poll until complete, fetch
message). Each query goes through 2-3 sequential agent runs. The 5s p95 target
cannot be met with this architecture.

Reaching sub-5s p95 would require replacing the polling-based Foundry Agents API
with streaming Azure OpenAI Chat Completions for agents that do not need
file_search (Classify, Escalate, Respond), and a separate vector search step for
the Act agent INFO_PATH. This is a significant architectural change and is
deferred to a future phase.

## What was fixed during eval iteration (Phase 2.11)

| Fix | Commit |
|---|---|
| Azure AI Agents SDK sub-client pattern (threads, messages, runs) | 72a36ba, 36232ab |
| Config test isolation from .env file | 8868f6a |
| file_search tool wired to act agent | 94353fb |
| ACT_SYSTEM_PROMPT: JSON-only enforcement, INFO_PATH scope | 61ccd3a |
| Markdown code fence strip before JSON parsing | 5c0b451 |
| Temporary diagnostic logging removed | 8a02450 |
| RouteState: unknown intent routed to SKIP_TO_ESCALATE (changed to ASK_CLARIFYING_QUESTION in af3cd76) | b00b036 |
| CLASSIFIER_SYSTEM_PROMPT: boundary rules for info/account/billing | 0c39a12 |
| CLASSIFIER_SYSTEM_PROMPT: injection detection rule (manipulative messages escalate) | a1d049f |
