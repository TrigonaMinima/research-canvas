"""Markdown to HTML, plus the little bits of document inspection the app needs."""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Any

from latex2mathml.converter import convert as latex_to_mathml
from markdown_it import MarkdownIt
from markdown_it.common.utils import escapeHtml
from markdown_it.token import Token
from mdit_py_plugins.amsmath import amsmath_plugin
from mdit_py_plugins.dollarmath import dollarmath_plugin

# html=False escapes raw HTML in the source. An imported document is untrusted text.
_md = MarkdownIt("commonmark", {"html": False, "linkify": True, "typographer": True})
_md.enable(["table", "strikethrough", "linkify"])

# allow_space is off so a price in prose stays prose: with it on, "It costs $5 and $10
# to run." parses "5 and " as a formula. The cost is that "$ E = mc^2 $", padded inside
# the delimiters, is no longer maths, which is pandoc's rule too. Do not turn it back
# on. Labels are off because nothing on a canvas links to a numbered equation.
_md.use(dollarmath_plugin, double_inline=True, allow_labels=False, allow_space=False)
_md.use(amsmath_plugin)

_HEADING = re.compile(r"^\s*#{1,6}\s*(.+?)\s*#*\s*$")


def render(markdown: str) -> str:
    return _md.render(markdown)


def first_heading(markdown: str) -> str | None:
    """The title of a canvas is the document's first heading, if it has one."""
    for line in markdown.splitlines():
        match = _HEADING.match(line)
        if match and match.group(1).strip():
            return match.group(1).strip()
    return None


# --- mathematics --------------------------------------------------------------
#
# Formulas are converted here, not by a script in the browser: the page ships no maths
# engine, and an anchor is an offset into text the server already rendered.


def _mathml(latex: str, *, block: bool) -> str:
    """LaTeX to MathML, or the source back as escaped code when it will not convert."""
    try:
        return latex_to_mathml(latex, display="block" if block else "inline")
    except Exception:  # noqa: BLE001 - one unsupported macro must not fail a document
        return f"<code>{escapeHtml(latex)}</code>"


# token type -> (wrapper open, wrapper close, is this display maths?).
# A span for inline maths, never a div: a div would split the surrounding <p>.
# $$…$$ is display maths wherever it was written, so it centres itself even inline.
# math_block_label is unreachable with allow_labels=False, but an unregistered token
# type raises while rendering, so it is wired up rather than left as a crash waiting
# for a settings change.
_MATH = {
    "math_inline": ('<span class="math inline">', "</span>", False),
    "math_inline_double": ('<span class="math inline">', "</span>", True),
    "math_block": ('<div class="math block">', "</div>\n", True),
    "math_block_label": ('<div class="math block">', "</div>\n", True),
    "amsmath": ('<div class="math amsmath">', "</div>\n", True),
}


def _math_rule(self: Any, tokens: Sequence[Token], idx: int, options: Any, env: Any) -> str:
    # No whitespace inside the wrapper. Whitespace there is a text node, and an anchor
    # is an offset into that text, so it would shift every later one.
    open_, close, block = _MATH[tokens[idx].type]
    return f"{open_}{_mathml(str(tokens[idx].content).strip(), block=block)}{close}"


for _type in _MATH:
    _md.add_render_rule(_type, _math_rule)
