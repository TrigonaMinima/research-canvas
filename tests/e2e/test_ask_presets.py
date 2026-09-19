"""Question chips in the ask popover: one click instead of a typed sentence."""

from __future__ import annotations

import pytest
from playwright.sync_api import expect
from tests.fixtures.selection import QUOTE, highlight

from research_canvas.config import DEFAULT_ASK_PRESETS, MAX_PRESET_LABEL_CHARS, MAX_PRESETS

pytestmark = pytest.mark.e2e

CHIPS = "[data-ask-preset]"
FIELD = "[data-ask-input]"
EXPLAIN = DEFAULT_ASK_PRESETS[0]


def open_popover(page, box="b1", needle=QUOTE):
    highlight(page, box, needle)
    page.wait_for_selector("[data-ask]")


def write_chips(page, chips):
    """Write the chips the way Settings does, then read them back into the app."""
    page.evaluate(
        """async (presets) => {
          const r = await fetch('/api/presets', {
            method: 'PUT',
            headers: {'content-type': 'application/json'},
            body: JSON.stringify({presets}),
          });
          if (!r.ok) throw new Error(await r.text());
        }""",
        chips,
    )
    page.reload()
    page.wait_for_selector("[data-box]")


def test_a_highlight_offers_one_chip_per_configured_question(canvas):
    open_popover(canvas)
    expect(canvas.locator(CHIPS)).to_have_count(len(DEFAULT_ASK_PRESETS))


def test_a_chip_is_named_by_its_label(canvas):
    open_popover(canvas)
    expect(canvas.locator(CHIPS).first).to_have_text(EXPLAIN["label"])


def test_clicking_a_chip_fills_the_question(canvas):
    open_popover(canvas)
    canvas.locator(CHIPS).first.click()
    expect(canvas.locator(FIELD)).to_have_value(EXPLAIN["question"])


def test_clicking_a_chip_keeps_the_popover_open(canvas):
    open_popover(canvas)
    canvas.locator(CHIPS).first.click()
    expect(canvas.locator("[data-ask]")).to_have_count(1)


def test_a_second_chip_replaces_the_first(canvas):
    open_popover(canvas)
    canvas.locator(CHIPS).first.click()
    canvas.locator(CHIPS).nth(1).click()
    expect(canvas.locator(FIELD)).to_have_value(DEFAULT_ASK_PRESETS[1]["question"])


def test_the_filled_question_is_still_editable(canvas):
    open_popover(canvas)
    canvas.locator(CHIPS).first.click()
    canvas.keyboard.type(" Keep it short.")
    expect(canvas.locator(FIELD)).to_have_value(f"{EXPLAIN['question']} Keep it short.")


def test_enter_after_a_chip_sends_the_chips_question(canvas):
    open_popover(canvas)
    canvas.locator(CHIPS).first.click()
    canvas.keyboard.press("Enter")
    expect(canvas.locator('[data-box="b2"] [data-question]')).to_have_text(EXPLAIN["question"])


def test_the_edited_question_is_what_gets_sent(canvas):
    open_popover(canvas)
    canvas.locator(CHIPS).first.click()
    canvas.keyboard.type(" Keep it short.")
    canvas.click("[data-ask-send]")
    expect(canvas.locator('[data-box="b2"] [data-question]')).to_contain_text("Keep it short.")


def test_typing_by_hand_still_works_with_no_chip_clicked(canvas):
    open_popover(canvas)
    canvas.fill(FIELD, "What is a residual connection?")
    canvas.click("[data-ask-send]")
    expect(canvas.locator('[data-box="b2"] [data-question]')).to_have_text(
        "What is a residual connection?"
    )


def test_chips_written_in_settings_show_on_the_next_highlight(canvas):
    canvas.click("[data-chrome] [data-settings-open]")
    canvas.wait_for_selector("[data-settings]")
    canvas.locator("[data-preset-label]").first.fill("Plainly")
    canvas.click("[data-settings-save]")
    canvas.wait_for_selector("[data-settings]", state="detached")
    open_popover(canvas)
    expect(canvas.locator(CHIPS).first).to_have_text("Plainly")


def test_no_chip_row_when_every_chip_is_deleted(canvas):
    write_chips(canvas, [])
    open_popover(canvas)
    expect(canvas.locator(CHIPS)).to_have_count(0)
    expect(canvas.locator("[data-ask-presets]")).to_have_count(0)


def test_a_full_set_of_long_chips_stays_inside_the_popover(canvas):
    long_name = "x" * MAX_PRESET_LABEL_CHARS
    write_chips(
        canvas,
        [
            {"label": f"{long_name[:-1]}{n}", "question": "Explain this."}
            for n in range(MAX_PRESETS)
        ],
    )
    open_popover(canvas)
    overflow = canvas.evaluate("""() => {
      const ask = document.querySelector('[data-ask]');
      return ask.scrollWidth - ask.clientWidth;
    }""")
    assert overflow <= 1


def test_the_send_button_stays_on_screen_under_a_full_set_of_chips(canvas):
    write_chips(
        canvas,
        [{"label": f"Chip {n}", "question": "Explain this."} for n in range(MAX_PRESETS)],
    )
    # A short window puts the passage low, which is where a taller popover used to
    # push its own footer, and the Ask button with it, off the bottom.
    canvas.set_viewport_size({"width": 1440, "height": 520})
    open_popover(canvas)
    on_screen = canvas.evaluate("""() => {
      const box = document.querySelector('[data-ask-send]').getBoundingClientRect();
      return box.bottom <= window.innerHeight && box.top >= 0;
    }""")
    assert on_screen


def test_the_chips_sit_in_a_named_group_of_buttons(canvas):
    open_popover(canvas)
    group = canvas.locator("[data-ask-presets]")
    expect(group).to_have_attribute("role", "group")
    assert canvas.locator(f"{CHIPS}[type='button']").count() == len(DEFAULT_ASK_PRESETS)
