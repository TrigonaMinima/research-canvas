"""The server killed in the middle of a merge or a research run (#64).

The force-quit release test covers answers. These run their own server, kill it hard
while a slow run is in flight, start it again on the same canvas root, and read what the
reader finds. A restart picks a new port, so the page goes to the new address.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import expect

from research_canvas.storage import INTERRUPTED_MERGE_REASON
from tests.fixtures.e2e_app import SAMPLE_DOC, start_server, stop_server
from tests.fixtures.merging import PANE
from tests.fixtures.selection import QUOTE, ask
from tests.fixtures.viewport import canvas_id_of

pytestmark = pytest.mark.e2e

KILL_ID = "e2e-chaos-kill"
SLOW = "[[fake:slow]]"
BRIEF = f"Survey the Python release history. {SLOW}"


class Killable:
    """One server of our own, killed and started again on the same canvas root."""

    def __init__(self, home):
        self.home = home
        self.proc, self.url = start_server(home, KILL_ID)

    def kill_and_restart(self) -> None:
        self.proc.kill()  # a force-quit: no chance to save anything on the way out
        self.proc.wait(timeout=10)
        self.proc, self.url = start_server(self.home, KILL_ID)

    def stop(self) -> None:
        stop_server(self.proc, KILL_ID)


@pytest.fixture
def killable(tmp_path_factory):
    server = Killable(tmp_path_factory.mktemp("kill"))
    yield server
    server.stop()


def reopen(page, killable: Killable, canvas_id: str) -> None:
    page.goto("about:blank")
    killable.kill_and_restart()
    page.goto(f"{killable.url}/?c={canvas_id}")
    page.wait_for_selector('[data-box="b1"]')


# --- research ----------------------------------------------------------------------


def research_running(page, killable: Killable) -> str:
    # Through the page, not the API: a run starts only when the page that made it listens.
    page.goto(killable.url + "/")
    page.click('[data-tab="research"]')
    page.fill("[data-topic]", "python releases")
    page.click("[data-research-draft]")
    expect(page.locator("[data-research-start]")).to_be_enabled(timeout=20000)
    page.fill("[data-research-prompt]", BRIEF)
    page.click("[data-research-start]")
    expect(page.locator('[data-box="b1"]')).to_have_attribute("data-status", "running")
    return canvas_id_of(page)


def test_should_call_a_killed_research_run_interrupted(page, killable):
    canvas_id = research_running(page, killable)

    reopen(page, killable, canvas_id)

    expect(page.locator('[data-box="b1"] [data-status-label]')).to_have_text("Interrupted")


def test_should_keep_the_brief_of_a_killed_research_run(page, killable):
    canvas_id = research_running(page, killable)

    reopen(page, killable, canvas_id)

    view = page.request.get(f"{killable.url}/api/canvases/{canvas_id}").json()
    assert view["research"]["prompt"] == BRIEF


def test_should_offer_to_retry_a_killed_research_run(page, killable):
    canvas_id = research_running(page, killable)

    reopen(page, killable, canvas_id)

    expect(page.locator('[data-box="b1"] [data-retry]')).to_be_visible()


def test_should_run_a_killed_research_run_again_on_retry(page, killable):
    canvas_id = research_running(page, killable)
    reopen(page, killable, canvas_id)

    page.click('[data-box="b1"] [data-retry]')

    expect(page.locator('[data-box="b1"]')).to_have_attribute("data-status", "done", timeout=30000)


# --- merge -------------------------------------------------------------------------


def merge_running(page, killable: Killable) -> tuple[str, str]:
    """A slow merge in flight. Returns the canvas id and the document before it."""
    page.goto(killable.url + "/")
    page.fill("[data-paste]", SAMPLE_DOC)
    page.click("[data-create]")
    page.wait_for_selector('[data-box="b1"]')
    canvas_id = canvas_id_of(page)
    before = body_of(page, killable, canvas_id)

    ask(page, "b1", QUOTE, "What is a residual connection?")
    page.wait_for_selector('[data-box="b2"][data-status="done"]', timeout=20000)
    page.click('[data-box="b2"] [data-merge]')
    page.fill("[data-merge-input]", f"Fold it in. {SLOW}")
    page.click("[data-merge-send]")
    page.wait_for_selector(PANE.format(box="b1"))
    # One change in, two still to come: the run is mid-way when the server dies.
    page.wait_for_selector('[data-box="b1"] [data-change]', timeout=10000)
    return canvas_id, before


def body_of(page, killable: Killable, canvas_id: str, box: str = "b1") -> str:
    url = f"{killable.url}/api/canvases/{canvas_id}/boxes/{box}/body"
    return page.request.get(url).json()["markdown"]


def test_should_say_a_killed_merge_was_interrupted(page, killable):
    canvas_id, _ = merge_running(page, killable)

    reopen(page, killable, canvas_id)

    expect(page.locator('[data-box="b1"] .merge__state')).to_have_text(INTERRUPTED_MERGE_REASON)


def test_should_leave_the_document_alone_when_a_merge_is_killed(page, killable):
    canvas_id, before = merge_running(page, killable)

    reopen(page, killable, canvas_id)

    assert body_of(page, killable, canvas_id) == before


def test_should_keep_the_answer_when_its_merge_is_killed(page, killable):
    canvas_id, _ = merge_running(page, killable)

    reopen(page, killable, canvas_id)

    expect(page.locator('[data-box="b2"]')).to_have_attribute("data-status", "done")


def test_should_let_a_killed_merge_be_rejected(page, killable):
    canvas_id, _ = merge_running(page, killable)
    reopen(page, killable, canvas_id)

    page.click('[data-box="b1"] .merge__bar--head [data-merge-reject]')

    expect(page.locator(PANE.format(box="b1"))).to_have_count(0)
