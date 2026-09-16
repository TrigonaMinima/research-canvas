"""LaTeX on the canvas: formulas render as MathML, and highlights survive them.

Math arrives as real `<math>` elements rendered on the server, so a formula sits in
the middle of the text nodes an anchor is measured against. These tests pin both
halves: the formula is a formula, and a highlight that touches one still resolves
back to the same passage after a reload.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import expect
from tests.fixtures.editor import SAVE_BUTTON, edit
from tests.fixtures.selection import SELECT, find_offsets, plain_text, send_question
from tests.fixtures.viewport import box_rect, edge_start, rect_of

from .conftest import FIXTURES, canvas_from

pytestmark = pytest.mark.e2e

MATH_DOC = (FIXTURES / "math_doc.md").read_text(encoding="utf-8")

BODY = '[data-box="b1"] [data-body]'

# The paragraph that carries an inline formula between two runs of prose.
BEFORE_FORMULA = "divides by"
AFTER_FORMULA = "before the softmax"

# The formula highlighted on its own. Its rendered text is long enough to clear
# MIN_SELECTION_CHARS, so the ask popover opens the way prose opens it.
FORMULA_TOKEN = "Divisor"

QUESTION = "What does this mean?"

# An answer box body written through the editor, because the fake `claude` cannot
# emit math. It lands through the same server-side render the answer stream uses.
# No brackets: CodeMirror closes those for you, which would rewrite the source.
ANSWER_WITH_MATH = "The bound is $Bound = 2n$ for every step."

# Select exactly one formula: both edges land inside the <math> element, which is
# where a reader's drag across a formula leaves them.
SELECT_FORMULA = """([box, token]) => {
  const body = document.querySelector('[data-box="' + box + '"] [data-body]');
  const math = [...body.querySelectorAll('math')].find(
    (m) => m.textContent.includes(token));
  if (!math) return null; // say what is missing instead of throwing from a walker
  const walker = document.createTreeWalker(math, NodeFilter.SHOW_TEXT);
  const nodes = [];
  let node;
  while ((node = walker.nextNode())) nodes.push(node);
  const last = nodes[nodes.length - 1];
  const range = document.createRange();
  range.setStart(nodes[0], 0);
  range.setEnd(last, last.nodeValue.length);
  const sel = window.getSelection();
  sel.removeAllRanges();
  sel.addRange(range);
  document.querySelector('[data-viewport]').dispatchEvent(
    new MouseEvent('mouseup', {bubbles: true, clientX: 500, clientY: 400}));
  return range.toString();
}"""


@pytest.fixture
def math_canvas(app):
    """A canvas whose document carries inline, display, and align math."""
    return canvas_from(app, MATH_DOC)


def highlight_across_the_formula(page) -> None:
    start, _ = find_offsets(page, "b1", BEFORE_FORMULA)
    _, end = find_offsets(page, "b1", AFTER_FORMULA)
    page.evaluate(SELECT, ["b1", start, end])


def highlight_the_formula(page) -> None:
    quoted = page.evaluate(SELECT_FORMULA, ["b1", FORMULA_TOKEN])
    assert quoted, f"no <math> element carrying {FORMULA_TOKEN!r} in box b1"


def stored_anchor(page, server: str) -> dict:
    """The anchor as the server kept it, read back over the API."""
    canvas_id = page.evaluate("() => new URLSearchParams(location.search).get('c')")
    view = page.request.get(f"{server}/api/canvases/{canvas_id}").json()
    return view["anchors"][0]


# --- formulas render ------------------------------------------------------


def test_should_render_inline_math_as_mathml(math_canvas):
    expect(math_canvas.locator(f"{BODY} math").first).to_be_visible()


def test_should_render_display_math_as_a_block(math_canvas):
    expect(math_canvas.locator(f'{BODY} math[display="block"]').first).to_be_visible()


def test_should_render_an_align_block_as_mathml(math_canvas):
    expect(math_canvas.locator(BODY)).not_to_contain_text("\\begin{align}")
    expect(math_canvas.locator(f'{BODY} math:has-text("Sublayer")')).to_have_count(1)


def test_should_leave_currency_amounts_as_prose(math_canvas):
    """`$5 and $10` is a grocery bill, not a formula."""
    paragraph = math_canvas.locator(f"{BODY} p", has_text="It costs")
    expect(paragraph.locator("math")).to_have_count(0)


# --- a highlight that crosses a formula -----------------------------------


def test_should_store_a_quote_that_matches_its_offsets_across_a_formula(math_canvas, server):
    """The quote is cut from the rendered plain text, so the two can never disagree."""
    highlight_across_the_formula(math_canvas)
    send_question(math_canvas, QUESTION)
    math_canvas.wait_for_selector('[data-box="b2"]')

    anchor = stored_anchor(math_canvas, server)
    rendered = plain_text(math_canvas, "b1")[anchor["start"] : anchor["end"]]

    assert anchor["quote"] == rendered


def test_should_restore_a_highlight_across_a_formula_after_a_reload(math_canvas):
    highlight_across_the_formula(math_canvas)
    send_question(math_canvas, QUESTION)
    math_canvas.wait_for_selector('[data-box="b2"][data-status="done"]', timeout=20000)

    math_canvas.reload()
    math_canvas.wait_for_selector('[data-box="b2"]')

    expect(math_canvas.locator('[data-box="b1"] mark[data-anchor]').first).to_be_visible()
    expect(math_canvas.locator('[data-edges] [data-edge="b2"]')).to_have_count(1)


# --- a highlight that is nothing but a formula ----------------------------


def test_should_wrap_a_formula_only_selection_in_a_single_mark(math_canvas):
    """A mark cannot live inside MathML, so the whole formula is marked once."""
    highlight_the_formula(math_canvas)
    send_question(math_canvas, QUESTION)
    math_canvas.wait_for_selector('[data-box="b2"]')

    expect(math_canvas.locator('[data-box="b1"] mark[data-anchor]')).to_have_count(1)
    expect(math_canvas.locator('[data-box="b1"] mark[data-anchor] > math')).to_have_count(1)


def test_should_draw_an_edge_for_a_formula_only_highlight(math_canvas):
    highlight_the_formula(math_canvas)
    send_question(math_canvas, QUESTION)
    math_canvas.wait_for_selector('[data-box="b2"][data-status="done"]', timeout=20000)

    expect(math_canvas.locator('[data-edges] [data-edge="b2"]')).to_have_count(1)


def test_should_leave_that_edge_from_the_formula_not_the_box_edge(math_canvas):
    """A <mark> around a <math> must measure, or every formula edge would fall back."""
    highlight_the_formula(math_canvas)
    send_question(math_canvas, QUESTION)
    math_canvas.wait_for_selector('[data-box="b2"][data-status="done"]', timeout=20000)

    mark = rect_of(math_canvas, '[data-box="b1"] mark[data-anchor-edge]')
    start = edge_start(math_canvas, "b2")
    box = box_rect(math_canvas, "b1")
    assert start["x"] < box["x"] + box["w"] - 1, "the edge left the box, not the formula"
    assert abs(start["x"] - (mark["x"] + mark["w"])) <= 2


# --- math in an answer ----------------------------------------------------


def test_should_render_math_in_an_answer_box(math_canvas):
    """The body goes in through the editor: the fake `claude` has no way to emit math."""
    highlight_across_the_formula(math_canvas)
    send_question(math_canvas, QUESTION)
    math_canvas.wait_for_selector('[data-box="b2"][data-status="done"]', timeout=20000)

    edit(math_canvas, "b2", ANSWER_WITH_MATH)
    math_canvas.click(SAVE_BUTTON.format(box="b2"))

    body = math_canvas.locator('[data-box="b2"] [data-body]')
    expect(body.locator('math:has-text("Bound")')).to_have_count(1)
