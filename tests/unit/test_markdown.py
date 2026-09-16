"""Markdown rendering and the plain text the anchors are measured against."""

from __future__ import annotations

from research_canvas import md


def test_should_render_a_heading():
    assert "<h1>" in md.render("# Title\n")


def test_should_escape_raw_html_in_the_source():
    assert "<script>" not in md.render("<script>alert(1)</script>\n")


def test_should_render_fenced_code_without_executing_it():
    assert "<code" in md.render("```py\nprint(1)\n```\n")


def test_should_extract_the_first_heading_as_a_title():
    assert md.first_heading("#  Attention Is All You Need \n\nbody") == "Attention Is All You Need"


def test_should_return_none_when_there_is_no_heading():
    assert md.first_heading("no heading here") is None
