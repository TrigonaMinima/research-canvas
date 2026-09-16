"""The bar across the top: breadcrumbs, find, zoom, theme, new canvas."""

from __future__ import annotations

import pytest
from playwright.sync_api import expect
from tests.fixtures.viewport import scale_of

pytestmark = pytest.mark.e2e


def test_breadcrumb_leads_back_to_the_canvas_list(canvas):
    canvas.click("[data-crumb-home]")
    expect(canvas.locator("[data-empty]")).to_be_visible()


def test_new_canvas_returns_to_the_empty_state(canvas):
    canvas.click("[data-new]")
    expect(canvas.locator("[data-empty]")).to_be_visible()
    expect(canvas.locator("[data-paste]")).to_have_value("")


def test_zoom_level_starts_at_one_hundred_percent(canvas):
    expect(canvas.locator("[data-zoom-level]")).to_have_text("100%")


def test_zoom_in_steps_up_by_a_quarter(canvas):
    canvas.click("[data-zoom-in]")
    expect(canvas.locator("[data-zoom-level]")).to_have_text("125%")
    assert scale_of(canvas) == pytest.approx(1.25, abs=0.01)


def test_zoom_out_steps_down(canvas):
    canvas.click("[data-zoom-out]")
    expect(canvas.locator("[data-zoom-level]")).to_have_text("80%")


def test_zoom_stops_at_two_hundred_percent(canvas):
    for _ in range(8):
        canvas.click("[data-zoom-in]")
    expect(canvas.locator("[data-zoom-level]")).to_have_text("200%")


def test_zoom_stops_at_ten_percent(canvas):
    for _ in range(14):
        canvas.click("[data-zoom-out]")
    expect(canvas.locator("[data-zoom-level]")).to_have_text("10%")


def test_fit_brings_the_canvas_back_into_view(canvas):
    canvas.click("[data-zoom-in]")
    canvas.click("[data-zoom-in]")
    canvas.click("[data-zoom-fit]")
    canvas.wait_for_timeout(600)
    assert scale_of(canvas) <= 1.0


def test_find_counts_the_matches(canvas):
    canvas.fill("[data-find]", "attention")
    expect(canvas.locator("[data-find-count]")).to_have_text("1/4")


def test_find_steps_through_the_matches(canvas):
    canvas.fill("[data-find]", "the")
    expect(canvas.locator("[data-find-count]")).to_contain_text("1/")
    canvas.click("[data-find-next]")
    expect(canvas.locator("[data-find-count]")).to_contain_text("2/")
    canvas.click("[data-find-prev]")
    expect(canvas.locator("[data-find-count]")).to_contain_text("1/")


def test_find_wraps_backwards_from_the_first_match(canvas):
    canvas.fill("[data-find]", "attention")
    canvas.click("[data-find-prev]")
    expect(canvas.locator("[data-find-count]")).to_have_text("4/4")


def test_find_reports_nothing_found(canvas):
    canvas.fill("[data-find]", "zzzznotinhere")
    expect(canvas.locator("[data-find-count]")).to_have_text("0/0")


def test_find_highlights_the_matches(canvas):
    canvas.fill("[data-find]", "attention")
    count = canvas.evaluate("() => { const h = CSS.highlights.get('find'); return h ? h.size : 0 }")
    assert count == 4


def test_theme_toggle_switches_to_dark_and_back(canvas):
    expect(canvas.locator("html")).to_have_attribute("data-theme", "light")
    canvas.click("[data-theme-toggle]")
    expect(canvas.locator("html")).to_have_attribute("data-theme", "dark")
    canvas.click("[data-theme-toggle]")
    expect(canvas.locator("html")).to_have_attribute("data-theme", "light")


def test_theme_survives_a_reload(canvas, server):
    canvas.click("[data-theme-toggle]")
    canvas.reload()
    expect(canvas.locator("html")).to_have_attribute("data-theme", "dark")


def test_run_pill_is_hidden_while_nothing_runs(canvas):
    expect(canvas.locator("[data-runpill]")).to_be_hidden()
