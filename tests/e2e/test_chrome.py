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


def test_both_fold_buttons_sit_with_the_other_view_controls(canvas):
    expect(canvas.locator(".tools [data-fold-all]")).to_have_text("Collapse all")
    expect(canvas.locator(".tools [data-unfold-all]")).to_have_text("Expand all")


def test_the_view_controls_keep_their_width_when_the_bar_is_tight(canvas):
    """The bar is one flex row with no wrap, so a narrow window has to squeeze something.
    The title ellipsises; the controls hold their size. A clipped button still clicks, so
    only a measurement catches a squeezed label."""
    measure = """() => ({
      tools: Math.round(document.querySelector('.tools').getBoundingClientRect().width),
      clipped: [...document.querySelectorAll('.tools button')]
        .filter((b) => b.scrollWidth > b.clientWidth + 1
                    || b.scrollHeight > b.clientHeight + 1)
        .map((b) => b.textContent.trim() || b.getAttribute('aria-label')),
    })"""
    canvas.evaluate(
        "() => { document.querySelector('[data-title]').textContent = "
        "'A Canvas With A Very Long Title Indeed '.repeat(3); }"
    )
    roomy = canvas.evaluate(measure)

    canvas.set_viewport_size({"width": 1100, "height": 900})
    tight = canvas.evaluate(measure)

    assert tight["clipped"] == []
    assert tight["tools"] == roomy["tools"], "the view controls gave up width to the title"
