"""Unit tests for the rendering helpers in src/ui/app.py.

_render_agent_text prepares agent output for Streamlit's Markdown renderer.
It has two jobs: escape dollar signs so amounts are not parsed as LaTeX, and
strip Markdown image syntax, which Streamlit renders as an <img> that fetches
its URL when the message displays. All other Markdown must survive, because
KB answers rely on bullets and bold.
"""

import pytest

from src.ui.app import _render_agent_text


class TestRenderAgentTextDollarEscaping:
    """Dollar amounts must not be parsed as LaTeX."""

    def test_single_amount_is_escaped(self) -> None:
        assert _render_agent_text("Your bill is $22.00.") == r"Your bill is \$22.00."

    def test_multiple_amounts_all_escaped(self) -> None:
        result = _render_agent_text("Subtotal $25.00, discount -$5.00, total $22.00.")
        assert result == r"Subtotal \$25.00, discount -\$5.00, total \$22.00."

    def test_text_without_dollars_is_unchanged(self) -> None:
        assert _render_agent_text("No amounts here.") == "No amounts here."


class TestRenderAgentTextImageStripping:
    """Markdown image syntax must not reach the renderer."""

    def test_image_collapses_to_alt_text(self) -> None:
        result = _render_agent_text("See ![logo](http://x/y.png) here.")
        assert result == "See logo here."

    def test_image_url_is_removed(self) -> None:
        result = _render_agent_text("![beacon](https://attacker.test/track.png)")
        assert "attacker.test" not in result
        assert result == "beacon"

    def test_image_with_empty_alt_collapses_to_nothing(self) -> None:
        assert _render_agent_text("![](http://x/y.png)") == ""

    def test_multiple_images_all_stripped(self) -> None:
        result = _render_agent_text("![a](http://x/1.png) and ![b](http://x/2.png)")
        assert result == "a and b"
        assert "http" not in result

    def test_reference_image_and_its_definition_are_stripped(self) -> None:
        """Full reference form. The definition line is what resolves the URL."""
        result = _render_agent_text(
            "See ![beacon][b] here.\n\n[b]: https://attacker.test/track.png"
        )
        assert "attacker.test" not in result
        assert "![" not in result
        assert "See beacon here." in result

    def test_collapsed_reference_image_is_stripped(self) -> None:
        result = _render_agent_text("See ![beacon][] here.")
        assert result == "See beacon here."

    def test_shortcut_reference_image_is_stripped(self) -> None:
        """Bare ![alt] resolves against a definition elsewhere in the message."""
        result = _render_agent_text(
            "See ![beacon] here.\n\n[beacon]: https://attacker.test/track.png"
        )
        assert "attacker.test" not in result
        assert "![" not in result

    def test_orphan_reference_definition_is_removed(self) -> None:
        """A definition with no image still names a URL, so it does not survive."""
        result = _render_agent_text("Hello.\n\n[b]: https://attacker.test/track.png")
        assert "attacker.test" not in result

    @pytest.mark.parametrize(
        "definition",
        [
            "[b]: <https://attacker.test/track.png>",
            '[b]: https://attacker.test/track.png "a) title"',
            "[b]: https://attacker.test/track.png 'title'",
            "[b]: https://attacker.test/track.png (title)",
        ],
    )
    def test_definition_with_title_or_angle_destination_is_removed(
        self, definition: str
    ) -> None:
        """A destination may be bracketed and may carry a title of any quoting."""
        result = _render_agent_text(f"See ![beacon][b] here.\n\n{definition}")
        assert "attacker.test" not in result


class TestRenderAgentTextKeepsProse:
    """A sentence shaped like a definition is prose, and must reach the customer."""

    def test_bracketed_lead_in_with_trailing_prose_survives(self) -> None:
        """Trailing prose means the line is not a definition. It was being deleted."""
        text = "Your bill is ready.\n[Note]: payment is due on the 15th.\nThanks!"
        assert _render_agent_text(text) == text

    @pytest.mark.parametrize(
        "text",
        [
            "[Note]: payment is due on the 15th.",
            "[Important]: call us before Friday to avoid a late fee.",
            "[Tip]: try restarting the router first.",
        ],
    )
    def test_prose_after_the_destination_is_not_a_definition(self, text: str) -> None:
        assert _render_agent_text(text) == text


class TestRenderAgentTextPreservesFormatting:
    """Markdown the KB answers depend on must survive untouched."""

    def test_bold_survives(self) -> None:
        assert _render_agent_text("Use **bold** text.") == "Use **bold** text."

    def test_bullets_survive(self) -> None:
        text = "Options:\n- Essential\n- Unlimited"
        assert _render_agent_text(text) == text

    def test_bullet_resembling_a_reference_definition_survives(self) -> None:
        """The definition pattern is anchored to line start, so bullets are safe."""
        text = "- [note]: not a definition line"
        assert _render_agent_text(text) == text

    def test_links_survive(self) -> None:
        text = "See [the policy](https://example.com/policy) for details."
        assert _render_agent_text(text) == text

    def test_link_is_not_mistaken_for_an_image(self) -> None:
        """A link differs from an image only by the leading '!'."""
        result = _render_agent_text("[not an image](http://x/y.png)")
        assert result == "[not an image](http://x/y.png)"


class TestRenderAgentTextCombined:
    """Both transformations apply together."""

    def test_amount_and_image_in_one_message(self) -> None:
        result = _render_agent_text(
            "Your bill is $22.00. ![chart](https://attacker.test/beacon.png)"
        )
        assert result == r"Your bill is \$22.00. chart"
        assert "attacker.test" not in result

    def test_amount_image_and_formatting_together(self) -> None:
        result = _render_agent_text(
            "**Total: $22.00**\n- paid\n![x](http://x/y.png)\n[link](http://z)"
        )
        assert result == "**Total: \\$22.00**\n- paid\nx\n[link](http://z)"


class TestRenderAgentTextEdgeCases:
    """Inputs that must not raise."""

    def test_empty_string(self) -> None:
        assert _render_agent_text("") == ""

    @pytest.mark.parametrize(
        "text",
        [
            "![unclosed(http://x/y.png",
            "!not an image",
        ],
    )
    def test_malformed_image_syntax_is_left_alone(self, text: str) -> None:
        """Only well-formed image syntax is stripped; the rest passes through."""
        assert _render_agent_text(text) == text

    def test_space_before_paren_is_a_shortcut_reference_not_malformed(self) -> None:
        """`![alt] (url)` is a shortcut reference image plus literal text.

        CommonMark resolves a bare `![alt]` against a `[alt]: url` definition
        anywhere in the document, so the reference is stripped and the trailing
        parenthesised text is left as the literal text it is. The cost of covering
        the shortcut form is that any `![x]` collapses to `x`.
        """
        assert _render_agent_text("![alt] (http://x/y.png)") == "alt (http://x/y.png)"
