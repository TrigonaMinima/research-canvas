"""The web search switch in the UI: the start screen, the bar, and the ask popover."""

from __future__ import annotations

import pytest
from playwright.sync_api import expect
from tests.e2e.conftest import SAMPLE_DOC
from tests.fixtures.selection import QUOTE, highlight, send_question
from tests.fixtures.viewport import canvas_id_of

pytestmark = pytest.mark.e2e

START = "button.webtoggle[data-start-web]"
CHROME = "header.chrome button.webtoggle[data-canvas-web]"
ASK = "button.webtoggle[data-ask-web]"


def _view(page, server: str) -> dict:
    return page.request.get(f"{server}/api/canvases/{canvas_id_of(page)}").json()


def _box(page, server: str, box_id: str) -> dict:
    return next(b for b in _view(page, server)["boxes"] if b["id"] == box_id)


def _create_with_start_toggle_off(app):
    app.click(START)
    app.fill("[data-paste]", SAMPLE_DOC)
    app.click("[data-create]")
    app.wait_for_selector('[data-box="b1"]')
    return app


def _open_popover(page) -> None:
    highlight(page, "b1", QUOTE)
    page.wait_for_selector("[data-ask]")


# --- the start screen ----------------------------------------------------------


def test_the_start_screen_has_one_web_search_toggle(app):
    expect(app.locator(START)).to_have_count(1)


def test_the_start_toggle_is_visible_under_the_paste_tab(app):
    expect(app.locator(START)).to_be_visible()


def test_the_start_toggle_is_visible_under_the_research_tab(app):
    app.click('[data-tab="research"]')
    expect(app.locator(START)).to_be_visible()


def test_the_start_toggle_is_on_by_default(app):
    expect(app.locator(START)).to_have_attribute("aria-pressed", "true")


def test_clicking_the_start_toggle_turns_it_off(app):
    app.click(START)
    expect(app.locator(START)).to_have_attribute("aria-pressed", "false")


def test_the_start_toggle_keeps_its_state_when_the_tab_changes(app):
    app.click(START)
    app.click('[data-tab="research"]')
    expect(app.locator(START)).to_have_attribute("aria-pressed", "false")


def test_the_start_toggle_keeps_its_state_when_the_reader_comes_back_to_the_paste_tab(app):
    app.click('[data-tab="research"]')
    app.click(START)
    app.click('[data-tab="paste"]')
    expect(app.locator(START)).to_have_attribute("aria-pressed", "false")


def test_a_canvas_created_with_the_start_toggle_on_has_web_search_on(canvas, server):
    assert _view(canvas, server)["webSearch"] is True


def test_a_canvas_created_with_the_start_toggle_off_has_web_search_off(app, server):
    _create_with_start_toggle_off(app)
    assert _view(app, server)["webSearch"] is False


# --- the bar -------------------------------------------------------------------


def test_the_bar_has_a_web_search_toggle(canvas):
    expect(canvas.locator(CHROME)).to_be_visible()


def test_the_bar_toggle_starts_on_for_a_web_search_canvas(canvas):
    expect(canvas.locator(CHROME)).to_have_attribute("aria-pressed", "true")


def test_the_bar_toggle_starts_off_for_a_web_off_canvas(app):
    _create_with_start_toggle_off(app)
    expect(app.locator(CHROME)).to_have_attribute("aria-pressed", "false")


def test_clicking_the_bar_toggle_turns_it_off(canvas):
    canvas.click(CHROME)
    expect(canvas.locator(CHROME)).to_have_attribute("aria-pressed", "false")


def test_clicking_the_bar_toggle_saves_web_search_off_on_the_canvas(canvas, server):
    canvas.click(CHROME)
    canvas.wait_for_function(
        "async (url) => (await (await fetch(url)).json()).webSearch === false",
        arg=f"{server}/api/canvases/{canvas_id_of(canvas)}",
    )
    assert _view(canvas, server)["webSearch"] is False


def test_clicking_the_bar_toggle_twice_turns_web_search_back_on(canvas, server):
    canvas.click(CHROME)
    canvas.click(CHROME)
    expect(canvas.locator(CHROME)).to_have_attribute("aria-pressed", "true")


def test_the_bar_toggle_stays_off_after_a_reload(canvas, server):
    canvas.click(CHROME)
    canvas.wait_for_function(
        "async (url) => (await (await fetch(url)).json()).webSearch === false",
        arg=f"{server}/api/canvases/{canvas_id_of(canvas)}",
    )
    canvas.reload()
    canvas.wait_for_selector('[data-box="b1"]')
    expect(canvas.locator(CHROME)).to_have_attribute("aria-pressed", "false")


# --- the ask popover -----------------------------------------------------------


def test_the_popover_toggle_starts_on_for_a_web_search_canvas(canvas):
    _open_popover(canvas)
    expect(canvas.locator(ASK)).to_have_attribute("aria-pressed", "true")


def test_the_popover_toggle_is_enabled_on_a_web_search_canvas(canvas):
    _open_popover(canvas)
    expect(canvas.locator(ASK)).to_be_enabled()


def test_clicking_the_popover_toggle_turns_it_off(canvas):
    _open_popover(canvas)
    canvas.click(ASK)
    expect(canvas.locator(ASK)).to_have_attribute("aria-pressed", "false")


def test_a_question_sent_with_the_popover_toggle_off_has_web_search_off(canvas, server):
    _open_popover(canvas)
    canvas.click(ASK)
    send_question(canvas, "Why?")
    canvas.wait_for_selector('[data-box="b2"][data-status="done"]', timeout=20000)
    assert _box(canvas, server, "b2")["webSearch"] is False


def test_a_question_sent_with_the_popover_toggle_untouched_has_web_search_on(canvas, server):
    _open_popover(canvas)
    send_question(canvas, "Why?")
    canvas.wait_for_selector('[data-box="b2"][data-status="done"]', timeout=20000)
    assert _box(canvas, server, "b2")["webSearch"] is True


def test_flipping_the_popover_toggle_leaves_the_canvas_switch_alone(canvas, server):
    _open_popover(canvas)
    canvas.click(ASK)
    send_question(canvas, "Why?")
    canvas.wait_for_selector('[data-box="b2"][data-status="done"]', timeout=20000)
    assert _view(canvas, server)["webSearch"] is True


def test_the_popover_toggle_is_off_and_disabled_on_a_web_off_canvas(app):
    _create_with_start_toggle_off(app)
    _open_popover(app)
    expect(app.locator(ASK)).to_be_disabled()


def test_the_popover_toggle_reads_not_pressed_on_a_web_off_canvas(app):
    _create_with_start_toggle_off(app)
    _open_popover(app)
    expect(app.locator(ASK)).to_have_attribute("aria-pressed", "false")


def test_the_popover_toggle_says_why_it_is_off_on_a_web_off_canvas(app):
    _create_with_start_toggle_off(app)
    _open_popover(app)
    expect(app.locator(ASK)).to_contain_text("off for this canvas")


def test_a_question_asked_on_a_web_off_canvas_has_web_search_off(app, server):
    _create_with_start_toggle_off(app)
    _open_popover(app)
    send_question(app, "Why?")
    app.wait_for_selector('[data-box="b2"][data-status="done"]', timeout=20000)
    assert _box(app, server, "b2")["webSearch"] is False


def test_the_chrome_switch_turns_the_open_popover_toggle_off(canvas):
    _open_popover(canvas)
    canvas.click(CHROME)
    expect(canvas.locator(ASK)).to_have_attribute("aria-pressed", "false")


def test_the_chrome_switch_disables_the_open_popover_toggle(canvas):
    _open_popover(canvas)
    canvas.click(CHROME)
    expect(canvas.locator(ASK)).to_be_disabled()


def test_the_chrome_switch_turned_back_on_enables_the_open_popover_toggle(app):
    _create_with_start_toggle_off(app)
    _open_popover(app)
    app.click(CHROME)
    expect(app.locator(ASK)).to_be_enabled()
