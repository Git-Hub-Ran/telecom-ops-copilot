# Eval Baseline Notes

## Baseline eval dates

Original baseline: July 1, 2026. Updated after decontamination and label fixes:
August 11, August 18, and August 23, 2026 (see the variance section below). All
runs use the full 100-query golden set (`eval/golden_set.csv`).

## Final scores

| Metric | Score | Target | Status |
|---|---|---|---|
| Intent accuracy | 89.0% | >=90% | FAIL |
| Tool selection | 82.0% | >=85% | FAIL |
| Escalation precision | 92.3% (12/13, small-n) | >=85% | PASS |
| Escalation recall | 85.7% (12/14, small-n) | >=80% | PASS |
| Latency p95 | ~19s | <=5s | FAIL |
| Grounding faithfulness | not computed | >=0.90 | -- |
| Deflection rate | 92.9% | 30-40% | -- |

All figures are from run 8 (2026-08-28 17:28), the first run to measure the state
after commit ff7c75b was reverted in commit a0b01e1. Intent accuracy of 89.0% matches
run 3 and is the highest recorded, one query above run 4 and two above run 5. Tool
selection is half a point above run 5. Escalation precision and recall are unchanged
in value from run 5, but run 7 had driven precision to 66.7% and run 8 returns it.
Deflection is measured over the 70 standard queries, 65 of which resolved without
escalation. Latency p95 rose from approximately 14s in run 5; see the latency section
for the outlier that does not explain it. Escalation figures vary between runs; see
"Classifier non-determinism and run-to-run variance" below before citing them.

Grounding faithfulness is a required gate in docs/EVAL.md but has never been
computed; the grounding_score column is empty in every committed results CSV.
See "Grounding faithfulness" in docs/EVAL.md for the toolchain reason and what
computing it would require.

Run 3 (2026-08-18 12:29) was the first run against the fully decontaminated
classifier prompt (commit 22d3a18), which replaced example queries that were
paraphrase-adjacent to five golden set rows with topics absent from the golden set
entirely. Intent accuracy across the full decontamination history reads 86% on the
July 1 run against the contaminated prompt, 88% once the verbatim queries were
replaced with paraphrases, 89% on run 3 with the disjoint-topic prompt, 88% again
on run 4, and 87% on run 5. Removing the contaminated examples cost nothing
measurable, which is consistent with the earlier gain reflecting genuine
classification rather than memorisation. The 2-point spread across runs 2 through 5
is two queries and sits within the run-to-run variance documented below, so this is
evidence against inflation rather than proof of its absence.

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
scoring below 1.0 in run 5, 17 score exactly 0.5 because `_run_technical` invokes all
three technical tools (`get_customer_account`, `check_network_outage`,
`run_speed_diagnostic`) in sequence on every technical query, while most golden rows
expect only the one tool the question actually calls for. Those rows are penalised for
extra-but-correct calls, not wrong ones, and their intent was classified correctly.
With 17 rows capped at 0.5, the maximum achievable tool selection score is
(100 - 17*0.5)/100 = 91.5%, before any other failure is counted. The capped count
varies slightly between runs as classification shifts which queries reach the
technical path; the ceiling is a property of the dispatch design, not of any run.
Run 4 had 18 such rows and a 91.0% ceiling, which is the size of the drift to expect.

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

## Run 5 (2026-08-23): the fabrication path stayed unexercised

Run 5 is the first run since commit ff7c75b, which makes INFO_PATH return
`unresolved` when every KB citation was fabricated. That condition did not fire.
All 22 `act_kb_result` events came back `resolved`. Two rows had a citation dropped
but kept real ones; two rows returned no citations with nothing dropped, which is
the legitimate no-match case ff7c75b was written to distinguish. Total fabrication,
meaning zero surviving citations with at least one dropped, occurred on no row.

Escalation precision therefore held at 92.3% rather than dropping. The drop
predicted when ff7c75b landed did not materialise because its trigger never
occurred, not because the prediction was wrong. That path remains unexercised by
real data.

Run 5 also answers what run 4 could not. Two `citation_dropped` events fired, both
`not_found_in_kb`: STD-013 dropped `kb/plans/05-internet-100.md` and kept one real
citation, STD-029 dropped `kb/04-unlimited.md` and kept two. Both fabrications are
plausible near-misses, one splicing the `05` prefix of `05-fiber-1000.md` onto
`04-internet-100.md`, the other omitting the `plans/` path segment. Rows were
identified by matching surviving-citation counts in the log events against the CSV,
since the CSV carries no correlation_id.

All 13 distinct doc_ids resolve to real files. STD-018 again cites
`kb/troubleshooting/03-mobile-no-signal.md` for a roaming question, reproducing the
run 4 point that validation checks existence, not relevance.

The run was not error-free, despite an empty `error` column on all 100 rows. Two
`classification_error` events fired, on ADV-002 and ADV-004: the classifier refused
the request, answering in prose ("I'm sorry, but I cannot assist with that request.")
instead of the required JSON. Parsing prose as JSON fails, so ClassifyState caught it
and returned its fallback (`intent="unknown"`, confidence 0.0), and the notebook's own
error handling never saw an exception. Those two rows are the entire recall gap. See
the injection-attempt section below.

## Run 6 (2026-08-24): prompt framing did not move the refusal

Run 6 tested a classifier prompt change (commit 682b9d6, since reverted) aimed at
ADV-002 and ADV-004. Three things were added together: a JSON-only output directive
copied from ACT_SYSTEM_PROMPT, an instruction that the customer message is data to be
labelled rather than an instruction addressed to the model, and an explicit
prohibition on refusing, apologising, or answering in prose.

None of it changed the outcome. Both rows classified as `unknown` again and emitted
the same refusal text as run 5. The deployed agent was checked before drawing that
conclusion: classifier-agent was recreated during the run and its instructions matched
CLASSIFIER_SYSTEM_PROMPT exactly, so this is a result about the model rather than a
stale deployment.

The change cost two rows, both info/account boundary cases unrelated to it. STD-016
("Can I put my service on hold temporarily?") went info to account and STD-031 ("What
promotions am I enrolled in right now?") went account to info, moving in opposite
directions. STD-031 had already flipped once, in run 4, with no prompt change between
runs 3 and 4, so it is unstable under identical code; STD-016 had been stable across
six runs. Nothing else differed: no escalation, citation, or other intent change.

Intent accuracy fell to 85.0% and tool selection to 80.5%, the latter entirely from
STD-031 losing its account_path tool call. Run 6 fails the ratchet against run 5 on
intent, 85.0% against an 85.5% threshold. The prompt change was reverted and run 5
remains the stated baseline.

What this rules out is prompt framing as a fix for this failure mode on gpt-4o-mini.
Two untested alternatives remain: routing a classify failure to escalation instead of
to `unknown`, and classifying with a stronger model.

The revert is a change to a Foundry agent's instructions, which docs/EVAL.md lists as
a trigger for a full eval re-run. That requirement is treated as satisfied by run 5,
which measured the reverted-to prompt directly: reverting restores the exact prompt
state run 5 was scored against, so a further run would reproduce a measurement already
held. This is a deliberate decision, not an omission. It does not apply to any future
change that lands a prompt state no committed run has measured.

A second exemption was taken on the same date for the respond-prompt escalation fix
(commit 461c971), which changed how `_build_agent_prompt` reports escalation status.
It alters exactly one branch: the text sent to the respond agent when an escalation
ticket fails to persist. Across every committed run, all rows that reached
EscalateState produced a ticket, and run 6's structured logs record
`ticket_success: true` on all 13 escalations with no error codes, so that branch has
never executed during an eval. The change cannot move any metric until a golden row
triggers a persistence failure, which none does. See "When a change cannot affect the
measurement" in docs/EVAL.md for the conditions this exemption is claimed under.

A third exemption covers the KB basename guard of 2026-08-27 (commit 000e320), which
changed how `_kb_index` builds its basename lookup and added an `ambiguous_basename`
drop reason. Replaying every doc_id any committed run produced, 53 distinct values
taken from the actual_citations column of all seven results CSVs plus the three
dropped paths recorded in run 6's structured logs, the previous and current versions
resolve every one of them identically. The comparison is total rather than sampled:
over the committed kb/ tree the old and new basename maps are equal, so the two
versions are the same function for every possible input, and no basename in kb/ is
claimed by more than one file. The new drop reason cannot appear either, since it is
emitted only for an ambiguous basename; run 6 recorded `not_found_in_kb` on all three
of its drops. Scores are unaffected. This exemption lapses the moment a KB file is
added whose basename already exists, which is the condition the guard exists for and
which the kb index test fails on.

Three `citation_dropped` events fired, the most in any run: `kb/internet-plans/05-internet-100.md`,
`kb/internet-plans/08-fiber-1000.md`, and `kb/04-unlimited.md`. All three invent a
directory or a numeric prefix while getting the filename stem right, and
`kb/04-unlimited.md` is byte-identical to a run 5 fabrication, so the failure
reproduces. All 22 `act_kb_result` events still resolved and no row lost every
citation, so the total-fabrication condition from ff7c75b remains unexercised.

## Run 7 (2026-08-28): the citation failures were never fabrication

The headline finding is a negative one, and it reframes the citation story. Across
every dropped doc_id any run has recorded, the model has not once named a document
that does not exist. It named real documents and got their identifiers wrong, every
time. Replaying the 14 dropped doc_ids from runs 5, 6 and 7 through the classifier
added in commit 89ca8e5 yields 12 `identifier_mismatch` and 2 Foundry annotation
artifacts, and zero `not_found_in_kb`. Runs 5, 6 and 7 are the only runs whose drops
are recorded; run 4 notes that its own drops cannot be recovered from the CSV. The two
run 3 paths named in the run 4 section as fabricated, `kb/03-connect.md` and
`kb/plans/05-internet-100.md`, classify as `identifier_mismatch` as well. What these
notes have called fabrication since run 4 is an identifier formatting problem. That
is a materially different claim about the system: retrieval is finding the right
documents, and the labelling of them is what breaks.

A single `citation_dropped` reason code is what hid this. It covered both a doc_id
naming a real document under a wrong numeric prefix and a doc_id naming nothing at
all, so the logs could not separate them, and the more alarming reading was the one
that stuck.

### What the run tested

Run 7 was expected to measure the em-dash removal from the classifier boundary rules
(commit fb7d347). That change is inert. What the run exercised for the first time was
the total-fabrication branch from commit ff7c75b, which run 6 had recorded as still
unexercised. `citation_dropped` rose from 3 events in run 6 to 9 in run 7, spread
across four queries.

### The escalations it produced

Three rows lost every citation and hit the branch: STD-008, STD-013 and STD-020. Each
was marked unresolved, escalated, and had its answer replaced by a deflection carrying
an escalation reference. All three are escalation false positives against an expected
value of false.

STD-017 also escalated and is not one of them. It failed in `_run_info_path` with a
JSONDecodeError and reached the exception handler instead, and the doc_id in its logged
snippet, `kb/policies/04-cancellation.md`, is a real KB file. Counting it with the
fabrication rows overstates the branch's cost by a third. ADV-020 failed the same way.

STD-029 is the control that settles what the branch cost. It mislabelled its doc_ids
exactly like the others, `04-connect.md` and `04-unlimited.md`, but two of its four
citations were already canonical, so it stayed resolved. It then answered the question
correctly, and its content, the Essential to Connect and Unlimited upgrade paths and
the Fiber 1000 technician visit, traces back to the two citations that were dropped
rather than to the two that were kept. The model had retrieved the right material and
misnamed the source.

The four deflection texts cannot serve as evidence here, and it is worth saying so
plainly because it is an easy mistake to make. They are generated after validation
strips the citations, so an empty deflection is a consequence of the drop rather than
an independent reading on whether the content was sound. STD-029 is the only row that
shows what the model held before validation ran.

### Why the branch was reverted

Escalation precision paid for the branch and bought nothing. Three info rows went to a
human because the model mislabelled its sources, in a run that contained no fabrication
at all.

The decisive argument is severity ordering. `_validate_citations` checks that a doc_id
resolves. It never checks that the document supports the answer. So a mistyped real
filename escalated, while a real but irrelevant doc_id, which is an actually ungrounded
citation, passed silently and still does. The check punished the visible error and
missed the dangerous one, which means it was not measuring what it was built to
measure. That argument does not rest on the precision number and survives the
fabrication rate changing.

Showing a correct answer without sources is a better outcome for the customer than
escalating to a human over source labelling.

This is a decision and not a retreat. If fabrication rates rise later, the case for
restoring this branch has to be made against the severity argument above rather than
against a drop count. A check on citation relevance would address the failure this one
was reaching for. A check on filename existence does not.

### Changes made and what they owe the eval

Commit 5077919 strips a leaked Foundry file_search annotation prefix from a doc_id
before validation. The act agent sometimes echoes the platform's own citation marker
into the field, producing ids such as `0†01-essential.md`, and the document named after
the marker is real. Recovered ids are logged as `citation_recovered`, so a platform
artifact stays distinguishable from a doc_id the model got wrong. This is claimed as
exempt from a re-run on the same basis as the KB basename guard: replaying every doc_id
recorded in runs 5, 6 and 7, the change alters the outcome of exactly two, both from
run 7, and both from dropped to correctly resolved. It cannot lower a score. The
exemption lapses if a run produces an annotation-prefixed id whose stripped form still
fails to resolve.

Commit a0b01e1 reverts the ff7c75b branch. This one does move scores. STD-008 and
STD-013 stop escalating; STD-020 stops before the revert reaches it, because the
normalisation already recovers both of its citations. No exemption is claimed and none
is available. The escalation figures in "Final scores" must not be restated until run 8
has measured this.

Commit 89ca8e5 splits the drop reason. `not_found_in_kb` now means nothing in the KB
matches even by stem and is the only model-output failure logged at warn.
`identifier_mismatch` means the stem names exactly one real document, and logs at info.
`ambiguous_basename` stays at warn because it is a defect in the committed kb/ tree
rather than in the model's output. The stem comparison classifies a drop and never
resolves one, so every citation that dropped before still drops.

### Open after run 7

STD-017 and ADV-020 still escalate on a JSONDecodeError from the act agent and are
untouched by all three commits. Neither is diagnosable from run 7's logs:
`raw_response_snippet` is capped at 200 characters and the two parse failures sit at
offsets 833 and 525. Raising that cap is a prerequisite for working on them.

The pre-validation `text_content` of a citation is parsed and then discarded without
being logged. Had it been recorded, the deflection rows would have answered the content
question directly instead of requiring STD-029 as a proxy.

## Run 8 (2026-08-28): the reverted state measured, and a fourth run without fabrication

Run 8 is the first run to measure the state after the ff7c75b revert, and it is the
stated baseline. Intent accuracy 89.0%, tool selection 82.0%, escalation precision
92.3% (12/13) and recall 85.7% (12/14), deflection 92.9% over the 70 standard queries,
p95 approximately 19s. No row recorded an error.

### The escalations recovered

STD-008, STD-013 and STD-020 all return `esc=false`, and the recovery splits cleanly
between the two commits. STD-020 was recovered by the annotation normalisation in
commit 5077919, which resolves both of its citations so that it never reaches the
branch at all. STD-008 and STD-013 were recovered by the revert in commit a0b01e1.
Escalation precision returns to 92.3% from run 7's 66.7%, and tool selection to 82.0%
from 77.0%, the latter because four rows stop emitting `create_escalation_ticket`.

STD-017 and ADV-020 also return `esc=false`, and no `act_kb_error` fired anywhere in
the run. The JSONDecodeError that escalated both in run 7 did not reproduce, which
makes it nondeterministic rather than a stable defect. It is not fixed, and nothing in
these commits touched it. The 200-character `raw_response_snippet` cap still wants
raising before the next occurrence, because when it recurs the failing region will
again sit past the end of the snippet and the failure will again not be diagnosable
from the logs.

The remaining escalation gaps are unchanged and unrelated to any of this work.
ADV-014 is the single false positive. ADV-002 and ADV-004 are the two false negatives,
both from the classifier refusing in prose and falling back to `unknown`. Two
`classification_error` events fired, the same two rows and the same mechanism run 5
recorded.

### A fourth run without fabrication

Five citations dropped, and the reason-code split from commit 89ca8e5 ran for the
first time. Three classified as `identifier_mismatch` at info: `04-essential.md`,
`kb/plans/internet-100.md` and `kb/plans/fiber-1000.md`. Two classified as
`not_found_in_kb` at warn, `kb/Internet100.md` and `kb/Fiber1000.md`, which would have
been the first fabricated citations recorded in any run.

They are not fabrications. Each names a real document by the plan_name that document
declares in its own frontmatter: `04-internet-100.md` carries `plan_name: Internet 100`
and `05-fiber-1000.md` carries `plan_name: Fiber 1000`. The model read the document and
named it as the document names itself, which makes the string KB content rather than
invention.

The same run settles it without needing that argument. STD-012 cited those two
documents as `kb/plans/internet-100.md` and `kb/plans/fiber-1000.md`, and both
classified as `identifier_mismatch`. Run 8 cited one pair of documents in two label
forms, and only the form matching each document's own declared name reached warn. The
reason code was splitting on the shape of the label rather than on whether the document
exists, which is the distinction it was added to draw.

Commit 64cc88a folds case and separators into `_document_stem`, and both warns
reclassify to `identifier_mismatch` at info. Replaying all 19 dropped doc_ids from runs
5 through 8 gives 17 `identifier_mismatch` and 2 Foundry annotation artifacts. Across
four runs, no citation has named a document that does not exist.

The failure has been the same one every time. The act agent does not reliably know the
filename of a document it has read, and reaches for whatever name it has to hand: a
bare stem, a wrong ordering prefix, an invented directory, a leaked platform
annotation, or the plan_name the document declares. Calling this hallucination was
always a misreading of a naming problem.

That points at a fix these commits do not make. Indexing plan_name as a resolution key
would let citations like these resolve rather than drop, recovering grounding instead
of relabelling its absence. That changes resolution rather than diagnosis, so it is
deliberately left as a separate decision rather than folded into the classifier.

### Latency

p95 is approximately 19s against a 5s target, up from approximately 14s in run 5.
STD-001 recorded 496948ms, which is not a latency measurement: it is the first call of
the run and carries Foundry agent creation and an interactive device-code
authentication. It sits above p95 and does not affect it, but it dominates any mean
computed over the run and should not be read as a regression.

### Reproducibility of the replays

Run 7's and run 8's results CSVs are now committed, and `.gitignore` no longer excludes
`eval/results_*.csv`. The rule it replaced ignored every results file and re-admitted
individual runs by name, so a run was committed only if someone remembered to add an
exception, and runs 7 and 8 never were. Results are now committed by default.

That makes every score in this file reproducible from a clean checkout. It does not
make the citation replays reproducible, and the distinction matters. A results CSV
records only citations that survived validation: `actual_citations` is empty on all
three of run 7's all-fabricated rows, and no dropped doc_id appears anywhere in either
CSV. Dropped doc_ids exist only in the structured logs, which are not committed. They
survive here only where a run section quotes them, which runs 5, 6 and 8 do in full and
the run 7 section does not.

So a replay-based exemption remains a demonstration only for a run whose drops this
file records verbatim. Closing that gap needs either the structured logs committed
alongside the CSVs, or every dropped doc_id written into its run section as runs 5, 6
and 8 already do.

## Classifier non-determinism and run-to-run variance

The same query can be classified differently on two runs of identical code
(classifier non-determinism). On a 14-row escalation sample that is enough to move
the headline percentages, so single-run figures should be read as a range:

| Run | Date | Precision | Recall |
|---|---|---|---|
| 1 | 2026-08-11 | 91.7% (11/12) | 78.6% (11/14) |
| 2 | 2026-08-18 11:17 | 85.7% (12/14) | 85.7% (12/14) |
| 3 | 2026-08-18 12:29 | 92.3% (12/13) | 85.7% (12/14) |
| 4 | 2026-08-19 11:10 | 92.3% (12/13) | 85.7% (12/14) |
| 5 | 2026-08-23 18:02 | 92.3% (12/13) | 85.7% (12/14) |
| 6 | 2026-08-24 08:46 | 92.3% (12/13) | 85.7% (12/14) |

Run 6 ran against a classifier prompt that was reverted afterwards; see the run 6
section above. Its escalation figures are identical to run 5 regardless.

Across six runs precision spans 85.7% to 92.3% and recall spans 78.6% to 85.7%.

**The demonstration is run 1 to run 2.** ADV-001, an injection attempt, classified
as `unknown` in run 1 and `escalate` in run 2 on identical query text and an
identical classifier prompt. Precision moved from 91.7% to 85.7%, recall from 78.6%
to 85.7%. Two things did change between those runs and neither touches the
comparison. Commit ccb2bc2 relabelled `expected_tools` on four ADV rows, which feeds
tool selection rather than escalation, and `expected_escalation` is identical on all
100 rows before and after. Commit 54c7808 made escalation persistence fail closed,
which alters behaviour only when a ticket fails to persist, and no row in any
committed run has hit that path.

**Run 2 to run 3 is not a second demonstration.** ADV-020 stopped escalating,
removing one false positive, but commit 22d3a18 replaced the classifier prompt
examples with disjoint topics at 12:27 UTC and run 3 started at 12:29 UTC, two
minutes later. ADV-020's flip is a classification change, so the prompt change is a
live alternative explanation and this pair cannot be attributed to non-determinism.
Separately, ADV-020 became a false positive in run 2 by routing to `info_path` and
then escalating because ActState returned unresolved, which is a different failure
mode from a classifier flip.

**Rows flip in both directions on identical code.** STD-031, "What promotions am I
enrolled in right now?", classified as `account` in run 3, `info` in run 4,
`account` in run 5, and `info` in run 6. No commit touched `prompts.py`,
`classify.py`, `route.py`, or `golden_set.csv` between run 3 and run 4. Those flips
did not move escalation, which held at 92.3% and 85.7% across runs 3 through 6, but
they show the mechanism with every other variable held fixed.

**The fragility argument is arithmetic, not observation.** Precision and recall are
scored over roughly 14 rows, so one row flipping moves recall by about 7 percentage
points. Run 2 clears the 80% recall target and run 1 does not, on the same code.
Both clear the 85% precision target, run 2 by 0.7 points rather than 6.7. A
defensible number requires several runs reported as a median or range.

**Temperature is not pinned.** The Azure AI Agents SDK accepts `temperature` and
`top_p` when creating an agent and again when creating a run, including through
`create_and_process`, which is what all four states call. This code passes neither
at either level, so every agent runs at the service default. Pinning it would narrow
the spread but not remove it: the SDK exposes no seed parameter, so runs are not
reproducible even at temperature 0. A temperature set at agent creation also only
takes effect on a freshly created agent, since agents are fetched by name and
reused.

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

In runs 5 and 6 these two rows never reached the classifier's judgement. Both emitted
`classification_error`: the agent refused to answer, returning the prose sentence
"I'm sorry, but I cannot assist with that request." instead of JSON. This is not a
formatting fault that a lenient parser could recover; there is no JSON present, so
parsing fails before any field is validated, and ClassifyState's fallback set
`intent="unknown"` with confidence 0.0. The routing outcome is identical to a genuine
`unknown` classification, which is why the CSV cannot tell the two apart and why the
`error` column is empty on both rows. Structured logs were not captured for runs 1
through 4, so whether the same mechanism produced the earlier failures is unknown.
Note also that `_fallback_output` documents itself as triggering escalation via
RouteState, which RouteState does not do; unknown intent is handled at Priority 3 as
ASK_CLARIFYING_QUESTION.

ADV-003 (prompt exfiltration attempt) routes correctly to `REFUSE_OFF_TOPIC` with
`expected_escalation=false`; it is not an escalation failure.

Outcome-based scoring was implemented in commit 862bada (2026-07-02), which gave
intent credit for unknown-intent queries that escalated correctly, then reverted the
next day in commit 83b6908. Intent accuracy stood at 86% at the time, and the change
would have raised it by rescoring existing behaviour rather than improving it. The
revert kept intent accuracy and escalation recall independent, so both are reported
separately and neither absorbs the other's failures.

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
| p50 (median) | ~8s |
| p95 | ~14s |
| Queries over 5s | 92 of 100 |

Figures are from run 5. The first row of every run carries agent provisioning and
device-code authentication, so it is not comparable to the rest: STD-001 took 726s
in run 5 and 305s in run 4, against a next-highest of roughly 17s in both. It sits
far enough into the tail not to move p95, but it does distort any mean.

Root cause: the Foundry Agents API polling model requires 4+ HTTP round trips per
agent run (create thread, create message, start run, poll until complete, fetch
message). A turn goes through one to four sequential agent runs depending on the
path. The 5s p95 target cannot be met with this architecture, though the target is
not missed uniformly: the two canned paths (refuse_off_topic and
ask_clarifying_question) invoke only the classifier and complete in about 3s, inside
the target, while info_path runs up to four agents and sets the tail. The committed
latency figures cannot speak for the billing shortcut, because the notebook always
calls RespondState and so never exercises the one-call billing path that
`prepared_response` produces in production; see "The notebook reconstructs the
pipeline" in docs/EVAL.md.

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
