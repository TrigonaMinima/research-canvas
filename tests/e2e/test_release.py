"""The PRD's release criteria, checked rather than asserted in prose.

- A pending box appears within 300ms of asking.
- A 20,000-word document with 100 answer boxes still pans at 30fps.
- A force-quit with three answers running loses nothing (US-18).
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest
from playwright.sync_api import expect
from tests.fixtures.big_canvas import ANSWERS, seed
from tests.fixtures.selection import ask, highlight
from tests.fixtures.viewport import scale_of

from .conftest import SAMPLE_DOC, start_server, stop_server

pytestmark = pytest.mark.e2e

PENDING_BUDGET_MS = 300
MIN_FPS = 30

# Count frames while the canvas is panned, the way a reader pans it.
MEASURE_PAN = """
async () => {
  const view = document.querySelector('[data-viewport]');
  let frames = 0, running = true;
  const tick = () => { frames++; if (running) requestAnimationFrame(tick); };
  requestAnimationFrame(tick);
  const started = performance.now();
  for (let i = 0; i < 60; i++) {
    view.dispatchEvent(new WheelEvent('wheel',
      {deltaX: 14, deltaY: 9, bubbles: true, cancelable: true}));
    await new Promise((r) => requestAnimationFrame(r));
  }
  const elapsed = performance.now() - started;
  running = false;
  return frames / (elapsed / 1000);
}
"""


# --- responsiveness -------------------------------------------------------


def test_a_pending_box_appears_within_300ms(canvas):
    highlight(canvas, "b1", "residual connection")
    canvas.wait_for_selector("[data-ask]")
    canvas.fill("[data-ask-input]", "Why? [[fake:slow]]")

    started = time.monotonic()
    canvas.click("[data-ask-send]")
    canvas.wait_for_selector('[data-box="b2"]', state="visible")
    elapsed_ms = (time.monotonic() - started) * 1000

    assert elapsed_ms < PENDING_BUDGET_MS, f"the box took {elapsed_ms:.0f}ms to appear"


# --- the large canvas -----------------------------------------------------


@pytest.fixture
def big(page, server: str, fresh_home: Path):
    """A 20,000-word document with 100 finished answers, open on the canvas."""
    canvas_id = seed(fresh_home)
    page.goto(f"{server}/?c={canvas_id}")
    page.wait_for_selector('[data-box="b1"]')
    return page


def test_the_large_canvas_draws_every_box(big):
    expect(big.locator("[data-box]")).to_have_count(ANSWERS + 1)


def test_the_large_canvas_draws_every_edge(big):
    expect(big.locator("[data-edges] [data-edge]")).to_have_count(ANSWERS)


def test_the_large_canvas_pans_at_thirty_frames_a_second(big):
    fps = big.evaluate(MEASURE_PAN)
    assert fps >= MIN_FPS, f"panning ran at {fps:.0f}fps"


def test_the_large_canvas_fits_every_box_into_view(big):
    big.click("[data-zoom-fit]")
    big.wait_for_timeout(600)
    assert 0.1 <= scale_of(big) <= 1.0


# --- US-18: a force-quit loses nothing ------------------------------------

CRASH_ID = "e2e-crash"
QUESTIONS = [
    "Why residual? [[fake:slow]]",
    "Why convolutional? [[fake:slow]]",
    "Why normalisation? [[fake:slow]]",
]
QUOTES = ["residual connection", "convolutional", "normalisation"]


def test_three_running_answers_survive_a_force_quit(page, tmp_path_factory):
    home = tmp_path_factory.mktemp("crash")
    proc, url = start_server(home, CRASH_ID)
    try:
        page.goto(url + "/")
        page.fill("[data-paste]", SAMPLE_DOC)
        page.click("[data-create]")
        page.wait_for_selector('[data-box="b1"]')
        canvas_id = page.evaluate("() => new URLSearchParams(location.search).get('c')")

        for quote, question in zip(QUOTES, QUESTIONS, strict=True):
            ask(page, "b1", quote, question)

        for box in ("b2", "b3", "b4"):
            expect(page.locator(f'[data-box="{box}"]')).to_have_attribute("data-status", "running")

        proc.kill()  # a force-quit, not a shutdown: no chance to tidy up
        proc.wait(timeout=10)
        page.goto("about:blank")

        proc, url = start_server(home, CRASH_ID)
        page.goto(f"{url}/?c={canvas_id}")
        page.wait_for_selector('[data-box="b1"]')

        for box, question in zip(("b2", "b3", "b4"), QUESTIONS, strict=True):
            expect(page.locator(f'[data-box="{box}"] [data-status-label]')).to_have_text(
                "Interrupted"
            )
            expect(page.locator(f'[data-box="{box}"] [data-question]')).to_contain_text(question)
        expect(page.locator('[data-box="b1"] mark[data-anchor]')).to_have_count(3)
        expect(page.locator("[data-edges] [data-edge]")).to_have_count(3)
    finally:
        stop_server(proc, CRASH_ID)
