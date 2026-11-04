"""Every rendered block names the source line edit mode should open at."""

# Guards 2679763 (fix: keep the reader's place when edit mode opens and closes).

from __future__ import annotations

import re

from research_canvas import md

# --- source line marks (data-line, data-line-end) ------------------------------


def _tag(html: str, name: str, nth: int = 0) -> str:
    """The nth opening tag of the given name, attributes included."""
    tags = re.findall(rf"<{name}\b[^>]*>", html)
    assert len(tags) > nth, f"no <{name}> #{nth} in {html!r}"
    return tags[nth]


def test_should_mark_a_paragraph_with_its_source_line():
    html = md.render("# Title\n\nSome text.\n")
    assert 'data-line="2"' in _tag(html, "p")


def test_should_mark_a_heading_with_its_source_line():
    html = md.render("Intro.\n\n## Section\n")
    assert 'data-line="2"' in _tag(html, "h2")


def test_should_mark_a_list_item_with_its_own_line():
    html = md.render("- first\n- second\n- third\n")
    assert 'data-line="1"' in _tag(html, "li", 1)


def test_should_mark_a_fenced_block_with_its_source_line():
    html = md.render("Before.\n\n```py\nprint(1)\n```\n")
    fence = re.search(r"<pre\b.*?</pre>", html, re.DOTALL)
    assert fence and 'data-line="2"' in fence.group(0)


def test_should_mark_a_display_maths_block_with_its_source_line():
    html = md.render("Before.\n\n$$\nE = mc^2\n$$\n")
    assert re.search(r'<div class="math block"[^>]*data-line="2"', html)


def test_should_mark_the_end_line_of_a_multi_line_paragraph():
    html = md.render("one\ntwo\nthree\n")
    assert 'data-line-end="3"' in _tag(html, "p")


def test_should_add_no_text_to_the_rendered_body():
    """Passes before the change too: the marks are attributes, never text."""
    html = md.render("# Title\n\nSome text.\n\n- one\n- two\n")
    text = re.sub(r"<[^>]+>", "", html)
    assert text.split() == ["Title", "Some", "text.", "one", "two"]
