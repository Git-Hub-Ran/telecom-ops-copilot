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
scoped to directories. Extending it to every file would flag each new test the
moment it is added, which is noise rather than drift.

File level: the README names docs/*.md and scripts/*.py one by one, so those
are checked as files rather than as directories. A document must appear in the
block AND in the Documentation link line below it, because it is advertised in
both and is easy to add to one and forget in the other; a script needs only the
block. The failure says which list is missing it. IGNORED_DOCS is the escape
hatch for a file that is deliberately not advertised.

The block and the link line are both located by their surrounding text, so
nothing here depends on line numbers.
"""

import os
import posixpath
import re
import subprocess
import sys

HEADING = "## Project structure"
FENCE = "```"
LINK_MARKER = "**Documentation:**"

# Markdown link targets, used to read the Documentation line.
LINK = re.compile(r"\[[^\]]*\]\(([^)]+)\)")

# Directories the README names file by file, as (directory, suffix, needs_link).
# Everything else is checked at directory granularity by reverse_failures, which
# is the right level for tests/ and for src/ subpackages. Only docs/ is repeated
# in the Documentation line, so only docs/ needs the second list.
FILE_LEVEL = [
    ("docs", ".md", True),
    ("scripts", ".py", False),
]

# Vendored tooling, not project structure. Both are checked into the repository
# but describe how the project is authored rather than what it contains, which
# is the same principle that excludes them in check_style.py. Nothing else needs
# an entry: this check reads `git ls-files`, so .git/, .pytest_cache/, data/ and
# every __pycache__ are invisible to it already by being untracked or ignored.
IGNORED_DIRS = {".claude", ".specify"}

# Escape hatch for the file-level check below. Put a path here when a tracked
# file under a FILE_LEVEL directory is deliberately not advertised in the
# README: an internal note, a scratch script, anything written for the author
# rather than for a reader. Adding a path here is a decision to leave it
# undocumented, so say why in a comment beside it. It is not the place to park
# a file that simply has not been written up yet; document that one instead.
IGNORED_DOCS: set[str] = set()


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


def documentation_links(readme: str) -> set[str]:
    """Link targets in the Documentation paragraph below the block.

    The paragraph runs from the marker to the next blank line, so it may wrap
    across as many lines as it likes.
    """
    lines = readme.splitlines()
    start = next(
        (i for i, l in enumerate(lines) if l.strip().startswith(LINK_MARKER)), None
    )
    if start is None:
        raise BlockNotFound(
            f"README.md has no {LINK_MARKER!r} line.\n"
            f"    This check reads the documentation links from that paragraph. "
            f"If it was renamed, update LINK_MARKER in this script to match."
        )
    end = next(
        (i for i in range(start, len(lines)) if not lines[i].strip()), len(lines)
    )
    targets = set()
    for line in lines[start:end]:
        targets.update(normalise_target(t) for t in LINK.findall(line))
    return targets


def normalise_target(target: str) -> str:
    """Reduce a markdown link target to a repository-relative path.

    Markdown allows the same destination to be written several ways, and a
    check that only understood one of them would fail on a link that is
    perfectly correct. Handles <angle brackets>, a "quoted title" after the
    path and a #fragment; posixpath.normpath then collapses ./ and //, so
    the separator forms do not each need their own case here.
    """
    target = target.strip()
    if target.startswith("<") and ">" in target:
        target = target[1 : target.index(">")]
    target = target.split(" ", 1)[0].split("#", 1)[0].strip()
    return posixpath.normpath(target) if target else target


def file_level_failures(entries, files, links) -> list[str]:
    """Files the README names individually must actually be named there."""
    listed = {path for path, _ in entries}
    out = []
    for path in sorted(files):
        if path in IGNORED_DOCS:
            continue
        parts = path.split("/")
        matched = [
            needs_link
            for directory, suffix, needs_link in FILE_LEVEL
            if len(parts) == 2 and parts[0] == directory and path.endswith(suffix)
        ]
        if not matched:
            continue
        missing = []
        if path not in listed:
            missing.append("the structure block")
        if matched[0] and path not in links:
            missing.append(f"the {LINK_MARKER} line")
        if missing:
            out.append(
                f"{path}: tracked but missing from {' and '.join(missing)}.\n"
                f"    The README names these individually; add it to "
                f"{'both' if len(missing) > 1 else 'the one above'}, or to "
                f"IGNORED_DOCS in this script if it is deliberately private."
            )
    return out


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
            readme = fh.read()
        entries = block_entries(readme)
        links = documentation_links(readme)
    except BlockNotFound as exc:
        print(f"1 project structure problem(s):\n\n{exc}")
        return 1

    failures = (
        forward_failures(entries, files, dirs)
        + reverse_failures(entries, files)
        + file_level_failures(entries, files, links)
    )
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
