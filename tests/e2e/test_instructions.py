"""Standing instructions: one global block of text, reachable from either screen."""

from __future__ import annotations

import pytest
from playwright.sync_api import expect

from research_canvas.config import INSTRUCTIONS_TOO_LONG_MESSAGE, MAX_INSTRUCTIONS_CHARS

pytestmark = pytest.mark.e2e

PANEL = "[data-instructions]"
FIELD = "[data-instructions-input]"


def open_panel(page, within="[data-empty]"):
    """The button lives in both screens, so a test says which one it means."""
    page.click(f"{within} [data-instructions-open]")
    page.wait_for_selector(PANEL)


def test_opens_from_the_empty_state(app):
    open_panel(app)
    expect(app.locator(FIELD)).to_be_visible()


def test_opens_from_the_chrome_bar(canvas):
    open_panel(canvas, "[data-chrome]")
    expect(canvas.locator(FIELD)).to_be_visible()


def test_starts_empty_when_nothing_was_ever_saved(app):
    open_panel(app)
    expect(app.locator(FIELD)).to_have_value("")


def test_saves_the_instructions(app):
    open_panel(app)
    app.fill(FIELD, "Answer in British English.")
    app.click("[data-instructions-save]")
    expect(app.locator(PANEL)).to_have_count(0)


def test_shows_the_saved_instructions_when_reopened(app):
    open_panel(app)
    app.fill(FIELD, "Answer in British English.")
    app.click("[data-instructions-save]")
    open_panel(app)
    expect(app.locator(FIELD)).to_have_value("Answer in British English.")


def test_the_same_instructions_reach_every_canvas(app):
    open_panel(app)
    app.fill(FIELD, "Answer in British English.")
    app.click("[data-instructions-save]")
    app.reload()
    app.wait_for_selector("[data-empty]")
    open_panel(app)
    expect(app.locator(FIELD)).to_have_value("Answer in British English.")


def test_escape_discards_an_unsaved_edit(app):
    open_panel(app)
    app.fill(FIELD, "Never saved.")
    app.keyboard.press("Escape")
    expect(app.locator(PANEL)).to_have_count(0)
    open_panel(app)
    expect(app.locator(FIELD)).to_have_value("")


def test_cancel_closes_the_panel(app):
    open_panel(app)
    app.click("[data-instructions-cancel]")
    expect(app.locator(PANEL)).to_have_count(0)


def test_a_click_outside_keeps_the_panel_open(canvas):
    open_panel(canvas, "[data-chrome]")
    canvas.fill(FIELD, "Halfway through a thought.")
    canvas.click("[data-viewport]", position={"x": 20, "y": 400})
    expect(canvas.locator(FIELD)).to_have_value("Halfway through a thought.")


def test_counts_the_characters_against_the_cap(app):
    open_panel(app)
    app.fill(FIELD, "12345")
    expect(app.locator("[data-instructions-count]")).to_contain_text(f"5/{MAX_INSTRUCTIONS_CHARS}")


def test_refuses_instructions_over_the_cap(app):
    open_panel(app)
    app.fill(FIELD, "x" * (MAX_INSTRUCTIONS_CHARS + 1))
    app.click("[data-instructions-save]")
    expect(app.locator("[data-toast]")).to_have_text(INSTRUCTIONS_TOO_LONG_MESSAGE)
    expect(app.locator(PANEL)).to_have_count(1)


def test_the_refusal_is_not_painted_over_by_the_empty_state(app):
    open_panel(app)
    app.fill(FIELD, "x" * (MAX_INSTRUCTIONS_CHARS + 1))
    app.click("[data-instructions-save]")
    expect(app.locator("[data-toast]")).to_have_text(INSTRUCTIONS_TOO_LONG_MESSAGE)
    # Playwright calls an occluded element visible, so ask the browser what is actually
    # on top. The empty state used to cover the toast, and the reader saw nothing.
    on_top = app.evaluate("""() => {
      const toast = document.querySelector('[data-toast]');
      const box = toast.getBoundingClientRect();
      return toast.contains(
        document.elementFromPoint(box.x + box.width / 2, box.y + box.height / 2));
    }""")
    assert on_top


def test_returns_focus_to_the_button_that_opened_it(app):
    open_panel(app)
    app.keyboard.press("Escape")
    expect(app.locator("[data-empty] [data-instructions-open]")).to_be_focused()
