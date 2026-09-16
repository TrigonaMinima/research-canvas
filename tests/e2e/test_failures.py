"""What the canvas shows when a run does not finish. Nothing is ever lost."""

from __future__ import annotations

import pytest
from playwright.sync_api import expect
from tests.fixtures.selection import QUOTE, ask

from research_canvas.runner import CRASHED_REASON as CRASHED
from research_canvas.runner import USAGE_LIMIT_REASON as USAGE_LIMIT

pytestmark = pytest.mark.e2e


def test_a_usage_limit_is_named_plainly(canvas):
    ask(canvas, "b1", QUOTE, "Explain this [[fake:usage_limit]]")
    box = canvas.locator('[data-box="b2"]')
    expect(box).to_have_attribute("data-status", "failed", timeout=20000)
    expect(box.locator("[data-reason]")).to_have_text(USAGE_LIMIT)


def test_a_dead_run_is_named_plainly(canvas):
    ask(canvas, "b1", QUOTE, "Explain this [[fake:crash]]")
    box = canvas.locator('[data-box="b2"]')
    expect(box).to_have_attribute("data-status", "failed", timeout=20000)
    expect(box.locator("[data-reason]")).to_have_text(CRASHED)


def test_a_failed_box_keeps_its_question_and_anchor(canvas):
    ask(canvas, "b1", QUOTE, "Explain this [[fake:error]]")
    expect(canvas.locator('[data-box="b2"]')).to_have_attribute(
        "data-status", "failed", timeout=20000
    )
    expect(canvas.locator('[data-box="b2"] [data-question]')).to_contain_text("Explain this")
    expect(canvas.locator('[data-box="b1"] mark[data-anchor]').first).to_contain_text(QUOTE)


def test_a_failed_box_offers_to_retry(canvas):
    ask(canvas, "b1", QUOTE, "Explain this [[fake:slowerror]]")
    expect(canvas.locator('[data-box="b2"]')).to_have_attribute(
        "data-status", "failed", timeout=20000
    )
    canvas.click('[data-box="b2"] [data-retry]')
    expect(canvas.locator('[data-box="b2"]')).to_have_attribute(
        "data-status", "running", timeout=5000
    )


def test_a_failure_survives_a_reload(canvas):
    ask(canvas, "b1", QUOTE, "Explain this [[fake:error]]")
    expect(canvas.locator('[data-box="b2"]')).to_have_attribute(
        "data-status", "failed", timeout=20000
    )
    canvas.reload()
    canvas.wait_for_selector('[data-box="b2"]')
    expect(canvas.locator('[data-box="b2"]')).to_have_attribute("data-status", "failed")


def test_a_running_box_shows_what_it_is_doing(canvas):
    ask(canvas, "b1", QUOTE, "Explain this [[fake:slow]]")
    expect(canvas.locator('[data-box="b2"] [data-wait]')).to_be_visible()
    expect(canvas.locator('[data-box="b2"] [data-wait]')).to_contain_text("…")
