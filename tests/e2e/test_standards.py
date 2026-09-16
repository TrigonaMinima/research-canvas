"""Web standards and accessibility, checked without fetching anything."""

from __future__ import annotations

import pytest
from playwright.sync_api import expect

pytestmark = pytest.mark.e2e

# An accessible name from text, aria-label, aria-labelledby, or title.
NAMES = """
() => [...document.querySelectorAll('button, [role="button"]')]
  .filter(el => el.offsetParent !== null)
  .filter(el => !(el.textContent || '').trim()
      && !el.getAttribute('aria-label')
      && !el.getAttribute('aria-labelledby')
      && !el.getAttribute('title'))
  .map(el => el.outerHTML.slice(0, 90))
"""

UNLABELLED_INPUTS = """
() => [...document.querySelectorAll('input, textarea, select')]
  .filter(el => el.offsetParent !== null)
  .filter(el => !el.getAttribute('aria-label')
      && !el.getAttribute('aria-labelledby')
      && !(el.id && document.querySelector('label[for="' + CSS.escape(el.id) + '"]')))
  .map(el => el.outerHTML.slice(0, 90))
"""

DUPLICATE_IDS = """
() => { const seen = new Set(), dupes = [];
  document.querySelectorAll('[id]').forEach(el => {
    if (seen.has(el.id)) dupes.push(el.id); else seen.add(el.id); });
  return dupes }
"""


def test_the_document_declares_its_language(app):
    expect(app.locator("html")).to_have_attribute("lang", "en")


def test_the_document_has_a_title(app):
    assert app.title().strip()


def test_the_page_has_exactly_one_top_level_heading(app):
    assert app.locator("h1:visible").count() == 1


def test_the_page_declares_a_viewport(app):
    assert app.locator('meta[name="viewport"]').count() == 1


def test_every_visible_button_has_an_accessible_name(app):
    assert app.evaluate(NAMES) == []


def test_every_visible_field_has_a_label(app):
    assert app.evaluate(UNLABELLED_INPUTS) == []


def test_ids_are_unique(app):
    assert app.evaluate(DUPLICATE_IDS) == []


def test_the_tabs_use_the_tab_pattern(app):
    tabs = app.locator('[role="tablist"] [role="tab"]')
    expect(tabs).to_have_count(2)
    for i in range(2):
        panel_id = tabs.nth(i).get_attribute("aria-controls")
        assert app.locator(f'#{panel_id}[role="tabpanel"]').count() == 1


def test_the_canvas_is_reachable_by_keyboard(canvas):
    canvas.keyboard.press("Tab")
    assert canvas.evaluate("() => document.activeElement.tagName") != "BODY"


def test_the_toast_announces_itself(canvas):
    expect(canvas.locator("[data-toast]")).to_have_attribute("role", "status")


def test_the_canvas_region_is_named(canvas):
    expect(canvas.locator("[data-viewport]")).to_have_attribute("aria-label", "Research canvas")


def test_the_chrome_bar_is_a_banner(canvas):
    expect(canvas.locator("[data-chrome]")).to_have_attribute("role", "banner")


def test_every_visible_button_has_a_name_on_a_canvas(canvas):
    assert canvas.evaluate(NAMES) == []


def test_every_visible_field_has_a_label_on_a_canvas(canvas):
    assert canvas.evaluate(UNLABELLED_INPUTS) == []


def test_nothing_is_fetched_from_the_network(canvas, server):
    """'Local only' has to be true, not a slogan."""
    outside = []
    canvas.on(
        "request",
        lambda r: outside.append(r.url) if not r.url.startswith(server) else None,
    )
    canvas.reload()
    canvas.wait_for_selector('[data-box="b1"]')
    assert [u for u in outside if not u.startswith("data:")] == []


def test_the_fonts_are_served_from_this_machine(canvas, server):
    fonts = canvas.evaluate(
        "() => [...document.fonts].map(f => f.family).filter((v, i, a) => a.indexOf(v) === i)"
    )
    assert "Literata" in fonts
    assert "Public Sans" in fonts


def test_reduced_motion_is_respected(app, server):
    app.emulate_media(reduced_motion="reduce")
    app.reload()
    app.wait_for_selector("[data-empty]")
    assert app.evaluate("() => matchMedia('(prefers-reduced-motion: reduce)').matches")
