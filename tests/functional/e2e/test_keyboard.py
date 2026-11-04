"""Every box action is reachable from the keyboard alone (#60).

Tab into a box and that box is the focused box, so the arrows fold it. Find steps
through matches on Enter and Shift+Enter. The contents list answers Enter and Space.
The picture view's step buttons are in tests/regression/e2e/test_zoom_step_keeps_focus.py.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import expect

from tests.fixtures.e2e_app import FIXTURES, canvas_from
from tests.fixtures.keyboard import tab_stops
from tests.fixtures.viewport import fold_help, transform_of, wait_for_camera

pytestmark = pytest.mark.e2e

ROOT = '[data-box="b1"]'
FOCUSED = '[data-box][data-focused="1"]'
FIND = "[data-find]"
FIND_COUNT = "[data-find-count]"
TOC_DOC = (FIXTURES / "toc_doc.md").read_text(encoding="utf-8")
TOGGLE = f"{ROOT} [data-toc-toggle]"
ENTRY = f"{ROOT} [data-toc-key]"
ON_SCREEN = """(key) => {
  const h = document.querySelector('[data-box="b1"] [data-sec="' + key + '"]').firstElementChild;
  const r = h.getBoundingClientRect();
  return r.top >= 0 && r.bottom <= window.innerHeight
      && r.left >= 0 && r.right <= window.innerWidth;
}"""


def tab_into_box(page, box: str = "b1") -> None:
    fold_help(page)
    stops = tab_stops(page)
    assert stops[-1]["box"] == box, f"Tab never reached a box: {stops}"


# --- a way into a box ---------------------------------------------------------


def test_should_focus_a_box_when_tab_reaches_a_control_in_it(canvas):
    tab_into_box(canvas)
    expect(canvas.locator(ROOT)).to_have_attribute("data-focused", "1")


def test_should_mark_a_tabbed_box_as_current(canvas):
    tab_into_box(canvas)
    expect(canvas.locator(ROOT)).to_have_attribute("aria-current", "true")


def test_should_fold_a_tabbed_box_on_arrow_left(canvas):
    tab_into_box(canvas)
    canvas.keyboard.press("ArrowLeft")
    expect(canvas.locator(ROOT)).to_have_attribute("data-collapsed", "1")


def test_should_unfold_a_tabbed_box_on_arrow_right_after_folding_it(canvas):
    tab_into_box(canvas)
    canvas.keyboard.press("ArrowLeft")
    expect(canvas.locator(ROOT)).to_have_attribute("data-collapsed", "1")
    canvas.keyboard.press("ArrowRight")
    expect(canvas.locator(ROOT)).not_to_have_attribute("data-collapsed", "1")


def test_should_not_move_the_camera_when_tab_focuses_a_box(canvas):
    fold_help(canvas)
    before = transform_of(canvas)
    tab_into_box(canvas)
    expect(canvas.locator(ROOT)).to_have_attribute("data-focused", "1")
    assert transform_of(canvas) == before


def test_should_leave_no_box_focused_while_tab_walks_the_chrome_bar(canvas):
    fold_help(canvas)
    canvas.evaluate("() => document.activeElement?.blur()")
    canvas.keyboard.press("Tab")
    expect(canvas.locator(FOCUSED)).to_have_count(0)


def test_should_not_focus_a_box_when_its_button_is_clicked_with_cmd(canvas):
    # A pointer focus is not a keyboard one: the Cmd click stays a selection toggle.
    canvas.click(f"{ROOT} [data-collapse]", modifiers=["ControlOrMeta"])
    expect(canvas.locator(FOCUSED)).to_have_count(0)


# --- the tab order ------------------------------------------------------------

# The desk comes first in the page, so Tab reaches the boxes before the bar above them.
CHROME_ORDER = [
    "data-crumb-home",
    "data-title",
    "data-find",
    "data-find-prev",
    "data-find-next",
    "data-zoom-out",
    "data-zoom-in",
    "data-zoom-fit",
]


def test_should_walk_the_chrome_bar_in_reading_order(canvas):
    stops = [s["stop"] for s in tab_stops(canvas, whole_cycle=True)]
    assert [s for s in stops if s in CHROME_ORDER] == CHROME_ORDER


def test_should_reach_the_desk_before_its_boxes(canvas):
    stops = tab_stops(canvas)
    assert [s["stop"] for s in stops[:1]] == ["data-viewport"]


def test_should_reach_the_chrome_bar_after_the_boxes(canvas):
    stops = tab_stops(canvas, whole_cycle=True)
    last_box = max(i for i, s in enumerate(stops) if s["box"])
    assert [s["stop"] for s in stops[last_box + 1 :]][:1] == ["data-crumb-home"]


# --- find steps on Enter --------------------------------------------------------


def find(page, query: str) -> int:
    page.fill(FIND, query)
    total = int(page.locator(FIND_COUNT).inner_text().split("/")[1])
    assert total > 1, "the query needs more than one match to step through"
    return total


def test_should_step_to_the_next_match_on_enter(canvas):
    total = find(canvas, "the")
    canvas.press(FIND, "Enter")
    expect(canvas.locator(FIND_COUNT)).to_have_text(f"2/{total}")


def test_should_step_back_to_the_last_match_on_shift_enter(canvas):
    total = find(canvas, "the")
    canvas.press(FIND, "Shift+Enter")
    expect(canvas.locator(FIND_COUNT)).to_have_text(f"{total}/{total}")


def test_should_match_the_next_button_on_enter(canvas):
    total = find(canvas, "the")
    canvas.click("[data-find-next]")
    canvas.press(FIND, "Enter")
    expect(canvas.locator(FIND_COUNT)).to_have_text(f"3/{total}")


def test_should_keep_the_query_when_enter_steps(canvas):
    find(canvas, "the")
    canvas.press(FIND, "Enter")
    expect(canvas.locator(FIND)).to_have_value("the")


def test_should_keep_the_focus_in_find_when_enter_steps(canvas):
    find(canvas, "the")
    canvas.press(FIND, "Enter")
    expect(canvas.locator(FIND)).to_be_focused()


# --- the contents list from the keyboard --------------------------------------


@pytest.fixture
def toc_canvas(app):
    return canvas_from(app, TOC_DOC)


@pytest.mark.parametrize("key", ["Enter", "Space"])
def test_should_open_the_contents_list_from_the_keyboard(toc_canvas, key):
    toc_canvas.locator(TOGGLE).focus()
    toc_canvas.keyboard.press(key)
    expect(toc_canvas.locator(TOGGLE)).to_have_attribute("aria-expanded", "true")


def test_should_close_the_contents_list_on_a_second_enter(toc_canvas):
    toc_canvas.locator(TOGGLE).focus()
    toc_canvas.keyboard.press("Enter")
    expect(toc_canvas.locator(TOGGLE)).to_have_attribute("aria-expanded", "true")
    toc_canvas.keyboard.press("Enter")
    expect(toc_canvas.locator(TOGGLE)).to_have_attribute("aria-expanded", "false")


def test_should_keep_the_focus_on_the_toggle_after_enter(toc_canvas):
    toc_canvas.locator(TOGGLE).focus()
    toc_canvas.keyboard.press("Enter")
    expect(toc_canvas.locator(TOGGLE)).to_be_focused()


def test_should_reach_the_first_entry_with_tab_from_the_toggle(toc_canvas):
    toc_canvas.locator(TOGGLE).focus()
    toc_canvas.keyboard.press("Enter")
    toc_canvas.keyboard.press("Tab")
    expect(toc_canvas.locator(ENTRY).first).to_be_focused()


def test_should_pan_to_a_heading_when_its_entry_is_pressed_with_enter(toc_canvas):
    toc_canvas.locator(TOGGLE).focus()
    toc_canvas.keyboard.press("Enter")
    assert not toc_canvas.evaluate(ON_SCREEN, "epsilon-part"), "the heading must start off screen"
    toc_canvas.locator(f'{ENTRY}[data-toc-key="epsilon-part"]').focus()
    toc_canvas.keyboard.press("Enter")
    wait_for_camera(toc_canvas)
    assert toc_canvas.evaluate(ON_SCREEN, "epsilon-part")
