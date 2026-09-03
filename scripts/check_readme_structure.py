#!/usr/bin/env python3
"""Fail when the README project structure block disagrees with the repository.

Usage:
    python scripts/check_readme_structure.py

Two checks run, because the block drifts in both directions.

Forward: every path in the block must be tracked in git. This catches a file
that was deleted or renamed while the block kept naming it. Resolution is
against `git ls-files` rather than the filesystem, so a path that exists only
in the working tree, untracked or gitignored, fails rather than passes.

Reverse: every tracked top-level directory and every tracked subdirectory of
src/ must appear somewhere in the block. This catches the opposite drift, a
directory added to the repository that nobody documented. It is deliberately
scoped to directories. Extending it to files would flag every new document and
test the moment it is added, which is noise rather than drift.

The block is located by its heading and the following fence, so nothing here
depends on line numbers.
"""

import os
import re
import subprocess
import sys

HEADING = "## Project structure"
FENCE = "```"

# Vendored tooling, not project structure. Both are checked into the repository
# but describe how the project is authored rather than what it contains, which
# is the same principle that excludes them in check_style.py. Nothing else needs
# an entry: this check reads `git ls-files`, so .git/, .pytest_cache/, data/ and
# every __pycache__ are invisible to it already by being untracked or ignored.
IGNORED_DIRS = {".claude", ".specify"}


class BlockNotFound(Exception):
    """The structure block could not be located in README.md."""


def repo_root() -> str:
    """The repository root, so this runs correctly from any directory."""
    try:
        return subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
    except subprocess.CalledProcessError:
        raise BlockNotFound(
            "not inside a git repository.\n"
            "    This check resolves paths against git, so it must run from a "
            "clone of this repository."
        )


def tracked_files(root: str) -> list[str]:
    out = subprocess.run(
        ["git", "-C", root, "ls-files"], capture_output=True, text=True, check=True
    ).stdout
    return out.splitlines()


def tracked_dirs(files: list[str]) -> set[str]:
    """Every directory implied by a tracked path.

    Built from path segments rather than string prefixes, so a tracked
    src/database.py implies src/ and not src/data/.
    """
    dirs = set()
    for path in files:
        parts = path.split("/")
        for i in range(1, len(parts)):
            dirs.add("/".join(parts[:i]))
    return dirs


def glob_to_regex(pattern: str) -> re.Pattern[str]:
    """Compile a block glob so that '*' stops at a path separator.

    fnmatch translates '*' to '.*', which crosses directories: it would let
    eval/results_x/nested.csv satisfy an entry written as eval/results_*.csv.
    """
    return re.compile(
        "".join("[^/]*" if part == "*" else re.escape(part)
                for part in re.split(r"(\*)", pattern))
        + r"\Z"
    )


def block_entries(readme: str) -> list[tuple[str, bool]]:
    """Return (path, is_directory) for each entry, rebuilt from indentation.

    Indent 0 resets the parent stack, indent 2 nests under the last indent-0
    directory, and so on. The path is the first token before any run of two or
    more spaces; the rest of the line is the description column.
    """
    lines = readme.splitlines()
    start = next(
        (i for i, l in enumerate(lines) if l.strip() == HEADING), None
    )
    if start is None:
        raise BlockNotFound(
            f"README.md has no {HEADING!r} heading.\n"
            f"    This check locates the block by that heading. If the heading "
            f"was renamed, update HEADING in this script to match."
        )
    opened = next(
        (i for i in range(start, len(lines)) if lines[i].strip() == FENCE), None
    )
    closed = (
        None if opened is None
        else next(
            (i for i in range(opened + 1, len(lines)) if lines[i].strip() == FENCE),
            None,
        )
    )
    if closed is None:
        raise BlockNotFound(
            f"README.md has no closing {FENCE} fence after the {HEADING!r} "
            f"heading.\n    The block must be a fenced code block."
        )

    stack: dict[int, str] = {}
    entries: list[tuple[str, bool]] = []
    for raw in lines[opened + 1 : closed]:
        if not raw.strip():
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        token = re.split(r"\s{2,}|\s+$", raw.strip())[0].strip()
        if not token:
            continue
        is_dir = token.endswith("/")
        name = token.rstrip("/")
        parents = [stack[k] for k in sorted(stack) if k < indent]
        if is_dir:
            stack = {k: v for k, v in stack.items() if k < indent}
            stack[indent] = name
        entries.append(("/".join(parents + [name]), is_dir))
    return entries


def forward_failures(entries, files, dirs) -> list[str]:
    known = set(files)
    out = []
    for path, is_dir in entries:
        if "*" in path:
            if not [f for f in files if glob_to_regex(path).match(f)]:
                out.append(
                    f"{path}: no tracked file matches this pattern.\n"
                    f"    Remove the entry, or commit the files it describes."
                )
        elif is_dir:
            if path in known:
                out.append(
                    f"{path}/: written as a directory but tracked as a file.\n"
                    f"    Drop the trailing slash in the block."
                )
            elif path not in dirs:
                out.append(
                    f"{path}/: not a tracked directory.\n"
                    f"    Remove the entry, or commit a file under it."
                )
        elif path not in known:
            if path in dirs:
                out.append(
                    f"{path}: written as a file but tracked as a directory.\n"
                    f"    Add a trailing slash in the block."
                )
            else:
                out.append(
                    f"{path}: not tracked in git.\n"
                    f"    Remove the entry, or commit the file it names."
                )
    return out


def reverse_failures(entries, files) -> list[str]:
    """Tracked directories in scope that no block entry mentions."""
    listed = {path for path, _ in entries}
    covered = {p.split("/", 1)[0] for p in listed}
    covered |= {"/".join(p.split("/")[:2]) for p in listed if "/" in p}

    in_scope = set()
    for path in files:
        parts = path.split("/")
        if len(parts) > 1:
            in_scope.add(parts[0])
        if parts[0] == "src" and len(parts) > 2:
            in_scope.add("src/" + parts[1])

    out = []
    for directory in sorted(in_scope - covered - IGNORED_DIRS):
        out.append(
            f"{directory}/: tracked but missing from the block.\n"
            f"    Add it, or add it to IGNORED_DIRS here if it is not "
            f"project structure."
        )
    return out


def main() -> int:
    try:
        root = repo_root()
        files = tracked_files(root)
        dirs = tracked_dirs(files)
        with open(os.path.join(root, "README.md"), encoding="utf-8") as fh:
            entries = block_entries(fh.read())
    except BlockNotFound as exc:
        print(f"1 project structure problem(s):\n\n{exc}")
        return 1

    failures = forward_failures(entries, files, dirs) + reverse_failures(entries, files)
    if failures:
        print(f"{len(failures)} project structure problem(s):\n")
        for f in failures:
            print(f)
        print(f"\nThe block is under '{HEADING}' in README.md.")
        return 1
    print(f"README structure block matches the repository ({len(entries)} entries).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
