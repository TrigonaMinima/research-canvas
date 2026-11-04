"""Settings: one page for the standing instructions and the question chips."""

from __future__ import annotations

import pytest
from playwright.sync_api import expect

from research_canvas.config import BLANK_PRESET_MESSAGE, DEFAULT_ASK_PRESETS, MAX_PRESETS

pytestmark = pytest.mark.e2e

PANEL = "[data-settings]"
ROW = "[data-preset-row]"
NAME = "[data-preset-label]"
QUESTION = "[data-preset-question]"


def open_settings(page, within="[data-empty]"):
    """The cog lives in both screens, so a test says which one it means."""
    page.click(f"{within} [data-settings-open]")
    page.wait_for_selector(PANEL)


def test_opens_from_the_empty_state(app):
    open_settings(app)
    expect(app.locator(PANEL)).to_be_visible()


def test_opens_from_the_chrome_bar(canvas):
    open_settings(canvas, "[data-chrome]")
    expect(canvas.locator(PANEL)).to_be_visible()


def test_shows_the_default_chips_before_any_are_written(app):
    open_settings(app)
    expect(app.locator(ROW)).to_have_count(len(DEFAULT_ASK_PRESETS))
    expect(app.locator(NAME).first).to_have_value(DEFAULT_ASK_PRESETS[0]["label"])


def test_renaming_a_chip_survives_a_reload(app):
    open_settings(app)
    app.locator(NAME).first.fill("Plainly")
    app.click("[data-settings-save]")
    expect(app.locator(PANEL)).to_have_count(0)
    app.reload()
    app.wait_for_selector("[data-empty]")
    open_settings(app)
    expect(app.locator(NAME).first).to_have_value("Plainly")


def test_rewording_a_chip_question_survives_a_reload(app):
    open_settings(app)
    app.locator(QUESTION).first.fill("Say this again for a ten year old.")
    app.click("[data-settings-save]")
    app.reload()
    app.wait_for_selector("[data-empty]")
    open_settings(app)
    expect(app.locator(QUESTION).first).to_have_value("Say this again for a ten year old.")


def test_adding_a_chip_appends_an_empty_row(app):
    open_settings(app)
    app.click("[data-preset-add]")
    expect(app.locator(ROW)).to_have_count(len(DEFAULT_ASK_PRESETS) + 1)
    expect(app.locator(NAME).last).to_have_value("")


def test_a_chip_added_here_is_saved(app):
    open_settings(app)
    app.click("[data-preset-add]")
    app.locator(NAME).last.fill("Sources")
    app.locator(QUESTION).last.fill("What are the sources for this?")
    app.click("[data-settings-save]")
    open_settings(app)
    expect(app.locator(NAME).last).to_have_value("Sources")


def test_deleting_a_chip_removes_its_row(app):
    open_settings(app)
    app.locator("[data-preset-delete]").first.click()
    expect(app.locator(ROW)).to_have_count(len(DEFAULT_ASK_PRESETS) - 1)


def test_a_deleted_chip_stays_deleted(app):
    open_settings(app)
    app.locator("[data-preset-delete]").first.click()
    app.click("[data-settings-save]")
    open_settings(app)
    expect(app.locator(ROW)).to_have_count(len(DEFAULT_ASK_PRESETS) - 1)


def test_every_chip_can_be_deleted(app):
    open_settings(app)
    for _ in range(len(DEFAULT_ASK_PRESETS)):
        app.locator("[data-preset-delete]").first.click()
    app.click("[data-settings-save]")
    open_settings(app)
    expect(app.locator(ROW)).to_have_count(0)


def test_stops_offering_more_rows_at_the_cap(app):
    open_settings(app)
    for _ in range(MAX_PRESETS):
        if app.locator("[data-preset-add]").is_enabled():
            app.click("[data-preset-add]")
    expect(app.locator(ROW)).to_have_count(MAX_PRESETS)
    expect(app.locator("[data-preset-add]")).to_be_disabled()


def test_a_half_written_chip_is_refused_and_keeps_the_page_open(app):
    open_settings(app)
    app.click("[data-preset-add]")
    app.locator(QUESTION).last.fill("A question with nobody to name it.")
    app.click("[data-settings-save]")
    expect(app.locator("[data-toast]")).to_have_text(BLANK_PRESET_MESSAGE)
    expect(app.locator(PANEL)).to_have_count(1)


def test_an_untouched_empty_row_is_dropped_rather_than_refused(app):
    open_settings(app)
    app.click("[data-preset-add]")
    app.click("[data-settings-save]")
    expect(app.locator(PANEL)).to_have_count(0)
    open_settings(app)
    expect(app.locator(ROW)).to_have_count(len(DEFAULT_ASK_PRESETS))


def test_escape_discards_an_unsaved_chip_edit(app):
    open_settings(app)
    app.locator(NAME).first.fill("Never saved")
    app.keyboard.press("Escape")
    expect(app.locator(PANEL)).to_have_count(0)
    open_settings(app)
    expect(app.locator(NAME).first).to_have_value(DEFAULT_ASK_PRESETS[0]["label"])


def test_cancel_closes_the_page(app):
    open_settings(app)
    app.click("[data-settings-cancel]")
    expect(app.locator(PANEL)).to_have_count(0)


def test_a_click_outside_keeps_the_page_open(canvas):
    open_settings(canvas, "[data-chrome]")
    canvas.locator(NAME).first.fill("Halfway through this")
    canvas.click("[data-viewport]", position={"x": 20, "y": 400})
    expect(canvas.locator(NAME).first).to_have_value("Halfway through this")


def test_returns_focus_to_the_cog_that_opened_it(app):
    open_settings(app)
    app.keyboard.press("Escape")
    expect(app.locator("[data-empty] [data-settings-open]")).to_be_focused()


def test_the_standing_instructions_still_save_from_here(app):
    open_settings(app)
    app.fill("[data-instructions-input]", "Answer in British English.")
    app.click("[data-settings-save]")
    open_settings(app)
    expect(app.locator("[data-instructions-input]")).to_have_value("Answer in British English.")


def test_saves_the_instructions_and_the_chips_together(app):
    open_settings(app)
    app.fill("[data-instructions-input]", "Be brief.")
    app.locator(NAME).first.fill("Plainly")
    app.click("[data-settings-save]")
    open_settings(app)
    expect(app.locator("[data-instructions-input]")).to_have_value("Be brief.")
    expect(app.locator(NAME).first).to_have_value("Plainly")
