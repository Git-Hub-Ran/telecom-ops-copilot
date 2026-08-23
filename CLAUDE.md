<!-- SPECKIT START -->
For additional context about technologies to be used, project structure,
shell commands, and other important information, read the current plan:
.specify/features/state-machine-orchestrator/plan.md
<!-- SPECKIT END -->

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
- Never use em-dashes, or the words "mentor", "capstone",
  "Day N", "revised", or "NEW" in any file or commit message.
- Always run git status before starting new work to verify a
  clean working tree.
- When replying in English, whether in Claude Code or in chat, use
  simple, plain English and keep answers short. This does not apply
  to code itself, only to explanatory text around it.
- Never cite line numbers in documentation, comments, or commit
  messages. Reference a symbol, function, or section name instead.
  Line numbers go stale on any edit above them, including edits made
  in an unrelated commit, and a citation that drifts back into
  correctness by chance is not a reference anyone can trust.
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
