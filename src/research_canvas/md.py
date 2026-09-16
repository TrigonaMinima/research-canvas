"""Markdown to HTML, plus the little bits of document inspection the app needs."""

from __future__ import annotations

import re

from markdown_it import MarkdownIt

# html=False escapes raw HTML in the source. An imported document is untrusted text.
_md = MarkdownIt("commonmark", {"html": False, "linkify": True, "typographer": True})
_md.enable(["table", "strikethrough", "linkify"])

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
