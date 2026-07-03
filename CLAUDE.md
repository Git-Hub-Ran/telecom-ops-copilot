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
