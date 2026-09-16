"""The first screen: what you see before a canvas exists."""

from __future__ import annotations

import pytest
from playwright.sync_api import expect

from research_canvas.config import DISPLAY_NAME
from research_canvas.storage import REFUSED_MESSAGE

pytestmark = pytest.mark.e2e

SHORT_PASTE = "Too short."
DOC = "# A Title\n\n" + ("A sentence about residual connections in transformers. " * 4)


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
    app.click("[data-canvas-list] button")
    expect(app.locator('[data-box="b1"]')).to_be_visible()
