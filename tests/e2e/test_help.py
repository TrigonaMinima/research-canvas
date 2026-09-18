"""The shortcuts card in the top-right corner of the canvas.

Some gestures here are a mouse gesture with a modifier, and those announce themselves
nowhere. The card says what they are. It rests as a chip, because the desk is the thing
worth looking at, and it remembers whichever way the reader left it.
"""

from __future__ import annotations

import sys

import pytest
from playwright.sync_api import expect
from tests.fixtures.viewport import transform_of

pytestmark = pytest.mark.e2e

CARD = "[data-help]"
TOGGLE = "[data-help-toggle]"
BODY = "[data-help-body]"

# What the card should print for the modifier, on this machine.
MOD_KEY = "⌘" if sys.platform == "darwin" else "Ctrl"


def fold(page) -> None:
    page.click(TOGGLE)


def open_card(page) -> None:
    """The card opens from the chip it rests as."""
    page.click(TOGGLE)
    expect(page.locator(BODY)).to_be_visible()


def test_should_rest_as_a_chip_when_a_canvas_opens(canvas):
    """The reader came for the desk. The card waits until it is asked for."""
    expect(canvas.locator(CARD)).to_be_visible()
    expect(canvas.locator(CARD)).to_have_attribute("data-folded", "1")
    expect(canvas.locator(BODY)).to_be_hidden()


def test_should_sit_in_the_top_right_corner(canvas):
    """Under the chrome bar, clear of the minimap in the other corner."""
    card = canvas.locator(CARD).bounding_box()
    width, height = canvas.evaluate("() => [window.innerWidth, window.innerHeight]")
    assert card["x"] + card["width"] > width * 0.6, "on the right"
    assert card["y"] < height * 0.4, "near the top"
    assert card["y"] >= 53, "below the chrome bar"


def test_should_open_when_the_chip_is_clicked(canvas):
    open_card(canvas)
    expect(canvas.locator(CARD)).not_to_have_attribute("data-folded", "1")


def test_should_fold_again_when_the_header_is_clicked(canvas):
    open_card(canvas)
    fold(canvas)
    expect(canvas.locator(CARD)).to_have_attribute("data-folded", "1")
    expect(canvas.locator(BODY)).to_be_hidden()


def test_should_stay_open_on_the_next_visit(canvas):
    """A reader still learning the gestures opens it once and keeps it."""
    open_card(canvas)
    canvas.reload()
    canvas.wait_for_selector('[data-box="b1"]')
    expect(canvas.locator(BODY)).to_be_visible()


def test_should_rest_as_a_chip_again_once_it_is_folded(canvas):
    """And a reader who has read it gets the desk back on the next canvas."""
    open_card(canvas)
    fold(canvas)
    canvas.reload()
    canvas.wait_for_selector('[data-box="b1"]')
    expect(canvas.locator(BODY)).to_be_hidden()


def test_should_say_what_the_toggle_does_while_open(canvas):
    open_card(canvas)
    expect(canvas.locator(TOGGLE)).to_have_attribute("aria-expanded", "true")
    assert canvas.locator(TOGGLE).get_attribute("aria-label")


def test_should_say_what_the_toggle_does_while_folded(canvas):
    expect(canvas.locator(TOGGLE)).to_have_attribute("aria-expanded", "false")
    assert canvas.locator(TOGGLE).get_attribute("aria-label")


def test_should_print_the_modifier_this_machine_uses(canvas):
    """A Mac reader is told about ⌘ and everyone else about Ctrl. One card, either way."""
    open_card(canvas)
    keys = canvas.locator("[data-mod]")
    assert keys.count() > 0
    for i in range(keys.count()):
        assert keys.nth(i).inner_text().strip() == MOD_KEY


def test_should_name_the_gestures_that_have_no_other_sign(canvas):
    """The band, the ring and the keys that send or save announce themselves nowhere."""
    open_card(canvas)
    text = canvas.locator(CARD).inner_text()
    assert "band" in text
    assert "ring a box" in text
    assert "Esc" in text


def test_should_leave_out_the_gestures_a_reader_finds_by_trying(canvas):
    """Dragging the desk and clicking a highlight are found in the first minute. A card
    that lists them buries the three that are not."""
    open_card(canvas)
    text = canvas.locator(CARD).inner_text()
    assert "Read" not in text
    assert "Follow" not in text
    assert "pan" not in text


def test_should_not_pan_the_desk_when_the_card_is_dragged(canvas):
    open_card(canvas)
    before = transform_of(canvas)
    card = canvas.locator(CARD).bounding_box()
    canvas.mouse.move(card["x"] + card["width"] / 2, card["y"] + card["height"] / 2)
    canvas.mouse.down()
    canvas.mouse.move(card["x"] - 200, card["y"] + 200, steps=6)
    canvas.mouse.up()
    assert transform_of(canvas) == before


def test_should_keep_the_card_off_the_first_screen(app):
    """Playwright calls an occluded element visible, so ask the browser what is on top.
    The card belongs to a canvas, and the first screen has no canvas to explain."""
    on_top = app.evaluate(
        """() => {
      const card = document.querySelector('[data-help]');
      if (!card) return false;
      const box = card.getBoundingClientRect();
      return card.contains(
        document.elementFromPoint(box.x + box.width / 2, box.y + box.height / 2));
    }"""
    )
    assert not on_top
