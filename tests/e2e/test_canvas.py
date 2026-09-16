"""Reading, highlighting, asking, and everything the answer box does afterwards."""

from __future__ import annotations

import pytest
from playwright.sync_api import expect
from tests.fixtures.editor import (
    CONTENT,
    CURSOR,
    EDIT_BUTTON,
    EDITOR,
    LINE,
    SAVE_BUTTON,
    SCROLLER,
    edit,
    open_editor,
    source_of,
)
from tests.fixtures.selection import QUOTE, SELECT, ask, find_offsets, highlight
from tests.fixtures.viewport import (
    box_rect,
    edge_start,
    rect_of,
    to_client,
    transform_of,
    view_centre,
)

from research_canvas.config import CHROME_HEIGHT, MIN_BOX_WIDTH, ROOT_BOX_WIDTH

pytestmark = pytest.mark.e2e


# --- the root box ---------------------------------------------------------


def test_root_box_renders_the_document(canvas):
    expect(canvas.locator('[data-box="b1"] [data-body] h1')).to_have_text(
        "Attention Is All You Need"
    )


def test_root_box_is_labelled_as_the_document(canvas):
    expect(canvas.locator('[data-box="b1"] .box__head')).to_contain_text("Document")


def test_root_box_cannot_be_deleted(canvas):
    expect(canvas.locator('[data-box="b1"] [data-delete]')).to_have_count(0)


# --- selection gating -----------------------------------------------------


def test_a_short_selection_does_not_offer_to_ask(canvas):
    start, _ = find_offsets(canvas, "b1", "The")
    canvas.evaluate(SELECT, ["b1", start, start + 2])
    expect(canvas.locator("[data-ask]")).to_have_count(0)


def test_highlighting_a_passage_opens_the_ask_popover(canvas):
    highlight(canvas, "b1", QUOTE)
    expect(canvas.locator("[data-ask]")).to_be_visible()
    expect(canvas.locator("[data-ask-quote]")).to_contain_text(QUOTE)


def test_the_ask_popover_can_be_dismissed(canvas):
    highlight(canvas, "b1", QUOTE)
    canvas.click("[data-ask-cancel]")
    expect(canvas.locator("[data-ask]")).to_have_count(0)


def test_the_dismiss_control_is_a_borderless_cross(canvas):
    highlight(canvas, "b1", QUOTE)
    close = canvas.locator("[data-ask-cancel]")
    expect(close).to_have_text("\u00d7")
    assert close.evaluate("(el) => getComputedStyle(el).borderTopWidth") == "0px"


def test_the_dismiss_control_still_says_what_it_does(canvas):
    highlight(canvas, "b1", QUOTE)
    expect(canvas.locator("[data-ask-cancel]")).to_have_attribute("aria-label", "Close")


def test_escape_dismisses_the_ask_popover(canvas):
    highlight(canvas, "b1", QUOTE)
    canvas.keyboard.press("Escape")
    expect(canvas.locator("[data-ask]")).to_have_count(0)


def test_clicking_away_dismisses_the_ask_popover(canvas):
    highlight(canvas, "b1", QUOTE)
    height = canvas.evaluate("() => window.innerHeight")
    canvas.mouse.click(10, height - 10)
    expect(canvas.locator("[data-ask]")).to_have_count(0)


def test_clicking_inside_the_ask_popover_keeps_it_open(canvas):
    highlight(canvas, "b1", QUOTE)
    canvas.click("[data-ask-quote]")
    expect(canvas.locator("[data-ask]")).to_be_visible()


def test_web_search_is_on_by_default_and_can_be_turned_off(canvas):
    highlight(canvas, "b1", QUOTE)
    toggle = canvas.locator("[data-ask-web]")
    expect(toggle).to_have_attribute("aria-pressed", "true")
    toggle.click()
    expect(toggle).to_have_attribute("aria-pressed", "false")


# --- asking ---------------------------------------------------------------


def test_asking_adds_an_answer_box_at_the_next_depth(canvas):
    ask(canvas, "b1", QUOTE, "What is a residual connection?")
    expect(canvas.locator('[data-box="b2"]')).to_be_visible()
    expect(canvas.locator('[data-box="b2"] .box__head')).to_contain_text("Depth 2")


def test_enter_sends_the_question(canvas):
    highlight(canvas, "b1", QUOTE)
    canvas.wait_for_selector("[data-ask]")
    canvas.fill("[data-ask-input]", "What is a residual connection?")
    canvas.press("[data-ask-input]", "Enter")
    expect(canvas.locator('[data-box="b2"]')).to_be_visible()


def test_shift_enter_opens_a_new_line_instead_of_sending(canvas):
    highlight(canvas, "b1", QUOTE)
    canvas.wait_for_selector("[data-ask]")
    canvas.fill("[data-ask-input]", "First line")
    canvas.press("[data-ask-input]", "Shift+Enter")
    canvas.type("[data-ask-input]", "second line")
    expect(canvas.locator("[data-ask-input]")).to_have_value("First line\nsecond line")
    expect(canvas.locator('[data-box="b2"]')).to_have_count(0)


def test_asking_does_not_move_the_camera(canvas):
    before = transform_of(canvas)
    ask(canvas, "b1", QUOTE, "What is a residual connection?")
    canvas.wait_for_selector('[data-box="b2"]')
    after = transform_of(canvas)
    assert before == after


def test_asking_says_where_the_answer_went(canvas):
    ask(canvas, "b1", QUOTE, "What is a residual connection?")
    expect(canvas.locator("[data-toast]")).to_have_text(
        "Answer box added at depth 2 — the view stays where you are"
    )


def test_the_answer_streams_in_and_finishes(canvas):
    ask(canvas, "b1", QUOTE, "What is a residual connection?")
    expect(canvas.locator('[data-box="b2"]')).to_have_attribute(
        "data-status", "done", timeout=20000
    )
    expect(canvas.locator('[data-box="b2"] [data-body]')).to_contain_text(
        "carries the input of a sublayer"
    )


def test_the_question_is_shown_on_the_answer_box(canvas):
    ask(canvas, "b1", QUOTE, "What is a residual connection?")
    expect(canvas.locator('[data-box="b2"] [data-question]')).to_have_text(
        "What is a residual connection?"
    )


def test_the_highlight_is_marked_in_the_source_box(canvas):
    ask(canvas, "b1", QUOTE, "What is a residual connection?")
    mark = canvas.locator('[data-box="b1"] mark[data-anchor]')
    expect(mark.first).to_contain_text(QUOTE)
    expect(mark.last).to_have_attribute("data-target", "b2")


def test_an_edge_joins_the_highlight_to_the_answer(canvas):
    ask(canvas, "b1", QUOTE, "What is a residual connection?")
    canvas.wait_for_selector('[data-box="b2"][data-status="done"]', timeout=20000)
    expect(canvas.locator('[data-edges] [data-edge="b2"]')).to_have_count(1)


def test_the_lead_line_leaves_from_the_underline_not_through_the_words(canvas):
    """It must read as the underline continuing, and never strike through the text."""
    ask(canvas, "b1", QUOTE, "What is a residual connection?")
    canvas.wait_for_selector('[data-box="b2"][data-status="done"]', timeout=20000)
    mark = rect_of(canvas, "mark[data-anchor-edge]")
    start = edge_start(canvas, "b2")
    assert abs(start["y"] - (mark["y"] + mark["h"])) <= 2
    assert start["y"] > mark["y"] + mark["h"] / 2


def test_you_can_ask_again_inside_an_answer(canvas):
    ask(canvas, "b1", QUOTE, "What is a residual connection?")
    canvas.wait_for_selector('[data-box="b2"][data-status="done"]', timeout=20000)
    ask(canvas, "b2", "carries the input", "Why add it back?")
    expect(canvas.locator('[data-box="b3"] .box__head')).to_contain_text("Depth 3")


def test_a_running_box_refuses_a_second_question(canvas):
    ask(canvas, "b1", QUOTE, "Explain this [[fake:slow]]")
    canvas.wait_for_selector('[data-box="b2"][data-status="running"]')
    expect(canvas.locator('[data-box="b2"] [data-body]')).to_contain_text("residual connection")
    highlight(canvas, "b2", "residual connection")
    expect(canvas.locator("[data-toast]")).to_have_text(
        "That box is still running — ask once it is done"
    )


def test_the_run_pill_shows_while_an_answer_runs(canvas):
    ask(canvas, "b1", QUOTE, "Explain this [[fake:slow]]")
    expect(canvas.locator("[data-runpill]")).to_be_visible()
    canvas.wait_for_selector('[data-box="b2"][data-status="done"]', timeout=20000)
    expect(canvas.locator("[data-runpill]")).to_be_hidden()


def test_clicking_the_highlight_jumps_to_its_answer(canvas):
    ask(canvas, "b1", QUOTE, "What is a residual connection?")
    canvas.wait_for_selector('[data-box="b2"][data-status="done"]', timeout=20000)
    before = transform_of(canvas)
    canvas.locator('[data-box="b1"] mark[data-anchor]').first.click()
    canvas.wait_for_timeout(700)
    after = transform_of(canvas)
    assert before != after


def test_an_answer_box_can_be_deleted(canvas):
    ask(canvas, "b1", QUOTE, "What is a residual connection?")
    canvas.wait_for_selector('[data-box="b2"][data-status="done"]', timeout=20000)
    canvas.click('[data-box="b2"] [data-delete]')
    expect(canvas.locator('[data-box="b2"]')).to_have_count(0)
    expect(canvas.locator('[data-box="b1"] mark[data-anchor]')).to_have_count(0)


# --- moving things around -------------------------------------------------


def test_a_box_can_be_dragged_by_its_header(canvas):
    box = canvas.locator('[data-box="b1"]')
    before = box.bounding_box()
    canvas.mouse.move(before["x"] + 120, before["y"] + 14)
    canvas.mouse.down()
    canvas.mouse.move(before["x"] + 320, before["y"] + 164, steps=8)
    canvas.mouse.up()
    after = box.bounding_box()
    assert round(after["x"] - before["x"]) == 200
    assert round(after["y"] - before["y"]) == 150


def test_a_box_can_be_resized_from_its_right_edge(canvas):
    box = canvas.locator('[data-box="b1"]')
    before = box.bounding_box()
    handle = canvas.locator('[data-box="b1"] [data-resize]').bounding_box()
    canvas.mouse.move(handle["x"] + 6, handle["y"] + 200)
    canvas.mouse.down()
    canvas.mouse.move(handle["x"] + 126, handle["y"] + 200, steps=8)
    canvas.mouse.up()
    assert round(box.bounding_box()["width"] - before["width"]) == 120


def test_the_desk_pans_when_you_drag_it(canvas):
    before = transform_of(canvas)
    canvas.mouse.move(1200, 700)
    canvas.mouse.down()
    canvas.mouse.move(1100, 620, steps=6)
    canvas.mouse.up()
    after = transform_of(canvas)
    assert before != after


def test_the_minimap_is_drawn_from_the_boxes(canvas):
    expect(canvas.locator("[data-minimap] rect[data-mini-box]")).to_have_count(1)


def test_clicking_the_minimap_moves_the_camera(canvas):
    before = transform_of(canvas)
    canvas.click("[data-minimap]", position={"x": 40, "y": 30})
    canvas.wait_for_timeout(600)
    after = transform_of(canvas)
    assert before != after


# --- it survives a reload -------------------------------------------------


def test_everything_survives_a_reload(canvas, server):
    ask(canvas, "b1", QUOTE, "What is a residual connection?")
    canvas.wait_for_selector('[data-box="b2"][data-status="done"]', timeout=20000)
    canvas.reload()
    canvas.wait_for_selector('[data-box="b2"]')
    expect(canvas.locator('[data-box="b2"] [data-question]')).to_have_text(
        "What is a residual connection?"
    )
    expect(canvas.locator('[data-box="b1"] mark[data-anchor]').first).to_contain_text(QUOTE)
    expect(canvas.locator('[data-edges] [data-edge="b2"]')).to_have_count(1)


def test_a_moved_box_stays_where_you_put_it(canvas):
    box = canvas.locator('[data-box="b1"]')
    before = box.bounding_box()
    canvas.mouse.move(before["x"] + 120, before["y"] + 14)
    canvas.mouse.down()
    canvas.mouse.move(before["x"] + 300, before["y"] + 14, steps=6)
    canvas.mouse.up()
    canvas.wait_for_timeout(400)
    canvas.reload()
    canvas.wait_for_selector('[data-box="b1"]')
    assert round(box.bounding_box()["x"] - before["x"]) == 180


# --- editing a box --------------------------------------------------------


EDITED = "# Attention Is All You Need\n\nA residual connection carries the input forward."


def test_the_document_box_can_be_edited(canvas):
    expect(canvas.locator(EDIT_BUTTON.format(box="b1"))).to_be_visible()


def test_an_answer_box_can_be_edited(canvas):
    ask(canvas, "b1", QUOTE, "What is a residual connection?")
    canvas.wait_for_selector('[data-box="b2"][data-status="done"]', timeout=20000)
    expect(canvas.locator(EDIT_BUTTON.format(box="b2"))).to_be_visible()


def test_editing_shows_the_markdown_source_not_the_rendered_html(canvas):
    open_editor(canvas, "b1")
    assert source_of(canvas, "b1").startswith("# Attention Is All You Need")


def test_the_editor_shows_the_whole_document(canvas):
    """The box is as tall as its document when rendered, and edit mode matches it."""
    open_editor(canvas, "b1")
    assert "machine translation" in source_of(canvas, "b1")


def test_the_editor_does_not_scroll_inside_itself(canvas):
    open_editor(canvas, "b1")
    scroller = canvas.locator(SCROLLER.format(box="b1"))
    overflow = scroller.evaluate("(el) => el.scrollHeight - el.clientHeight")
    assert overflow <= 1


def test_the_editor_is_labelled_for_screen_readers(canvas):
    open_editor(canvas, "b1")
    expect(canvas.locator(CONTENT.format(box="b1"))).to_have_attribute(
        "aria-label", "Markdown source"
    )


def test_editing_hides_the_rendered_body(canvas):
    open_editor(canvas, "b1")
    expect(canvas.locator('[data-box="b1"] [data-body]')).to_be_hidden()


def test_the_editor_opens_with_the_caret_on_the_first_line(canvas):
    """The reader wants to start where the document starts, not at its end."""
    open_editor(canvas, "b1")
    cursor = canvas.locator(CURSOR.format(box="b1")).bounding_box()
    first_line = canvas.locator(LINE.format(box="b1")).first.bounding_box()
    assert abs(cursor["y"] - first_line["y"]) < first_line["height"]


def test_tab_indents_the_line(canvas):
    edit(canvas, "b1", "one")
    canvas.keyboard.press("Home")
    canvas.keyboard.press("Tab")
    assert source_of(canvas, "b1") == "  one"


def test_enter_saves_the_edit(canvas):
    edit(canvas, "b1", EDITED)
    canvas.keyboard.press("Enter")
    expect(canvas.locator('[data-box="b1"] [data-body]')).to_contain_text(
        "carries the input forward"
    )
    expect(canvas.locator(EDITOR.format(box="b1"))).to_be_hidden()


def test_shift_enter_opens_a_new_line_instead_of_saving(canvas):
    edit(canvas, "b1", "# Kept")
    canvas.keyboard.press("Shift+Enter")
    canvas.keyboard.insert_text("a second line")
    assert source_of(canvas, "b1") == "# Kept\na second line"
    expect(canvas.locator(EDITOR.format(box="b1"))).to_be_visible()


def test_shift_enter_carries_a_list_marker_to_the_next_line(canvas):
    edit(canvas, "b1", "# Kept\n\n- first item")
    canvas.keyboard.press("Shift+Enter")
    canvas.keyboard.insert_text("second item")
    assert source_of(canvas, "b1").endswith("- first item\n- second item")


def test_saving_an_edit_rewrites_the_body(canvas):
    edit(canvas, "b1", EDITED)
    canvas.click(SAVE_BUTTON.format(box="b1"))
    expect(canvas.locator('[data-box="b1"] [data-body]')).to_contain_text(
        "carries the input forward"
    )
    expect(canvas.locator(EDITOR.format(box="b1"))).to_be_hidden()


def test_escape_leaves_edit_mode(canvas):
    open_editor(canvas, "b1")
    canvas.keyboard.press("Escape")
    expect(canvas.locator(EDITOR.format(box="b1"))).to_be_hidden()
    expect(canvas.locator('[data-box="b1"] [data-body]')).to_be_visible()


def test_escape_throws_the_edit_away(canvas):
    edit(canvas, "b1", "# Gone\n\nThis was never saved.")
    canvas.keyboard.press("Escape")
    expect(canvas.locator('[data-box="b1"] [data-body]')).not_to_contain_text(
        "This was never saved."
    )
    expect(canvas.locator('[data-box="b1"] [data-body] h1')).to_have_text(
        "Attention Is All You Need"
    )


def test_a_blank_edit_is_refused_with_the_reason(canvas):
    edit(canvas, "b1", "   ")
    canvas.click(SAVE_BUTTON.format(box="b1"))
    expect(canvas.locator("[data-toast]")).to_contain_text("cannot be empty")
    expect(canvas.locator(EDITOR.format(box="b1"))).to_be_visible()


def test_an_edit_survives_a_reload(canvas):
    edit(canvas, "b1", EDITED)
    canvas.click(SAVE_BUTTON.format(box="b1"))
    expect(canvas.locator('[data-box="b1"] [data-body]')).to_contain_text(
        "carries the input forward"
    )
    canvas.reload()
    canvas.wait_for_selector('[data-box="b1"]')
    expect(canvas.locator('[data-box="b1"] [data-body]')).to_contain_text(
        "carries the input forward"
    )


def test_an_edit_that_keeps_the_passage_keeps_the_mark_and_its_edge(canvas):
    ask(canvas, "b1", QUOTE, "What is a residual connection?")
    canvas.wait_for_selector('[data-box="b2"][data-status="done"]', timeout=20000)
    edit(canvas, "b1", EDITED)
    canvas.click(SAVE_BUTTON.format(box="b1"))
    expect(canvas.locator('[data-box="b1"] mark[data-anchor]').first).to_contain_text(QUOTE)
    expect(canvas.locator('[data-edges] [data-edge="b2"]')).to_have_count(1)


def test_a_running_box_cannot_be_edited(canvas):
    ask(canvas, "b1", QUOTE, "Explain this [[fake:slow]]")
    canvas.wait_for_selector('[data-box="b2"][data-status="running"]')
    expect(canvas.locator(EDIT_BUTTON.format(box="b2"))).to_be_hidden()
