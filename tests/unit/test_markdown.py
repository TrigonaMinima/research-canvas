"""Markdown rendering and the plain text the anchors are measured against."""

from __future__ import annotations

import re

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
    assert "<p>" in md.render("Garbage $\\notarealmacro{x}$ here.\n")


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
