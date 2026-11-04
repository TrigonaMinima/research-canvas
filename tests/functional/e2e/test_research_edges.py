"""The research panel's less travelled paths: leaving mid-run, a refused start, the
topic cap, and a redraft over an edited brief (#62)."""

from __future__ import annotations

import json
import re

import pytest
from playwright.sync_api import expect

from research_canvas.config import MAX_TOPIC_CHARS
from tests.functional.e2e.test_research_topic import ROOT, TOPIC, draft, research

pytestmark = pytest.mark.e2e

EMPTY = "[data-empty]"
NEW = "[data-new]"
START = "[data-research-start]"
NOTE = "[data-research-note]"
PROMPT = "[data-research-prompt]"
LEAVE = "The research run stops if you leave. Leave anyway?"
REFUSED = "Too many runs at once. Try again in a minute."
LINGER = "[[fake:linger]]"  # holds the run open, so it is still running when we leave


def running_research(page):
    research(page, brief=f"## Goal\n\nKeep going. {LINGER}")
    expect(page.locator(ROOT)).to_have_attribute("data-status", re.compile("queued|running"))
    return page


def answer_dialog(page, accept: bool) -> list[str]:
    """Answer the next dialog one way, and note what it asked."""
    asked: list[str] = []

    def on_dialog(dialog):
        asked.append(dialog.message)
        if accept:
            dialog.accept()
        else:
            dialog.dismiss()

    page.once("dialog", on_dialog)
    return asked


# --- leaving a canvas mid-run ------------------------------------------------------


def test_should_ask_before_leaving_a_running_research_canvas(app):
    running_research(app)
    asked = answer_dialog(app, accept=False)
    app.click(NEW)
    assert asked == [LEAVE]


def test_should_stay_on_the_canvas_when_the_leave_is_cancelled(app):
    running_research(app)
    answer_dialog(app, accept=False)
    app.click(NEW)
    expect(app.locator(ROOT)).to_be_visible()


def test_should_leave_when_the_leave_is_confirmed(app):
    running_research(app)
    answer_dialog(app, accept=True)
    app.click(NEW)
    expect(app.locator(EMPTY)).to_be_visible()


def test_should_not_ask_before_leaving_a_plain_canvas(canvas):
    asked = answer_dialog(canvas, accept=False)
    canvas.click(NEW)
    expect(canvas.locator(EMPTY)).to_be_visible()
    assert asked == []


# --- a refused start ------------------------------------------------------------------


def refuse_start(page) -> None:
    page.route(
        "**/api/research",
        lambda route: route.fulfill(
            status=429, content_type="application/json", body=json.dumps({"detail": REFUSED})
        ),
    )
    draft(page)
    page.click(START)


def test_should_say_why_a_research_start_was_refused(app):
    refuse_start(app)
    expect(app.locator(NOTE)).to_have_text(REFUSED)


def test_should_mark_the_note_as_a_refusal(app):
    refuse_start(app)
    expect(app.locator(NOTE)).to_have_attribute("data-refused", "1")


def test_should_enable_start_again_after_a_refusal(app):
    refuse_start(app)
    expect(app.locator(NOTE)).to_have_text(REFUSED)
    expect(app.locator(START)).to_be_enabled()


def test_should_keep_the_brief_after_a_refusal(app):
    refuse_start(app)
    expect(app.locator(NOTE)).to_have_text(REFUSED)
    expect(app.locator(PROMPT)).to_have_value(re.compile(TOPIC))


# --- the topic cap ---------------------------------------------------------------------


def test_should_cap_the_topic_field_at_the_server_limit(app):
    app.click('[data-tab="research"]')
    expect(app.locator("[data-topic]")).to_have_attribute("maxlength", str(MAX_TOPIC_CHARS))


def test_should_stop_typing_at_the_topic_cap(app):
    app.click('[data-tab="research"]')
    app.locator("[data-topic]").focus()
    app.keyboard.insert_text("x" * MAX_TOPIC_CHARS)
    app.keyboard.type("yz")
    assert len(app.locator("[data-topic]").input_value()) == MAX_TOPIC_CHARS


# --- a redraft over an edited brief --------------------------------------------------------


def test_should_replace_an_edited_brief_on_redraft(app):
    draft(app)
    app.fill(PROMPT, "my own words")
    app.click("[data-research-draft]")
    expect(app.locator(START)).to_be_enabled(timeout=20000)
    expect(app.locator(PROMPT)).not_to_have_value(re.compile("my own words"))


def test_should_draft_the_new_topic_on_redraft(app):
    draft(app)
    app.fill(PROMPT, "my own words")
    app.fill("[data-topic]", "rust editions")
    app.click("[data-research-draft]")
    expect(app.locator(PROMPT)).to_have_value(re.compile("rust editions"), timeout=20000)
