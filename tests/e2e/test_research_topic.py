"""Research a topic from scratch: draft a brief, approve it, watch the run read the web."""

from __future__ import annotations

import re

import pytest
from playwright.sync_api import expect

# What the stand-in CLI searches for, fetches, and finds without citing.
from tests.fixtures.fake_claude import FETCHED, QUERY, UNCITED

from research_canvas.config import (
    BLANK_TOPIC_MESSAGE,
    MAX_RESEARCH_PROMPT_CHARS,
    RESEARCH_CRASHED_REASON,
    RESEARCH_NO_WEB_REASON,
    RESEARCH_PROMPT_TOO_LONG_MESSAGE,
    SOURCES_HEADING,
    UNVERIFIED_HEADING,
)

pytestmark = pytest.mark.e2e

ROOT = '[data-box="b1"]'
TOPIC = "python releases"


def draft(page, topic: str = TOPIC):
    page.click('[data-tab="research"]')
    page.fill("[data-topic]", topic)
    page.click("[data-research-draft]")
    expect(page.locator("[data-research-start]")).to_be_enabled(timeout=20000)


def research(page, brief: str | None = None):
    draft(page)
    if brief is not None:
        page.fill("[data-research-prompt]", brief)
    page.click("[data-research-start]")
    page.wait_for_selector(ROOT)
    return page.locator(ROOT)


def finished(page, brief: str | None = None):
    root = research(page, brief)
    expect(root).to_have_attribute("data-status", "done", timeout=20000)
    return root


# --- the brief ------------------------------------------------------------------


def test_the_brief_is_hidden_until_one_is_drafted(app):
    app.click('[data-tab="research"]')
    expect(app.locator("[data-research-prompt]")).to_be_hidden()


def test_a_blank_topic_is_refused_with_a_reason(app):
    app.click('[data-tab="research"]')
    app.click("[data-research-draft]")
    expect(app.locator("[data-research-note]")).to_have_text(BLANK_TOPIC_MESSAGE)


def test_the_drafted_brief_is_about_the_topic(app):
    draft(app)
    expect(app.locator("[data-research-prompt]")).to_have_value(re.compile(TOPIC))


def test_the_drafted_brief_can_be_edited(app):
    draft(app)
    expect(app.locator("[data-research-prompt]")).to_be_editable()


def test_enter_in_the_topic_drafts_the_brief(app):
    app.click('[data-tab="research"]')
    app.fill("[data-topic]", TOPIC)
    app.press("[data-topic]", "Enter")
    expect(app.locator("[data-research-start]")).to_be_enabled(timeout=20000)


LONG_TOPIC = "what to wear to a wedding, mine and others, casual and formal, " * 4


def height(page, selector: str) -> float:
    return page.locator(selector).bounding_box()["height"]


def clipped(page, selector: str) -> bool:
    return page.locator(selector).evaluate("el => el.scrollHeight > el.clientHeight")


def test_the_topic_box_grows_with_a_long_topic(app):
    app.click('[data-tab="research"]')
    one_line = height(app, "[data-topic]")
    app.fill("[data-topic]", LONG_TOPIC)
    assert height(app, "[data-topic]") > one_line


def test_a_long_topic_is_shown_whole(app):
    app.click('[data-tab="research"]')
    app.fill("[data-topic]", LONG_TOPIC)
    assert not clipped(app, "[data-topic]")


def test_the_topic_box_shrinks_back_when_the_topic_is_cut(app):
    app.click('[data-tab="research"]')
    one_line = height(app, "[data-topic]")
    app.fill("[data-topic]", LONG_TOPIC)
    app.fill("[data-topic]", "short")
    assert height(app, "[data-topic]") == one_line


def test_the_brief_box_is_as_tall_as_the_drafted_brief(app):
    draft(app)
    assert not clipped(app, "[data-research-prompt]")


def test_the_brief_box_grows_as_the_brief_is_edited(app):
    draft(app)
    before = height(app, "[data-research-prompt]")
    app.fill("[data-research-prompt]", "one more line\n" * 60)
    assert height(app, "[data-research-prompt]") > before and not clipped(
        app, "[data-research-prompt]"
    )


def test_a_tall_brief_leaves_the_top_of_the_page_reachable(app):
    draft(app)
    app.fill("[data-research-prompt]", "one more line\n" * 120)
    app.locator("[data-empty] h1").scroll_into_view_if_needed()
    expect(app.locator("[data-empty] h1")).to_be_in_viewport()


def test_the_page_stays_where_the_reader_scrolled_it_while_the_brief_is_written(app):
    app.set_viewport_size({"width": 900, "height": 420})
    app.click('[data-tab="research"]')
    app.fill("[data-topic]", f"{LONG_TOPIC * 3} [[fake:slow]]")
    app.click("[data-research-draft]")
    expect(app.locator("[data-research-prompt]")).not_to_have_value("", timeout=20000)
    scrolled = app.locator("[data-empty]").evaluate(
        "el => { el.scrollTop = el.scrollHeight; return el.scrollTop; }"
    )

    expect(app.locator("[data-research-start]")).to_be_enabled(timeout=20000)

    assert app.locator("[data-empty]").evaluate("el => el.scrollTop") == scrolled > 0


def test_shift_enter_in_the_topic_adds_a_line_and_does_not_draft(app):
    app.click('[data-tab="research"]')
    app.fill("[data-topic]", TOPIC)
    app.press("[data-topic]", "Shift+Enter")
    expect(app.locator("[data-research-prompt]")).to_be_hidden()


def test_an_emptied_brief_cannot_be_started(app):
    draft(app)
    app.fill("[data-research-prompt]", "   ")
    expect(app.locator("[data-research-start]")).to_be_disabled()


def test_the_brief_field_has_a_label(app):
    draft(app)
    expect(app.get_by_label("Research brief")).to_be_visible()


# --- a dot that blinks while the brief is written -------------------------------

DOT = "[data-research-dot]"


def start_slow_draft(page):
    page.click('[data-tab="research"]')
    page.fill("[data-topic]", f"{TOPIC} [[fake:slow]]")
    page.click("[data-research-draft]")


def test_no_dot_shows_before_a_brief_is_drafted(app):
    app.click('[data-tab="research"]')
    expect(app.locator(DOT)).to_be_hidden()


def test_a_dot_shows_while_the_brief_is_written(app):
    start_slow_draft(app)
    expect(app.locator(DOT)).to_be_visible()


def test_the_dot_blinks(app):
    start_slow_draft(app)
    expect(app.locator(DOT)).to_have_css("animation-name", "lw-pulse")


def test_the_dot_goes_once_the_brief_is_written(app):
    draft(app)
    expect(app.locator(DOT)).to_be_hidden()


def test_the_dot_holds_still_for_a_reader_who_asked_for_less_motion(app):
    app.emulate_media(reduced_motion="reduce")
    start_slow_draft(app)
    expect(app.locator(DOT)).to_have_css("animation-name", "none")


TOP_DOT = "[data-research-dot-top]"


def test_a_dot_shows_above_the_brief_while_it_is_written(app):
    start_slow_draft(app)
    expect(app.locator(TOP_DOT)).to_be_visible()


def test_the_dot_above_the_brief_sits_over_the_text(app):
    start_slow_draft(app)
    expect(app.locator(TOP_DOT)).to_be_visible()
    dot = app.locator(TOP_DOT).bounding_box()
    assert dot["y"] + dot["height"] <= app.locator("[data-research-prompt]").bounding_box()["y"]


def test_the_dot_above_the_brief_blinks(app):
    start_slow_draft(app)
    expect(app.locator(TOP_DOT)).to_have_css("animation-name", "lw-pulse")


def test_the_dot_above_the_brief_goes_once_it_is_written(app):
    draft(app)
    expect(app.locator(TOP_DOT)).to_be_hidden()


# --- a brief of any length can be edited ------------------------------------------

TOO_LONG = "x" * (MAX_RESEARCH_PROMPT_CHARS + 1)


def test_a_brief_over_the_cap_can_still_be_typed_into(app):
    draft(app)
    app.fill("[data-research-prompt]", TOO_LONG)
    app.locator("[data-research-prompt]").press_sequentially("abc")
    expect(app.locator("[data-research-prompt]")).to_have_value(re.compile("abc"))


def test_a_brief_over_the_cap_says_so(app):
    draft(app)
    app.fill("[data-research-prompt]", TOO_LONG)
    expect(app.locator("[data-research-note]")).to_have_text(RESEARCH_PROMPT_TOO_LONG_MESSAGE)


def test_a_brief_over_the_cap_cannot_be_started(app):
    draft(app)
    app.fill("[data-research-prompt]", TOO_LONG)
    expect(app.locator("[data-research-start]")).to_be_disabled()


def test_a_brief_trimmed_back_under_the_cap_can_be_started(app):
    draft(app)
    app.fill("[data-research-prompt]", TOO_LONG)
    app.fill("[data-research-prompt]", "Short again.")
    expect(app.locator("[data-research-start]")).to_be_enabled()


def test_a_brief_trimmed_back_under_the_cap_drops_the_warning(app):
    draft(app)
    app.fill("[data-research-prompt]", TOO_LONG)
    app.fill("[data-research-prompt]", "Short again.")
    expect(app.locator("[data-research-note]")).not_to_have_text(RESEARCH_PROMPT_TOO_LONG_MESSAGE)


# --- a refresh keeps the draft ----------------------------------------------------

# What a browser sends on a hard refresh, and on no other load.
HARD_REFRESH = {"Cache-Control": "no-cache", "Pragma": "no-cache"}


def hard_refresh(page):
    page.set_extra_http_headers(HARD_REFRESH)
    page.reload()
    page.wait_for_selector("[data-empty]")


def test_a_refresh_keeps_the_topic(app):
    draft(app)
    app.reload()
    expect(app.locator("[data-topic]")).to_have_value(TOPIC)


def test_a_refresh_keeps_the_brief(app):
    draft(app)
    app.fill("[data-research-prompt]", "The brief, as I edited it.")
    app.reload()
    expect(app.locator("[data-research-prompt]")).to_have_value("The brief, as I edited it.")


def test_a_refresh_comes_back_on_the_research_tab(app):
    draft(app)
    app.reload()
    expect(app.locator("[data-research-prompt]")).to_be_visible()


def test_a_refreshed_brief_can_be_started(app):
    draft(app)
    app.reload()
    expect(app.locator("[data-research-start]")).to_be_enabled()


def test_a_refreshed_brief_is_shown_whole(app):
    draft(app)
    app.reload()
    expect(app.locator("[data-research-prompt]")).not_to_have_value("")
    assert not clipped(app, "[data-research-prompt]")


def test_a_refresh_keeps_a_topic_that_has_no_brief_yet(app):
    app.click('[data-tab="research"]')
    app.fill("[data-topic]", TOPIC)
    app.reload()
    expect(app.locator("[data-topic]")).to_have_value(TOPIC)


def test_a_topic_without_a_brief_comes_back_without_one(app):
    app.click('[data-tab="research"]')
    app.fill("[data-topic]", TOPIC)
    app.reload()
    expect(app.locator("[data-research-prompt]")).to_be_hidden()


def test_a_refresh_in_the_middle_of_a_draft_keeps_what_was_written(app):
    app.click('[data-tab="research"]')
    app.fill("[data-topic]", f"{TOPIC} [[fake:slow]]")
    app.click("[data-research-draft]")
    expect(app.locator("[data-research-prompt]")).not_to_have_value("", timeout=20000)
    app.reload()
    expect(app.locator("[data-research-prompt]")).not_to_have_value("")


def test_a_draft_cut_short_by_a_refresh_can_be_redrafted(app):
    app.click('[data-tab="research"]')
    app.fill("[data-topic]", f"{TOPIC} [[fake:slow]]")
    app.click("[data-research-draft]")
    expect(app.locator("[data-research-prompt]")).not_to_have_value("", timeout=20000)
    app.reload()
    expect(app.locator("[data-research-draft]")).to_be_enabled()


def test_a_hard_refresh_clears_the_topic(app):
    draft(app)
    hard_refresh(app)
    app.click('[data-tab="research"]')
    expect(app.locator("[data-topic]")).to_have_value("")


def test_a_hard_refresh_clears_the_brief(app):
    draft(app)
    hard_refresh(app)
    app.click('[data-tab="research"]')
    expect(app.locator("[data-research-prompt]")).to_be_hidden()


def test_a_hard_refresh_goes_back_to_the_first_tab(app):
    draft(app)
    hard_refresh(app)
    expect(app.locator("[data-paste]")).to_be_visible()


def test_a_draft_cleared_by_a_hard_refresh_stays_cleared(app):
    draft(app)
    hard_refresh(app)
    app.set_extra_http_headers({})
    app.reload()
    expect(app.locator("[data-paste]")).to_be_visible()


def test_a_started_research_leaves_no_draft_behind(app, server):
    finished(app)
    app.goto(server + "/")
    app.click('[data-tab="research"]')
    expect(app.locator("[data-topic]")).to_have_value("")


# --- the run --------------------------------------------------------------------


def test_the_edited_brief_is_what_the_run_follows(app):
    root = finished(app, "Cover only CPython.\nEDITED-BY-THE-READER")
    expect(root.locator("[data-body]")).to_contain_text("EDITED-BY-THE-READER")


def test_the_run_shows_each_search_as_it_happens(app):
    root = research(app, "A slow one. [[fake:slow]]")
    expect(root.locator("[data-activity]")).to_contain_text(QUERY, timeout=20000)


def test_the_run_shows_each_page_as_it_reads_it(app):
    root = research(app, "A slow one. [[fake:slow]]")
    expect(root.locator("[data-activity]")).to_contain_text(FETCHED, timeout=20000)


def test_the_run_says_it_is_researching(app):
    root = research(app, "A slow one. [[fake:slow]]")
    expect(root.locator("[data-wait-label]")).to_have_text("Researching the web…")


def test_the_report_lands_in_the_document_box(app):
    root = finished(app)
    expect(root.locator("[data-body] h1")).to_have_text("Python releases: a short report")


def test_narration_before_a_search_is_not_part_of_the_report(app):
    root = finished(app)
    expect(root.locator("[data-body]")).not_to_contain_text("Let me search")


def test_the_report_ends_with_its_sources(app):
    root = finished(app)
    expect(root.locator("[data-body]")).to_contain_text(SOURCES_HEADING)


def test_a_search_result_nobody_cited_is_not_a_source(app):
    root = finished(app)
    expect(root.locator("[data-body]")).not_to_contain_text(UNCITED)


def test_a_citation_the_run_never_saw_is_listed_apart(app):
    root = finished(app)
    expect(root.locator("[data-body]")).to_contain_text(UNVERIFIED_HEADING)


def test_a_citation_the_run_never_saw_is_flagged_on_the_box(app):
    root = finished(app)
    expect(root.locator("[data-sources-flag]")).to_contain_text("1 citation")


def test_the_canvas_takes_the_title_of_the_report(app):
    finished(app)
    expect(app.locator("[data-title]")).to_have_text("Python releases: a short report")


def test_the_activity_log_steps_aside_once_the_report_is_in(app):
    root = finished(app)
    expect(root.locator("[data-activity]")).to_be_hidden()


def test_the_topic_stays_on_the_report(app):
    root = finished(app)
    expect(root.locator("[data-question]")).to_have_text(TOPIC)


def test_a_finished_report_keeps_its_flag_after_a_reload(app):
    finished(app)
    app.reload()
    expect(app.locator(ROOT)).to_have_attribute("data-status", "done")
    expect(app.locator(f"{ROOT} [data-sources-flag]")).to_contain_text("1 citation")


# --- when it does not finish ----------------------------------------------------


def test_a_failed_run_is_worded_for_a_report(app):
    root = research(app, "This one breaks. [[fake:error]]")
    expect(root).to_have_attribute("data-status", "failed", timeout=20000)
    expect(root.locator("[data-reason]")).to_have_text(RESEARCH_CRASHED_REASON)


def test_a_failed_run_offers_to_retry_the_research(app):
    root = research(app, "This one breaks. [[fake:error]]")
    expect(root.locator("[data-retry]")).to_have_text("Retry research", timeout=20000)


def test_a_run_that_never_reached_the_web_is_not_saved_as_a_report(app):
    root = research(app, "No web here. [[fake:noweb]]")
    expect(root).to_have_attribute("data-status", "failed", timeout=20000)
    expect(root.locator("[data-reason]")).to_have_text(RESEARCH_NO_WEB_REASON)


def test_a_reload_in_the_middle_of_a_run_leaves_a_retry(app):
    root = research(app, "A slow one. [[fake:slow]]")
    expect(root.locator("[data-activity]")).to_contain_text(QUERY, timeout=20000)
    app.reload()
    expect(app.locator(ROOT)).to_have_attribute("data-status", "interrupted", timeout=20000)
    expect(app.locator(f"{ROOT} [data-retry]")).to_be_visible()
