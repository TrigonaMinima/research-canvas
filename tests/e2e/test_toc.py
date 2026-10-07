"""A contents list in every box that has enough headings to need one.

A long box is hard to move through on a canvas that never scrolls, so a box with three
or more h1 to h3 headings carries a "Contents (n)" strip. The strip starts closed, keeps
its open state per box across a reload, and a click on an entry pans the camera to that
heading, unfolding any section that hides it. The strip sits outside `[data-body]`, so
the rendered plain text, and every stored anchor measured against it, stays as it was.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import expect
from tests.fixtures.editor import SAVE_TOP, edit, open_editor
from tests.fixtures.sections import THREE_HEADINGS, chevron
from tests.fixtures.selection import plain_text
from tests.fixtures.viewport import fold_help, wait_for_camera

from .conftest import FIXTURES, canvas_from

pytestmark = pytest.mark.e2e

TOC_DOC = (FIXTURES / "toc_doc.md").read_text(encoding="utf-8")

BOX = '[data-box="b1"]'
TOC = f"{BOX} [data-toc]"
TOGGLE = f"{BOX} [data-toc-toggle]"
LIST = f"{BOX} [data-toc-list]"
ENTRY = f"{BOX} [data-toc-key]"

HEADINGS = ["Alpha Part", "Beta Part", "Gamma Part", "Delta Part", "Epsilon Part"]

TWO_HEADINGS = "# One\n\nFirst paragraph.\n\n## Two\n\nSecond paragraph.\n"
TWO_PLUS_H4 = "# One\n\nFirst.\n\n## Two\n\nSecond.\n\n#### Four\n\nFourth.\n"

# Where a heading sits against the window, once the camera has stopped.
ON_SCREEN = """(key) => {
  const h = document.querySelector('[data-box="b1"] [data-sec="' + key + '"]').firstElementChild;
  const r = h.getBoundingClientRect();
  return r.top >= 0 && r.bottom <= window.innerHeight
      && r.left >= 0 && r.right <= window.innerWidth;
}"""

# A drag cannot start on text the browser refuses to select.
USER_SELECT = """() => [
  document.querySelector('[data-box="b1"] [data-toc]'),
  document.querySelector('[data-box="b1"] [data-toc-key]'),
].map((el) => getComputedStyle(el).userSelect)"""

# The nesting a reader sees: each entry's depth is the number of lists above it.
DEPTHS = """() => [...document.querySelectorAll('[data-box="b1"] [data-toc-key]')].map((el) => {
  let depth = 0;
  for (let n = el.parentElement; n && !n.matches('[data-toc-list]'); n = n.parentElement) {
    if (n.tagName === 'OL' || n.tagName === 'UL') depth++;
  }
  return depth;
})"""


@pytest.fixture
def canvas(app):
    """A long document: five listed headings across three levels, one h4 that must not
    be listed, and enough text between them that the last heading starts off screen."""
    return canvas_from(app, TOC_DOC)


def open_toc(page) -> None:
    page.click(TOGGLE)
    expect(page.locator(TOGGLE)).to_have_attribute("aria-expanded", "true")


# --- when it shows -----------------------------------------------------------


def test_should_show_toc_when_box_has_three_headings(app):
    canvas_from(app, THREE_HEADINGS)
    expect(app.locator(TOC)).to_be_visible()


def test_should_hide_toc_when_box_has_two_headings(app):
    canvas_from(app, TWO_HEADINGS)
    expect(app.locator(TOC)).to_have_attribute("hidden", "")


def test_should_ignore_h4_when_counting(app):
    canvas_from(app, TWO_PLUS_H4)
    expect(app.locator(TOC)).to_have_attribute("hidden", "")


def test_should_show_toc_on_first_render_without_a_toggle(canvas):
    expect(canvas.locator(TOC)).to_be_visible()


def test_should_count_only_listed_headings_in_the_toggle(canvas):
    expect(canvas.locator(TOGGLE)).to_contain_text("Contents (5)")


# --- the list ----------------------------------------------------------------


def test_should_start_closed(canvas):
    expect(canvas.locator(TOGGLE)).to_have_attribute("aria-expanded", "false")


def test_should_hide_the_list_while_closed(canvas):
    expect(canvas.locator(LIST)).to_have_attribute("hidden", "")


def test_should_point_the_toggle_at_its_list(canvas):
    expect(canvas.locator(TOGGLE)).to_have_attribute("aria-controls", "toc-b1")


def test_should_list_headings_in_order(canvas):
    open_toc(canvas)
    expect(canvas.locator(ENTRY)).to_have_text(HEADINGS)


def test_should_nest_entries_by_heading_level(canvas):
    open_toc(canvas)
    # A top-level entry sits in the list itself; each level below adds one nested list.
    assert canvas.evaluate(DEPTHS) == [0, 1, 2, 0, 1]


def test_should_keep_open_state_after_reload(canvas):
    # The open state is patched in the background: reload only once it has landed.
    with canvas.expect_response(lambda r: r.request.method == "PATCH"):
        open_toc(canvas)
    canvas.reload()
    canvas.wait_for_selector(TOGGLE)
    expect(canvas.locator(TOGGLE)).to_have_attribute("aria-expanded", "true")


# --- jumping -----------------------------------------------------------------


def test_should_pan_to_heading_on_entry_click(canvas):
    open_toc(canvas)
    heading = canvas.locator(f'{BOX} [data-sec="epsilon-part"]').first
    assert not canvas.evaluate(ON_SCREEN, "epsilon-part"), "the heading must start off screen"
    canvas.click(f'{ENTRY}[data-toc-key="epsilon-part"]')
    wait_for_camera(canvas)
    expect(heading).to_be_attached()
    assert canvas.evaluate(ON_SCREEN, "epsilon-part")


def test_should_unfold_folded_section_on_entry_click(canvas):
    open_toc(canvas)
    chevron(canvas, "delta-part").click()
    body = canvas.locator(f'{BOX} [data-sec="delta-part"] > [data-sec-body]')
    expect(body).to_have_attribute("data-collapsed", "1")
    canvas.click(f'{ENTRY}[data-toc-key="epsilon-part"]')
    expect(body).not_to_have_attribute("data-collapsed", "1")


# --- when it hides -----------------------------------------------------------


def test_should_hide_toc_when_box_is_folded(canvas):
    fold_help(canvas)
    canvas.click(f"{BOX} .box__head [data-label]")
    expect(canvas.locator(BOX)).to_have_attribute("data-collapsed", "1")
    expect(canvas.locator(TOC)).to_have_attribute("hidden", "")


def test_should_hide_toc_while_editing(canvas):
    open_editor(canvas, "b1")
    expect(canvas.locator(TOC)).to_have_attribute("hidden", "")


def test_should_rebuild_toc_after_edit_adds_headings(app):
    canvas_from(app, TWO_HEADINGS)
    expect(app.locator(TOC)).to_have_attribute("hidden", "")
    edit(app, "b1", THREE_HEADINGS + "\n## Four\n\nFourth.\n")
    app.click(SAVE_TOP.format(box="b1"))
    expect(app.locator(TOGGLE)).to_contain_text("Contents (4)")


# --- what it must not disturb ------------------------------------------------


def test_should_leave_rendered_plain_text_unchanged(canvas):
    open_toc(canvas)
    text = plain_text(canvas, "b1")
    # The strip is outside the body, so each heading is in the plain text once, not twice.
    assert [text.count(h) for h in HEADINGS] == [1] * len(HEADINGS)


def test_should_not_count_toc_text_in_find_results(canvas):
    open_toc(canvas)
    canvas.fill("[data-find]", "Epsilon Part")
    expect(canvas.locator("[data-find-count]")).to_have_text("1/1")


def test_should_keep_toc_text_out_of_a_drag_selection(canvas):
    open_toc(canvas)
    assert canvas.evaluate(USER_SELECT) == ["none", "none"]
