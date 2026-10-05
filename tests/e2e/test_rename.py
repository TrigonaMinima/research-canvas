"""Renaming a canvas from its header, against the real API."""

from __future__ import annotations

import pytest
from playwright.sync_api import expect
from tests.fixtures.rename import FIELD, TITLE, start_rename
from tests.fixtures.viewport import canvas_id_of

from research_canvas.config import BLANK_TITLE_MESSAGE, DISPLAY_NAME, MAX_TITLE_CHARS

from .conftest import canvas_from
from .test_empty_state import DOC, ENTRY, saved_canvas

pytestmark = pytest.mark.e2e

OLD = "A Title"
NEW = "Notes on Residuals"


@pytest.fixture
def titled(app):
    """A canvas whose header title is `A Title`."""
    return canvas_from(app, DOC)


def rename_to(page, text: str) -> None:
    start_rename(page)
    page.fill(FIELD, text)
    page.press(FIELD, "Enter")


def test_clicking_the_title_opens_the_rename_input(titled):
    start_rename(titled)
    expect(titled.locator(FIELD)).to_be_visible()


def test_the_rename_input_holds_the_current_title(titled):
    start_rename(titled)
    expect(titled.locator(FIELD)).to_have_value(OLD)


def test_the_rename_input_is_focused(titled):
    start_rename(titled)
    expect(titled.locator(FIELD)).to_be_focused()


def test_the_title_button_hides_while_the_input_shows(titled):
    start_rename(titled)
    expect(titled.locator(TITLE)).to_be_hidden()


def test_the_rename_input_is_hidden_until_rename_starts(titled):
    # Evaluated on the element itself, so a missing input fails instead of reading as hidden.
    assert titled.locator(FIELD).evaluate("el => el.offsetParent === null")


def test_enter_renames_the_header(titled):
    rename_to(titled, NEW)
    expect(titled.locator(TITLE)).to_have_text(NEW)


def test_enter_closes_the_rename_input(titled):
    rename_to(titled, NEW)
    expect(titled.locator(FIELD)).to_be_hidden()


def test_the_tab_title_follows_a_rename(titled):
    rename_to(titled, NEW)
    expect(titled).to_have_title(f"{NEW} · {DISPLAY_NAME}")


def test_a_rename_leaves_the_url_unchanged(titled):
    before = titled.url
    rename_to(titled, NEW)
    expect(titled.locator(TITLE)).to_have_text(NEW)
    assert titled.url == before


def test_a_rename_leaves_the_canvas_id_unchanged(titled):
    before = canvas_id_of(titled)
    rename_to(titled, NEW)
    expect(titled.locator(TITLE)).to_have_text(NEW)
    assert canvas_id_of(titled) == before


def test_the_new_title_survives_a_reload(titled):
    rename_to(titled, NEW)
    expect(titled.locator(TITLE)).to_have_text(NEW)
    titled.reload()
    titled.wait_for_selector('[data-box="b1"]')
    expect(titled.locator(TITLE)).to_have_text(NEW)


def test_the_canvas_list_shows_the_new_title(app):
    saved_canvas(app)
    app.click(ENTRY)
    app.wait_for_selector('[data-box="b1"]')
    rename_to(app, NEW)
    expect(app.locator(TITLE)).to_have_text(NEW)
    app.click("[data-crumb-home]")
    expect(app.locator("[data-canvas-list] .name")).to_have_text(NEW)


def test_a_rename_with_an_unchanged_title_closes_the_input(titled):
    rename_to(titled, f"  {OLD}  ")
    expect(titled.locator(FIELD)).to_be_hidden()


def test_a_rename_with_an_unchanged_title_sends_no_request(titled):
    sent = []
    titled.on("request", lambda r: sent.append(r.method) if r.method == "PATCH" else None)
    rename_to(titled, OLD)
    expect(titled.locator(FIELD)).to_be_hidden()
    assert sent == []


def test_escape_keeps_the_old_title_in_the_header(titled):
    start_rename(titled)
    titled.fill(FIELD, NEW)
    titled.press(FIELD, "Escape")
    expect(titled.locator(TITLE)).to_have_text(OLD)


def test_escape_closes_the_rename_input(titled):
    start_rename(titled)
    titled.press(FIELD, "Escape")
    expect(titled.locator(FIELD)).to_be_hidden()


def test_blur_keeps_the_old_title_in_the_header(titled):
    start_rename(titled)
    titled.fill(FIELD, NEW)
    titled.locator(FIELD).blur()
    expect(titled.locator(TITLE)).to_have_text(OLD)


def test_blur_closes_the_rename_input(titled):
    start_rename(titled)
    titled.locator(FIELD).blur()
    expect(titled.locator(FIELD)).to_be_hidden()


def test_a_blank_title_shows_the_toast(titled):
    rename_to(titled, "   ")
    expect(titled.locator("[data-toast]")).to_have_text(BLANK_TITLE_MESSAGE)


def test_a_blank_title_keeps_the_rename_input_open(titled):
    rename_to(titled, "   ")
    expect(titled.locator("[data-toast]")).to_have_text(BLANK_TITLE_MESSAGE)
    expect(titled.locator(FIELD)).to_be_visible()


def test_a_blank_title_leaves_the_header_title_alone(titled):
    rename_to(titled, "   ")
    expect(titled.locator("[data-toast]")).to_have_text(BLANK_TITLE_MESSAGE)
    titled.press(FIELD, "Escape")
    expect(titled.locator(TITLE)).to_have_text(OLD)


def test_the_keyboard_alone_renames_a_canvas(titled):
    titled.focus(TITLE)
    titled.keyboard.press("Enter")
    titled.keyboard.press("ControlOrMeta+a")
    titled.keyboard.type(NEW)
    titled.keyboard.press("Enter")
    expect(titled.locator(TITLE)).to_have_text(NEW)


def test_space_on_the_title_button_starts_a_rename(titled):
    titled.focus(TITLE)
    titled.keyboard.press("Space")
    expect(titled.locator(FIELD)).to_be_visible()


def test_the_rename_input_caps_the_title_length(titled):
    start_rename(titled)
    expect(titled.locator(FIELD)).to_have_attribute("maxlength", str(MAX_TITLE_CHARS))
