"""Unit tests for shared state helpers.

strip_code_fence removes the Markdown fence that agents sometimes wrap around
their JSON responses. It is consolidated from four identical copies that lived in
the state modules, so the mechanics are covered here once rather than repeated in
each state's test file. Each state keeps one test proving it calls this.
"""

import pytest

from src.orchestrator.states.base import strip_code_fence

_JSON = '{"a": 1}'


class TestStripCodeFence:
    """Fence forms that must all yield the bare payload."""

    @pytest.mark.parametrize(
        "raw",
        [
            f"```json\n{_JSON}\n```",
            f"```\n{_JSON}\n```",
            f"```json {_JSON}```",
            f"```{_JSON}```",
            f"```json\n{_JSON}",
            _JSON,
            f"   {_JSON}   ",
        ],
        ids=[
            "multiline-tagged",
            "multiline-bare",
            "single-line-tagged",
            "single-line-bare",
            "unclosed-fence",
            "no-fence",
            "padded-no-fence",
        ],
    )
    def test_payload_is_recovered(self, raw: str) -> None:
        assert strip_code_fence(raw) == _JSON

    def test_single_line_fence_does_not_raise(self) -> None:
        """Regression: splitting on the first newline raised IndexError here.

        Every caller wraps this in a broad except, so the IndexError did not
        surface as a crash. It discarded a parseable response and took the
        fallback path instead, which on ClassifyState means intent="unknown".
        """
        assert strip_code_fence(f"```json {_JSON}```") == _JSON

    def test_backticks_inside_the_payload_survive(self) -> None:
        """Only the trailing fence is removed; the closing pattern is anchored."""
        raw = '```json\n{"a": "x```y"}\n```'
        assert strip_code_fence(raw) == '{"a": "x```y"}'

    def test_empty_string_is_returned_unchanged(self) -> None:
        assert strip_code_fence("") == ""
