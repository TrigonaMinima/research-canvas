"""The first screen: what you see before a canvas exists."""

from __future__ import annotations

import pytest
from playwright.sync_api import expect
from tests.fixtures.editor import SAVE_BUTTON, edit

from research_canvas.config import DISPLAY_NAME
from research_canvas.storage import REFUSED_MESSAGE

from .conftest import canvas_from

pytestmark = pytest.mark.e2e

SHORT_PASTE = "Too short."
DOC = "# A Title\n\n" + ("A sentence about residual connections in transformers. " * 4)
OTHER_DOC = "# Another Title\n\n" + ("A sentence about attention heads in transformers. " * 4)

ENTRY = "[data-canvas-list] a"


def saved_canvas(page, markdown: str = DOC) -> str:
    """Import a document, come back to the list, and answer with the canvas id.

    The id is read off the URL the app wrote when it opened the canvas, so the tests
    below never check a link against a value taken from that same link.
    """
    canvas_from(page, markdown)
    canvas_id = page.url.split("?c=")[-1]
    page.click("[data-crumb-home]")
    page.wait_for_selector(ENTRY)
    return canvas_id


def test_shows_the_skill_display_name(app):
    expect(app.locator("[data-empty] .eyebrow")).to_have_text(DISPLAY_NAME)


def test_titles_the_document(app):
    expect(app).to_have_title(DISPLAY_NAME)


def test_invites_you_to_start(app):
    expect(app.locator("[data-empty] h1")).to_have_text("Start a canvas")


def test_paste_tab_is_selected_first(app):
    expect(app.locator('[data-tab="paste"]')).to_have_attribute("aria-selected", "true")
    expect(app.locator('[data-tab="research"]')).to_have_attribute("aria-selected", "false")
    expect(app.locator("[data-paste]")).to_be_visible()


def test_research_tab_shows_a_disabled_start_button(app):
    app.click('[data-tab="research"]')
    expect(app.locator('[data-tab="research"]')).to_have_attribute("aria-selected", "true")
    expect(app.locator("[data-research-start]")).to_be_disabled()


def test_research_start_explains_why_it_is_off(app):
    app.click('[data-tab="research"]')
    app.click("[data-research-note]")
    expect(app.locator("[data-toast]")).to_have_text(
        "Research runs are P1 — not in the v1 skeleton"
    )


def test_refuses_a_paste_that_is_too_short(app):
    app.fill("[data-paste]", SHORT_PASTE)
    app.click("[data-create]")
    expect(app.locator("[data-note]")).to_have_text(REFUSED_MESSAGE)
    expect(app.locator("[data-empty]")).to_be_visible()


def test_creates_a_canvas_from_a_real_paste(app):
    app.fill("[data-paste]", DOC)
    app.click("[data-create]")
    expect(app.locator("[data-empty]")).to_be_hidden()
    expect(app.locator('[data-box="b1"]')).to_be_visible()
    expect(app.locator("[data-toast]")).to_have_text(
        "Canvas created — highlight any passage to ask"
    )


def test_uses_the_first_heading_as_the_title(app):
    app.fill("[data-paste]", DOC)
    app.click("[data-create]")
    expect(app.locator("[data-title]")).to_have_text("A Title")


def test_lists_a_saved_canvas_so_research_can_resume(app, server):
    app.fill("[data-paste]", DOC)
    app.click("[data-create]")
    app.wait_for_selector('[data-box="b1"]')
    app.goto(server + "/")
    expect(app.locator("[data-canvas-list] li")).to_have_count(1)
    app.click(ENTRY)
    expect(app.locator('[data-box="b1"]')).to_be_visible()
    # A plain click is still the app's to handle: no second tab, no reload.
    assert len(app.context.pages) == 1


def test_a_saved_canvas_is_a_link_to_itself(app):
    canvas_id = saved_canvas(app)
    expect(app.locator(ENTRY).first).to_have_attribute("href", f"?c={canvas_id}")


def test_a_modifier_click_opens_the_canvas_in_a_new_tab(app):
    saved_canvas(app)
    with app.context.expect_page() as opened:
        app.click(ENTRY, modifiers=["ControlOrMeta"])
    tab = opened.value
    tab.wait_for_selector('[data-box="b1"]')
    # The tab you clicked from never moved.
    expect(app.locator("[data-empty]")).to_be_visible()
    tab.close()


def test_a_middle_click_leaves_the_current_tab_where_it_is(app):
    saved_canvas(app)
    app.click(ENTRY, button="middle")
    expect(app.locator("[data-empty]")).to_be_visible()


def test_the_tab_is_named_after_the_canvas(app):
    saved_canvas(app)
    app.click(ENTRY)
    app.wait_for_selector('[data-box="b1"]')
    expect(app).to_have_title(f"A Title · {DISPLAY_NAME}")
    app.click("[data-crumb-home]")
    expect(app).to_have_title(DISPLAY_NAME)


def test_two_canvases_can_be_edited_at_once(app, server):
    """The point of the feature: two canvases open at once, neither one clobbered."""
    first = saved_canvas(app)
    second = saved_canvas(app, OTHER_DOC)

    second_tab = app.context.new_page()
    second_tab.goto(f"{server}/?c={second}")
    second_tab.wait_for_selector('[data-box="b1"]')
    app.goto(f"{server}/?c={first}")
    app.wait_for_selector('[data-box="b1"]')

    edits = ((app, "# Edited first"), (second_tab, "# Edited second"))
    for tab, line in edits:
        edit(tab, "b1", line)
        tab.click(SAVE_BUTTON.format(box="b1"))
        expect(tab.locator('[data-box="b1"] [data-body]')).to_contain_text(line[2:])

    # Neither tab wrote over the other: each canvas kept its own edit on disk.
    for tab, line in edits:
        tab.reload()
        tab.wait_for_selector('[data-box="b1"]')
        expect(tab.locator('[data-box="b1"] [data-body]')).to_contain_text(line[2:])
    second_tab.close()
