"""One box at a time is the focused box: it carries data-focused="1", and no other does.

A plain click inside a box focuses it. An edge or a highlight focuses the box it leads
to, and the way back (button or quote) focuses the parent. Bare desk clears focus, a pan
does not, and a Cmd/Ctrl click (the selection toggle) never moves it.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import expect
from tests.fixtures.selection import answer_from_root
from tests.fixtures.viewport import answer_in_reach, settled, to_client, wait_for_camera

pytestmark = pytest.mark.e2e

FOCUSED = '[data-box][data-focused="1"]'
B1 = '[data-box="b1"]'
B2 = '[data-box="b2"]'
B2_BODY = f"{B2} [data-body]"
B2_HEAD = f"{B2} .box__head [data-label]"
B2_GRIP = f"{B2} .box__head .grip"
MARK = f"{B1} mark[data-anchor]"

# zoom_to_fit moves the boxes, so a fixed desk point (as in test_select.py) can land
# inside one. Probed instead: the first grid point that is viewport and nothing else.
BARE_DESK = """() => {
  for (let y = innerHeight - 40; y > 80; y -= 30) {
    for (let x = 40; x < innerWidth - 40; x += 30) {
      const at = document.elementFromPoint(x, y);
      if (at && at.closest('[data-viewport]') && !at.closest('[data-box], [data-edge]')) {
        return [x, y];
      }
    }
  }
  return null;
}"""

# The edges layer has no viewBox, so a point on a path is already in canvas px.
# Same probe as EDGE_MIDPOINT in test_canvas.py.
EDGE_MIDPOINT = """(target) => {
  const path = document.querySelector('[data-edge="' + target + '"] path:last-of-type');
  const at = path.getPointAtLength(path.getTotalLength() / 2);
  return [at.x, at.y];
}"""


def focus_answer(page) -> None:
    """An answer on screen and focused by a click on its body text."""
    answer_in_reach(page)
    page.click(B2_BODY, position={"x": 8, "y": 8})
    expect(page.locator(B2)).to_have_attribute("data-focused", "1")


def bare_desk(page) -> tuple[float, float]:
    x, y = page.evaluate(BARE_DESK)
    return x, y


def sweep(page, start: tuple[float, float], end: tuple[float, float]) -> None:
    page.mouse.move(*start)
    page.mouse.down()
    page.mouse.move(*end, steps=8)
    page.mouse.up()


# --- a click inside a box focuses it ------------------------------------------


def test_should_focus_a_box_when_its_body_is_clicked(canvas):
    answer_in_reach(canvas)
    canvas.click(B2_BODY, position={"x": 8, "y": 8})
    expect(canvas.locator(B2)).to_have_attribute("data-focused", "1")


def test_should_focus_a_box_when_its_header_is_clicked(canvas):
    answer_in_reach(canvas)
    canvas.click(B2_HEAD)
    expect(canvas.locator(B2)).to_have_attribute("data-focused", "1")


def test_should_still_fold_a_box_when_its_header_click_focuses_it(canvas):
    answer_in_reach(canvas)
    canvas.click(B2_HEAD)
    expect(canvas.locator(B2)).to_have_attribute("data-collapsed", "1")


def test_should_focus_a_box_when_a_button_in_it_is_clicked(canvas):
    answer_in_reach(canvas)
    canvas.click(f"{B2} [data-collapse]")
    expect(canvas.locator(B2)).to_have_attribute("data-focused", "1")


# --- moving focus -------------------------------------------------------------


def test_should_move_focus_to_another_box_on_a_click(canvas):
    focus_answer(canvas)
    canvas.click(f"{B1} .box__head [data-label]")
    expect(canvas.locator(B1)).to_have_attribute("data-focused", "1")


def test_should_leave_exactly_one_focused_box_after_focus_moves(canvas):
    focus_answer(canvas)
    canvas.click(f"{B1} .box__head [data-label]")
    expect(canvas.locator(FOCUSED)).to_have_count(1)


# --- edges and highlights lead to the child -----------------------------------


def test_should_focus_the_child_when_its_edge_is_clicked(canvas):
    answer_from_root(canvas)
    x, y = canvas.evaluate(EDGE_MIDPOINT, "b2")
    canvas.mouse.click(*to_client(canvas, x, y))
    expect(canvas.locator(B2)).to_have_attribute("data-focused", "1")


def test_should_focus_the_child_when_its_highlight_is_clicked(canvas):
    answer_from_root(canvas)
    canvas.locator(MARK).first.click()
    expect(canvas.locator(B2)).to_have_attribute("data-focused", "1")


def test_should_not_focus_the_parent_when_its_highlight_is_clicked(canvas):
    answer_from_root(canvas)
    canvas.locator(MARK).first.click()
    expect(canvas.locator(B2)).to_have_attribute("data-focused", "1")
    expect(canvas.locator(B1)).not_to_have_attribute("data-focused", "1")


# --- the way back focuses the parent ------------------------------------------


def test_should_focus_the_parent_when_go_to_parent_is_clicked(canvas):
    answer_from_root(canvas)
    canvas.locator(MARK).first.click()
    expect(canvas.locator(B2)).to_have_attribute("data-focused", "1")
    wait_for_camera(canvas)  # the camera has to land before the button is hittable
    canvas.click(f"{B2} [data-goparent]")
    expect(canvas.locator(B1)).to_have_attribute("data-focused", "1")


def test_should_take_focus_off_the_child_when_go_to_parent_is_clicked(canvas):
    answer_from_root(canvas)
    canvas.locator(MARK).first.click()
    expect(canvas.locator(B2)).to_have_attribute("data-focused", "1")
    wait_for_camera(canvas)
    canvas.click(f"{B2} [data-goparent]")
    expect(canvas.locator(B2)).not_to_have_attribute("data-focused", "1")


def test_should_focus_the_parent_when_the_quote_is_clicked(canvas):
    answer_from_root(canvas)
    canvas.locator(MARK).first.click()
    expect(canvas.locator(B2)).to_have_attribute("data-focused", "1")
    wait_for_camera(canvas)
    canvas.click(f"{B2} [data-quote]")
    expect(canvas.locator(B1)).to_have_attribute("data-focused", "1")


# --- bare desk, pans, and the selection toggle --------------------------------


def test_should_clear_focus_on_a_click_on_bare_desk(canvas):
    focus_answer(canvas)
    canvas.mouse.click(*bare_desk(canvas))
    expect(canvas.locator(FOCUSED)).to_have_count(0)


def test_should_keep_focus_through_a_pan(canvas):
    focus_answer(canvas)
    x, y = bare_desk(canvas)
    sweep(canvas, (x, y), (x + 60, y - 50))
    expect(canvas.locator(B2)).to_have_attribute("data-focused", "1")


def test_should_not_focus_a_box_on_a_cmd_click(canvas):
    answer_in_reach(canvas)
    canvas.click(B2_GRIP, modifiers=["ControlOrMeta"])
    expect(canvas.locator(FOCUSED)).to_have_count(0)


def test_should_not_move_focus_on_a_cmd_click_of_another_box(canvas):
    focus_answer(canvas)
    canvas.click(f"{B1} .box__head .grip", modifiers=["ControlOrMeta"])
    expect(canvas.locator(B2)).to_have_attribute("data-focused", "1")


def test_should_not_move_focus_on_a_cmd_click_of_an_edge(canvas):
    focus_answer(canvas)
    canvas.click(f"{B1} .box__head [data-label]")
    expect(canvas.locator(B1)).to_have_attribute("data-focused", "1")
    x, y = canvas.evaluate(EDGE_MIDPOINT, "b2")
    canvas.keyboard.down("ControlOrMeta")  # mouse.click takes no modifiers of its own
    canvas.mouse.click(*to_client(canvas, x, y))
    canvas.keyboard.up("ControlOrMeta")
    settled(canvas)  # nothing to wait on when nothing should change, so wait on frames
    expect(canvas.locator(B1)).to_have_attribute("data-focused", "1")


def test_should_focus_the_box_a_selection_drag_began_in_when_it_ends_on_the_desk(canvas):
    answer_in_reach(canvas)
    body = canvas.locator(B2_BODY).bounding_box()
    sweep(canvas, (body["x"] + 8, body["y"] + 8), bare_desk(canvas))
    expect(canvas.locator(B2)).to_have_attribute("data-focused", "1")


def test_should_keep_focus_when_a_selection_drag_ends_on_the_desk(canvas):
    focus_answer(canvas)
    body = canvas.locator(B2_BODY).bounding_box()
    sweep(canvas, (body["x"] + 8, body["y"] + 8), bare_desk(canvas))
    settled(canvas)  # the release is a click on the desk: give it its frames
    expect(canvas.locator(B2)).to_have_attribute("data-focused", "1")


def test_should_keep_a_selection_in_the_question_when_its_click_moves_focus(canvas):
    answer_in_reach(canvas)
    q = canvas.locator(f"{B2} [data-question]").bounding_box()
    mid = q["y"] + q["height"] / 2
    sweep(canvas, (q["x"] + 4, mid), (q["x"] + min(q["width"] - 4, 120), mid))
    expect(canvas.locator(B2)).to_have_attribute("data-focused", "1")
    assert canvas.evaluate("() => getSelection().toString().length") > 0


def test_should_mark_the_focused_box_as_current_for_assistive_tech(canvas):
    focus_answer(canvas)
    expect(canvas.locator(B2)).to_have_attribute("aria-current", "true")


def test_should_drop_the_current_mark_when_focus_moves_away(canvas):
    focus_answer(canvas)
    canvas.click(f"{B1} .box__head [data-label]")
    expect(canvas.locator(B2)).not_to_have_attribute("aria-current", "true")


# --- going away ---------------------------------------------------------------


def test_should_leave_no_focused_box_when_the_focused_box_is_deleted(canvas):
    focus_answer(canvas)
    canvas.click(f"{B2} [data-delete]")  # no confirm step, as in test_canvas.py
    expect(canvas.locator(B2)).to_have_count(0)
    expect(canvas.locator(FOCUSED)).to_have_count(0)


def test_should_clear_focus_when_another_canvas_opens(canvas):
    focus_answer(canvas)
    canvas.click("[data-crumb-home]")
    canvas.wait_for_selector("[data-canvas-list] a")
    canvas.click("[data-canvas-list] a")
    canvas.wait_for_selector(B1)
    expect(canvas.locator(FOCUSED)).to_have_count(0)
