"""A press on a box header is a click or a drag, told apart by how far it travels.

Under `DRAG_SLOP` screen pixels the reader meant to click: the box folds, stays where it
is, and is not pinned. From there up it is a drag, as it always was: the box moves and
its fold state is left alone.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import expect
from tests.fixtures.viewport import (
    answer_in_reach,
    box_rect,
    canvas_id_of,
    drag_header_by,
    press_header,
)

from research_canvas.config import DRAG_SLOP

pytestmark = pytest.mark.e2e


def stored_pinned(page, server: str, box: str):
    """The pinned flag as the server kept it, after the background patch has landed."""
    page.wait_for_timeout(400)
    view = page.request.get(f"{server}/api/canvases/{canvas_id_of(page)}").json()
    return {b["id"]: b for b in view["boxes"]}[box].get("pinned")


def test_should_not_fold_the_box_when_its_header_is_dragged(canvas):
    drag_header_by(canvas, "b1", 0, 150)
    expect(canvas.locator('[data-box="b1"]')).not_to_have_attribute("data-collapsed", "1")


def test_should_keep_a_folded_box_folded_when_its_header_is_dragged(canvas):
    canvas.click('[data-box="b1"] [data-collapse]')
    drag_header_by(canvas, "b1", 0, 150)
    expect(canvas.locator('[data-box="b1"]')).to_have_attribute("data-collapsed", "1")


def test_should_fold_the_box_when_the_press_wobbles_by_a_pixel(canvas):
    press_header(canvas, "b1", 1, 1)
    expect(canvas.locator('[data-box="b1"]')).to_have_attribute("data-collapsed", "1")


def test_should_not_move_the_box_when_the_press_wobbles_by_a_pixel(canvas):
    before = box_rect(canvas, "b1")
    press_header(canvas, "b1", 1, 1)
    after = box_rect(canvas, "b1")
    # The press folds the box, so its height changes. Only the place is compared.
    assert (after["x"], after["y"]) == pytest.approx((before["x"], before["y"]), abs=0.01)


def test_should_not_pin_the_box_when_the_press_wobbles_by_a_pixel(canvas, server):
    answer_in_reach(canvas)
    press_header(canvas, "b2", 1, 1)
    # Proof the press landed on the header: a miss would leave the box unpinned as well.
    expect(canvas.locator('[data-box="b2"]')).to_have_attribute("data-collapsed", "1")
    assert not stored_pinned(canvas, server, "b2")


def test_should_fold_the_box_when_the_press_stops_just_short_of_the_threshold(canvas):
    press_header(canvas, "b1", DRAG_SLOP - 1)
    expect(canvas.locator('[data-box="b1"]')).to_have_attribute("data-collapsed", "1")


def test_should_move_the_box_when_the_press_reaches_the_threshold(canvas):
    before = box_rect(canvas, "b1")
    press_header(canvas, "b1", DRAG_SLOP)
    assert box_rect(canvas, "b1")["x"] != pytest.approx(before["x"], abs=0.01)


def test_should_not_fold_the_box_when_the_press_reaches_the_threshold(canvas):
    press_header(canvas, "b1", DRAG_SLOP)
    expect(canvas.locator('[data-box="b1"]')).not_to_have_attribute("data-collapsed", "1")
