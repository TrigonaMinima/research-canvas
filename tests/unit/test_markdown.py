"""Markdown rendering and the plain text the anchors are measured against."""

from __future__ import annotations

import re

from research_canvas import md


def test_should_render_a_heading():
    assert re.search(r"<h1[^>]*>Title</h1>", md.render("# Title\n"))


def test_should_escape_raw_html_in_the_source():
    assert "<script>" not in md.render("<script>alert(1)</script>\n")


def test_should_render_fenced_code_without_executing_it():
    assert "<code" in md.render("```py\nprint(1)\n```\n")


def test_should_extract_the_first_heading_as_a_title():
    assert md.first_heading("#  Attention Is All You Need \n\nbody") == "Attention Is All You Need"


def test_should_return_none_when_there_is_no_heading():
    assert md.first_heading("no heading here") is None


# --- mathematics (LaTeX in, MathML out) ---------------------------------------


def test_should_render_inline_math_as_inline_mathml():
    assert 'display="inline"' in md.render("Mass and energy: $E = mc^2$.\n")


def test_should_render_display_math_as_block_mathml():
    assert 'display="block"' in md.render("$$E = mc^2$$\n")


def test_should_render_inline_double_dollar_math_as_mathml():
    """double_inline gives $$…$$ its own token type; it must be converted too."""
    assert "<math" in md.render("Mass $$E = mc^2$$ inline.\n")


def test_should_render_an_amsmath_environment_as_mathml():
    assert "<math" in md.render("\\begin{align}a_1 &= b_2\\end{align}\n")


def test_should_keep_a_subscript_in_the_rendered_math():
    assert "<msub>" in md.render("$a_1 \\le b_2$\n")


def test_should_convert_an_operator_macro_rather_than_pass_it_through():
    """&#x02264; is the converted \\le. Its absence means the source leaked out raw."""
    assert "&#x02264;" in md.render("$a_1 \\le b_2$\n")


def test_should_not_treat_currency_in_prose_as_math():
    assert "<math" not in md.render("It costs $5 and $10 to run.\n")


def test_should_not_raise_on_an_unsupported_macro():
    assert re.search(r"<p[^>]*>", md.render("Garbage $\\notarealmacro{x}$ here.\n"))


def test_should_fall_back_to_code_when_a_formula_cannot_convert():
    assert "<code" in md.render("Broken $<b>}{{$ here.\n")


def test_should_not_emit_math_for_a_formula_that_cannot_convert():
    assert "<math" not in md.render("Broken $<b>}{{$ here.\n")


def test_should_escape_a_formula_it_could_not_convert():
    assert "&lt;b&gt;" in md.render("Broken $<b>}{{$ here.\n")


def test_should_render_math_without_whitespace_between_tags():
    """Anchors are offsets into the rendered text, so a stray whitespace node shifts them."""
    assert not re.search(r">\s+<", _math_element(md.render("Mass: $E = mc^2$.\n")))


def _math_element(html: str) -> str:
    match = re.search(r"<math\b.*?</math>", html, re.DOTALL)
    assert match, f"no <math> element in {html!r}"
    return match.group(0)


TABLE = "| a | b |\n| - | - |\n| 1 | 2 |\n"


def test_should_wrap_a_table_in_a_scroll_wrapper():
    assert re.match(r'<div class="table-wrap"><table\b', md.render(TABLE))


def test_should_leave_no_whitespace_between_wrapper_and_table():
    """Anchors are offsets into the rendered text, so the wrapper may add no text node."""
    assert md.render(TABLE).endswith("</table></div>\n")


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


# --- which section a passage sits in ------------------------------------------


def test_should_name_the_heading_a_passage_sits_under():
    doc = "# Title\n\nIntro.\n\n## Pricing\n\nIt costs money.\n"
    assert md.heading_before(doc, doc.index("It costs")) == "Pricing"


def test_should_name_the_nearest_heading_above_a_passage():
    doc = "# Title\n\n## Pricing\n\nOne.\n\n## Limits\n\nTwo.\n"
    assert md.heading_before(doc, doc.index("Two.")) == "Limits"


def test_should_name_no_heading_for_text_above_every_heading():
    doc = "Loose opening line.\n\n# Title\n\nBody.\n"
    assert md.heading_before(doc, 0) is None


def test_should_ignore_a_hash_inside_a_fenced_block():
    doc = "# Title\n\n```\n# not a heading\n```\n\nBody.\n"
    assert md.heading_before(doc, doc.index("Body.")) == "Title"
