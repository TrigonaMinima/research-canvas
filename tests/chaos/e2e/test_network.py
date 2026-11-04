"""The browser when the network fails (#56).

Each test breaks one request on its own page with `page.route` or `set_offline`, and
checks the reader is told, keeps what they typed, and is left somewhere they can retry.
The session server is never touched, so nothing here leaks into another test.
"""

from __future__ import annotations

import re
import time

import pytest
from playwright.sync_api import expect

from research_canvas.config import BRIEF_CRASHED_REASON, BRIEF_USAGE_LIMIT_REASON
from research_canvas.storage import INTERRUPTED_REASON
from tests.fixtures.e2e_app import SAMPLE_DOC
from tests.fixtures.editor import CONTENT, SAVE_TOP, edit, open_editor
from tests.fixtures.network import (
    ASK,
    BODY,
    BOX,
    CANVAS,
    CANVAS_LIST,
    CONFIG,
    DETAIL,
    EXPAND,
    INSTRUCTIONS,
    RETRY,
    STREAM,
    TOAST,
    drop,
    fail,
    watch_errors,
)
from tests.fixtures.rename import FIELD, start_rename
from tests.fixtures.selection import QUOTE, ask, highlight

pytestmark = pytest.mark.e2e

QUESTION = "Why does the residual path help?"
EDITED = "# Edited offline\n\nThis text must survive a dead network.\n"


def question_left_open(page) -> str:
    """Ask, and return what the popover still holds once the request has failed."""
    ask(page, "b1", QUOTE, QUESTION)
    expect(page.locator(TOAST)).to_be_visible()
    return page.locator("[data-ask-input]").input_value()


def finished_answer(page, question: str = "What is it? [[fake:ok]]") -> None:
    ask(page, "b1", QUOTE, question)
    page.wait_for_selector('[data-box="b2"][data-status="done"]', timeout=20000)


# --- api.js: a reply that is not JSON ---------------------------------------------


def test_should_name_a_proxy_502_page_by_its_status_text(canvas):
    def proxy_page(route):
        if route.request.method != "PATCH":
            route.fallback()
            return
        route.fulfill(status=502, content_type="text/html", body="<html><h1>502</h1></html>")

    canvas.route(CANVAS, proxy_page)
    start_rename(canvas)
    canvas.fill(FIELD, "A new name")
    canvas.press(FIELD, "Enter")

    expect(canvas.locator(TOAST)).to_have_text("Bad Gateway")


# --- a fetch that never arrives ------------------------------------------------------


def test_should_say_so_when_an_ask_is_dropped(canvas):
    drop(canvas, ASK, "POST")
    ask(canvas, "b1", QUOTE, QUESTION)

    expect(canvas.locator(TOAST)).to_be_visible()


def test_should_keep_the_question_when_an_ask_is_dropped(canvas):
    drop(canvas, ASK, "POST")

    assert question_left_open(canvas) == QUESTION


def test_should_keep_the_edit_open_when_saving_offline(canvas):
    edit(canvas, "b1", EDITED)
    canvas.context.set_offline(True)
    try:
        canvas.click(SAVE_TOP.format(box="b1"))
        expect(canvas.locator(TOAST)).to_be_visible()
        expect(canvas.locator(CONTENT.format(box="b1"))).to_contain_text("survive a dead network")
    finally:
        canvas.context.set_offline(False)


def test_should_save_the_offline_edit_once_back_online(canvas, server):
    edit(canvas, "b1", EDITED)
    canvas.context.set_offline(True)
    canvas.click(SAVE_TOP.format(box="b1"))
    expect(canvas.locator(TOAST)).to_be_visible()
    canvas.context.set_offline(False)

    canvas.click(SAVE_TOP.format(box="b1"))

    expect(canvas.locator('[data-box="b1"] [data-body]')).to_contain_text("survive a dead network")


# --- a stream dropped while the page stays open ---------------------------------------


def test_should_settle_a_dropped_stream_from_the_disk(canvas):
    # The run never reaches the server, so the disk calls it interrupted.
    drop(canvas, STREAM)
    ask(canvas, "b1", QUOTE, QUESTION)

    expect(canvas.locator('[data-box="b2"] [data-reason]')).to_have_text(
        INTERRUPTED_REASON, timeout=10000
    )


def test_should_keep_asking_the_disk_with_a_growing_wait(canvas):
    drop(canvas, STREAM)
    looks: list[float] = []

    def still_running(route):
        # The first two looks are told the run is still going; the third gets the truth.
        if route.request.method != "GET":
            route.fallback()
            return
        looks.append(time.monotonic())
        if len(looks) > 2:
            route.fallback()
            return
        view = route.fetch().json()
        for box in view["boxes"]:
            if box["id"] == "b2":
                box["status"] = "running"
        route.fulfill(json=view)

    canvas.route(CANVAS, still_running)
    ask(canvas, "b1", QUOTE, QUESTION)
    expect(canvas.locator('[data-box="b2"]')).to_have_attribute(
        "data-status", "interrupted", timeout=15000
    )

    first, second = looks[1] - looks[0], looks[2] - looks[1]
    assert second > first * 1.5, f"waits of {first:.2f}s then {second:.2f}s did not back off"


def test_should_keep_asking_the_disk_when_one_look_fails(canvas):
    drop(canvas, STREAM)
    fail(canvas, CANVAS, "GET", times=1)
    ask(canvas, "b1", QUOTE, QUESTION)

    expect(canvas.locator('[data-box="b2"]')).to_have_attribute(
        "data-status", "interrupted", timeout=15000
    )


# --- a 5xx on save, ask and patch --------------------------------------------------------


def test_should_say_so_when_a_save_fails(canvas):
    fail(canvas, BODY, "PUT")
    edit(canvas, "b1", EDITED)
    canvas.click(SAVE_TOP.format(box="b1"))

    expect(canvas.locator(TOAST)).to_have_text(DETAIL)


def test_should_keep_the_edit_when_a_save_fails(canvas):
    fail(canvas, BODY, "PUT")
    edit(canvas, "b1", EDITED)
    canvas.click(SAVE_TOP.format(box="b1"))
    expect(canvas.locator(TOAST)).to_be_visible()

    expect(canvas.locator(CONTENT.format(box="b1"))).to_contain_text("survive a dead network")


def test_should_say_so_when_an_ask_fails(canvas):
    fail(canvas, ASK, "POST")
    ask(canvas, "b1", QUOTE, QUESTION)

    expect(canvas.locator(TOAST)).to_have_text(DETAIL)


def test_should_keep_the_question_when_an_ask_fails(canvas):
    fail(canvas, ASK, "POST")

    assert question_left_open(canvas) == QUESTION


def test_should_send_the_kept_question_once_the_server_is_back(canvas):
    fail(canvas, ASK, "POST", times=1)
    question_left_open(canvas)

    canvas.click("[data-ask-send]")

    expect(canvas.locator('[data-box="b2"] [data-question]')).to_contain_text(QUESTION)


def test_should_say_so_when_a_rename_fails(canvas):
    fail(canvas, CANVAS, "PATCH")
    start_rename(canvas)
    canvas.fill(FIELD, "A new name")
    canvas.press(FIELD, "Enter")

    expect(canvas.locator(TOAST)).to_have_text(DETAIL)


def test_should_keep_the_typed_title_when_a_rename_fails(canvas):
    fail(canvas, CANVAS, "PATCH")
    start_rename(canvas)
    canvas.fill(FIELD, "A new name")
    canvas.press(FIELD, "Enter")
    expect(canvas.locator(TOAST)).to_be_visible()

    expect(canvas.locator(FIELD)).to_have_value("A new name")


# --- the research brief failing --------------------------------------------------------


def draft_brief(page, topic: str) -> None:
    page.click('[data-tab="research"]')
    page.fill("[data-topic]", topic)
    page.click("[data-research-draft]")


def test_should_name_a_brief_that_finished_with_a_failure(app):
    draft_brief(app, "python releases [[fake:usage_limit]]")

    expect(app.locator("[data-research-note]")).to_have_text(
        BRIEF_USAGE_LIMIT_REASON, timeout=20000
    )


def test_should_name_a_brief_whose_stream_broke(app):
    drop(app, EXPAND)
    draft_brief(app, "python releases")

    expect(app.locator("[data-research-note]")).to_have_text(BRIEF_CRASHED_REASON)


def test_should_let_the_brief_be_drafted_again_after_its_stream_broke(app):
    drop(app, EXPAND)
    draft_brief(app, "python releases")
    expect(app.locator("[data-research-note]")).to_have_text(BRIEF_CRASHED_REASON)

    expect(app.locator("[data-research-draft]")).to_be_enabled()


# --- booting with part of the server missing --------------------------------------------


def test_should_not_leave_a_blank_page_when_the_config_fails(page, server, fresh_home):
    fail(page, CONFIG, "GET")
    page.goto(server + "/")

    expect(page.locator("[data-boot-failed]")).to_be_visible()


def test_should_not_leave_a_blank_page_when_the_config_is_dropped(page, server, fresh_home):
    drop(page, CONFIG)
    page.goto(server + "/")

    expect(page.locator("[data-boot-failed]")).to_be_visible()


def test_should_say_so_when_the_canvas_list_fails(page, server, fresh_home):
    fail(page, CANVAS_LIST, "GET")
    page.goto(server + "/")

    expect(page.locator(TOAST)).to_have_text(DETAIL)


def test_should_not_throw_when_the_canvas_list_fails(page, server, fresh_home):
    problems = watch_errors(page)
    fail(page, CANVAS_LIST, "GET")
    page.goto(server + "/")
    expect(page.locator(TOAST)).to_be_visible()

    assert not problems, f"the page threw: {problems}"


def test_should_still_offer_an_import_when_the_canvas_list_fails(page, server, fresh_home):
    fail(page, CANVAS_LIST, "GET")
    page.goto(server + "/")

    expect(page.locator("[data-paste]")).to_be_visible()


def test_should_fall_through_to_the_list_for_a_canvas_that_is_gone(page, server, fresh_home):
    # The empty state is in the markup from the start, so only a filled list proves the boot.
    page.request.post(server + "/api/canvases", data={"markdown": SAMPLE_DOC, "webSearch": True})
    page.goto(server + "/?c=deleted-long-ago")

    expect(page.locator("[data-canvas-list] li")).to_have_count(1)


def test_should_drop_the_gone_canvas_from_the_address(page, server, fresh_home):
    page.goto(server + "/?c=deleted-long-ago")

    expect(page).not_to_have_url(re.compile(r"c="))


# --- the toasts no spec reached ----------------------------------------------------------


def test_should_say_so_when_settings_fail_to_load(canvas):
    fail(canvas, INSTRUCTIONS, "GET")
    canvas.locator("[data-settings-open]:visible").first.click()

    expect(canvas.locator(TOAST)).to_have_text(DETAIL)


def test_should_open_no_settings_page_when_they_fail_to_load(canvas):
    fail(canvas, INSTRUCTIONS, "GET")
    canvas.locator("[data-settings-open]:visible").first.click()
    expect(canvas.locator(TOAST)).to_be_visible()

    expect(canvas.locator("[data-settings]")).to_have_count(0)


def test_should_put_the_web_switch_back_when_it_fails_to_save(canvas):
    before = canvas.get_attribute("[data-canvas-web]", "aria-pressed")
    fail(canvas, CANVAS, "PATCH")
    canvas.click("[data-canvas-web]")
    expect(canvas.locator(TOAST)).to_have_text(DETAIL)

    expect(canvas.locator("[data-canvas-web]")).to_have_attribute("aria-pressed", before)


def test_should_say_so_when_a_delete_fails(canvas):
    finished_answer(canvas)
    fail(canvas, BOX, "DELETE")
    canvas.click('[data-box="b2"] [data-delete]')

    expect(canvas.locator(TOAST)).to_have_text(DETAIL)


def test_should_keep_the_box_when_a_delete_fails(canvas):
    finished_answer(canvas)
    fail(canvas, BOX, "DELETE")
    canvas.click('[data-box="b2"] [data-delete]')
    expect(canvas.locator(TOAST)).to_be_visible()

    expect(canvas.locator('[data-box="b2"]')).to_be_visible()


def test_should_say_so_when_a_retry_fails(canvas):
    ask(canvas, "b1", QUOTE, "Explain this [[fake:error]]")
    expect(canvas.locator('[data-box="b2"]')).to_have_attribute(
        "data-status", "failed", timeout=20000
    )
    fail(canvas, RETRY, "POST")
    canvas.click('[data-box="b2"] [data-retry]')

    expect(canvas.locator(TOAST)).to_have_text(DETAIL)


def test_should_keep_a_failed_box_failed_when_its_retry_fails(canvas):
    ask(canvas, "b1", QUOTE, "Explain this [[fake:error]]")
    expect(canvas.locator('[data-box="b2"]')).to_have_attribute(
        "data-status", "failed", timeout=20000
    )
    fail(canvas, RETRY, "POST")
    canvas.click('[data-box="b2"] [data-retry]')
    expect(canvas.locator(TOAST)).to_be_visible()

    expect(canvas.locator('[data-box="b2"]')).to_have_attribute("data-status", "failed")


def test_should_say_so_when_the_editor_source_fails_to_load(canvas):
    fail(canvas, BODY, "GET")
    canvas.click('[data-box="b1"] [data-edit]')

    expect(canvas.locator(TOAST)).to_have_text(DETAIL)


def test_should_open_no_editor_when_its_source_fails_to_load(canvas):
    fail(canvas, BODY, "GET")
    canvas.click('[data-box="b1"] [data-edit]')
    expect(canvas.locator(TOAST)).to_be_visible()

    expect(canvas.locator(CONTENT.format(box="b1"))).to_have_count(0)


def test_should_open_the_editor_once_the_source_loads_again(canvas):
    fail(canvas, BODY, "GET", times=1)
    canvas.click('[data-box="b1"] [data-edit]')
    expect(canvas.locator(TOAST)).to_be_visible()

    open_editor(canvas, "b1")

    expect(canvas.locator(CONTENT.format(box="b1"))).to_be_visible()


def test_should_keep_the_highlight_usable_after_a_failed_ask(canvas):
    # The passage is still there to ask about once the reader closes the kept question.
    fail(canvas, ASK, "POST", times=1)
    question_left_open(canvas)
    canvas.click("[data-ask-cancel]")

    highlight(canvas, "b1", QUOTE)

    expect(canvas.locator("[data-ask]")).to_be_visible()
