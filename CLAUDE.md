<!-- SPECKIT START -->
For additional context about technologies to be used, project structure,
shell commands, and other important information, read the current plan:
.specify/features/state-machine-orchestrator/plan.md
<!-- SPECKIT END -->

That plan is the pre-build document. Its body describes intended architecture
that changed during implementation, so do not read it for current structure or
commands: those are in "Project structure" and "Commands" at the end of this
file, and what actually shipped is in docs/ARCHITECTURE.md.

## Standing rules

- Before any `git commit`, show the full diff (`git diff --staged`) for
  every file being committed and wait for explicit user approval. No
  exceptions, including multi-file commits and task-tracking files.
- Never create files that were not explicitly requested. Do not
  create memory files, feedback files, or any file outside the
  task scope.
- Never bundle planning commits with implementation commits. One
  logical change per commit.
- Never include "Co-Authored-By: Claude" or any AI attribution
  in commit messages.
- Never use em-dashes, or the words "mentor", "capstone", "revised",
  or "Day N" and "NEW" as markers, in authored prose: source, tests,
  docs, README, notebook cell source, and commit messages. Naming a
  banned word in quotes is a mention rather than a use, which is how
  this rule states what it bans. A word inside the name of a file that
  exists in the repository is a path reference, not prose:
  docs/CAPSTONE_ASSESSMENT.md is linked from README, and renaming it to
  get a word out of a filename would break those links for no gain.
  Recorded model output is never edited to satisfy a style rule, which
  covers eval/results_*.csv and notebook cell outputs. Em-dashes have no
  exemption; this rule names one without containing one.
  `scripts/check_style.py` enforces all of the above and runs in CI.
- Always run git status before starting new work to verify a
  clean working tree.
- At the start of a session, run `git log` against the last commit
  you remember before reasoning about the current state. Work lands
  between sessions, and a stale picture produces confident wrong
  answers rather than visible errors. When a request references work
  you have no record of, verify it from the repository rather than
  accepting the premise or disputing it. Accepting invents detail;
  disputing denies work that was really done.
- When replying in English, whether in Claude Code or in chat, use
  simple, plain English and keep answers short. This does not apply
  to code itself, only to explanatory text around it.
- Never cite line numbers in documentation, comments, or commit
  messages. Reference a symbol, function, or section name instead.
  Line numbers go stale on any edit above them, including edits made
  in an unrelated commit, and a citation that drifts back into
  correctness by chance is not a reference anyone can trust.
- When verifying a claim across files, read the files rather than pattern
  matching them. Grep finds the phrasings you already thought of, not the
  ones you did not: sweeps for "~18s" and "17 to 18s" both missed
  "approximately 20 seconds". A reported finding names instances, not all
  of them: findings citing three places have repeatedly turned out to have
  five or six. Use grep to find candidates and a report to start from,
  never to conclude that a class of claim is fully corrected.
- Never use the NotebookEdit tool on `.ipynb` files in this repo.
  Notebook outputs are committed here, and NotebookEdit strips the
  outputs of every cell it touches and nulls `execution_count`.
  Edit the notebook JSON surgically instead, at the byte or line
  level, so outputs and source formatting survive unchanged.

## Writing code

Work down this ladder before writing anything new. Stop at the first
step that answers the need.

1. Does this need to exist at all? If not, say so and stop.
2. Is it already in this codebase? Reuse it.
3. Does the standard library cover it? Use that.
4. Is there a native platform feature for it? Use that.
5. Does an already installed dependency cover it? Use that.
6. Can it be one line? Write the one line.
7. Only then write new code, and write the minimum that works.

- Never add features, options, config, or abstraction layers that
  were not requested.
- Do not add error handling, logging, or defensive checks beyond
  what the surrounding code already does.
- This ladder never applies to validation, security, or
  accessibility. Those are written in full.

## Project structure

```
src/orchestrator/  the five-state pipeline: state_machine.py, states/,
                   agents/ (prompts and the get-or-create factory),
                   models/, observability/
src/tools/         the five tool functions
src/data/          BillingDataSource protocol, JSON and SQLite implementations
src/ui/            Streamlit app
tests/             pytest suite, mirroring the src/ layout
eval/              golden_set.csv, committed results CSVs, BASELINE_NOTES.md
kb/                knowledge base markdown
notebooks/         03-evaluation.ipynb is the eval runner
scripts/           score_eval.py and the data setup scripts
docs/              ARCHITECTURE.md is what shipped; PLAN.md is pre-build
```

## Commands

```bash
pytest tests/ -q                                  # full suite, no credentials
streamlit run src/ui/app.py                       # needs .env and device-code sign-in
python scripts/score_eval.py <results.csv>        # against EVAL.md thresholds
python scripts/score_eval.py <results.csv> --baseline <prior.csv>   # ratchet
```

`score_eval.py` takes no default results file. The newest run is not necessarily
the baseline, and the script cannot tell them apart.

## Quality gates before a PR

- `pytest tests/ -q` passes. CI runs the same suite on Python 3.12.
- The eval has been re-run if any trigger in docs/EVAL.md applies, or the reason
  it was not is recorded in eval/BASELINE_NOTES.md under the conditions set out
  in "When a change cannot affect the measurement" in docs/EVAL.md.
- If a run happened, its results CSV and the notebook outputs are committed and
  BASELINE_NOTES.md records the figures.
- The CI ratchet in `.github/workflows/tests.yml` names the two most recent runs.
- Deployed Foundry agent prompts match the repository. Agents are fetched by name
  and reused, so a prompt edit is inert until the agent is deleted and recreated.
  Check all four, not the one that changed.

## Branching

Work happens on `Dev`. Pull requests go from `Dev` into `Main`. CI runs on push
to `Dev` and on pull requests targeting `Main`.
