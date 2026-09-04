#!/usr/bin/env python3
"""Fail on em-dashes and banned words in authored prose.

Usage:
    python scripts/check_style.py

Enforces the style rule in CLAUDE.md. Everything it skips is skipped on a stated
principle rather than a list of files, so adding a file never means adding an
exemption here.

What is not authored prose:

- Tooling directories (.claude/, .specify/) are vendored, not written here.
- Generated fixtures (mock-data/) are produced by a script.
- Recorded model output is a record of what a model said and is never edited to
  satisfy a style rule. That means eval/results_*.csv, and in a notebook the cell
  outputs but not the cell source.

Two things are mentions rather than uses, and both are checked structurally:

- A banned word in double quotes is being named, not used. That is how the rule
  in CLAUDE.md states what it bans, and how any file may quote it.
- A banned word inside the name of a file that exists in the repository is a path
  reference. docs/CAPSTONE_ASSESSMENT.md is referenced from README; renaming it
  to remove a word from a filename would break inbound links for no gain. The
  path must actually be tracked, so this cannot be used to smuggle prose through.

Em-dashes have no exemption at all. A rule can say "em-dash" without containing
one, so an em-dash written into a standing rule fails like any other.
"""

import json
import re
import subprocess
import sys
from pathlib import Path

# Written as an escape so this file does not contain the character it bans, the
# same reason the rule in CLAUDE.md can name an em-dash without using one.
EM_DASH = "\u2014"

# "Day N" and "NEW" are banned as markers, not as English. Matching them
# case-insensitively would flag the ordinary words "new" and "day 15".
WORD_CHECKS = [
    ("mentor", re.compile(r"mentor", re.I)),
    ("capstone", re.compile(r"capstone", re.I)),
    ("Day N", re.compile(r"\bDay\s+\d+\b")),
    ("revised", re.compile(r"\brevised\b", re.I)),
    ("NEW", re.compile(r"\bNEW\b")),
]

SKIP_PREFIXES = (".claude/", ".specify/", "mock-data/")
RECORDED_OUTPUT = re.compile(r"^eval/results_.*\.csv$")
BINARY_SUFFIXES = (".png", ".jpg", ".db", ".ico")

QUOTED = re.compile(r'"[^"]*"')


def tracked_files() -> list[str]:
    out = subprocess.run(
        ["git", "ls-files"], capture_output=True, text=True, check=True
    ).stdout
    return out.split()


def is_authored(path: str) -> bool:
    if path.startswith(SKIP_PREFIXES):
        return False
    if RECORDED_OUTPUT.match(path):
        return False
    return not path.endswith(BINARY_SUFFIXES)


def lines_of(path: str) -> list[tuple[int, str]]:
    """Return (line number, text) pairs of authored content only.

    For a notebook that means cell source. Cell outputs are recorded model
    output and are excluded, so a line number there refers to the cell and the
    position within its source.
    """
    p = Path(path)
    if path.endswith(".ipynb"):
        nb = json.loads(p.read_text(encoding="utf-8"))
        out: list[tuple[int, str]] = []
        for index, cell in enumerate(nb.get("cells", [])):
            source = cell.get("source", "")
            text = source if isinstance(source, str) else "".join(source)
            for offset, line in enumerate(text.splitlines()):
                out.append((index, line))
        return out
    return list(enumerate(p.read_text(encoding="utf-8").splitlines(), 1))


def is_mention(line: str, matched: str, names: set[str]) -> bool:
    """True if this occurrence names the word rather than using it."""
    if any(matched.lower() in q.lower() for q in QUOTED.findall(line)):
        return True
    return any(
        name in line and matched.lower() in name.lower() for name in names
    )


def main() -> int:
    files = tracked_files()
    # Every tracked path and basename, so a path reference can be recognised
    # without naming any file here.
    names = set(files) | {f.rsplit("/", 1)[-1] for f in files}

    failures: list[str] = []
    for path in files:
        if not is_authored(path):
            continue
        try:
            content = lines_of(path)
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
        for number, line in content:
            if EM_DASH in line:
                failures.append(f"{path}:{number}: em-dash\n    {line.strip()[:100]}")
            for label, pattern in WORD_CHECKS:
                for match in pattern.finditer(line):
                    if is_mention(line, match.group(0), names):
                        continue
                    failures.append(
                        f"{path}:{number}: banned word {label!r}\n"
                        f"    {line.strip()[:100]}"
                    )

    if failures:
        print(f"{len(failures)} style violation(s):\n")
        for f in failures:
            print(f)
        print("\nSee the style rule in CLAUDE.md.")
        return 1
    print("No em-dashes or banned words in authored prose.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
