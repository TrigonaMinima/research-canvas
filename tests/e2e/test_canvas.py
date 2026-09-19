"""Reading, highlighting, asking, and everything the answer box does afterwards."""

from __future__ import annotations

import re
from itertools import pairwise

import pytest
from playwright.sync_api import expect
from tests.fixtures.editor import (
    CONTENT,
    CURSOR,
    EDIT_BUTTON,
    EDITOR,
    LINE,
    SAVE_BOTTOM,
    SAVE_TOP,
    SCROLLER,
    edit,
    open_editor,
    source_of,
)
from tests.fixtures.selection import (
    QUOTE,
    SELECT,
    ask,
    find_offsets,
    highlight,
    send_question,
)
from tests.fixtures.viewport import (
    box_rect,
    canvas_id_of,
    drag_header_by,
    edge_start,
    line_rects_of,
    rect_of,
    to_client,
    transform_of,
    view_centre,
    wait_for_camera,
    zoom_to_fit,
)

from research_canvas.config import BOX_GAP, CHROME_HEIGHT, MIN_BOX_WIDTH, ROOT_BOX_WIDTH

from .conftest import canvas_from

# BOX_GAP is the exact fixed gap `restack()` must leave between two boxes stacked
# under the same parent, read from the server's own copy rather than retyped.

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


def test_a_wrapped_highlight_keeps_its_lead_line_attached(canvas):
    """A wrapped mark measures as the union of all its lines, not the last one it ends on."""
    start, _ = find_offsets(canvas, "b1", "The dominant sequence transduction models")
    _, end = find_offsets(canvas, "b1", "an encoder and a decoder.")
    canvas.evaluate(SELECT, ["b1", start, end])
    send_question(canvas, "What does this passage describe?")
    canvas.wait_for_selector('[data-box="b2"][data-status="done"]', timeout=20000)

    lines = line_rects_of(canvas, "mark[data-anchor-edge]")
    last_line = lines[-1]
    # Preconditions: the mark really does wrap, and its widest line really does end
    # well right of its last one, so no font or box width can make this vacuous.
    assert len(lines) >= 2
    widest = max(line["x"] + line["w"] for line in lines)
    assert widest - (last_line["x"] + last_line["w"]) >= 40

    start_x = edge_start(canvas, "b2")["x"]
    assert abs(start_x - (last_line["x"] + last_line["w"])) <= 2


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
    drag_header_by(canvas, "b1", 200, 150)
    after = box.bounding_box()
    assert round(after["x"] - before["x"]) == 200
    assert round(after["y"] - before["y"]) == 150


def test_a_box_can_be_resized_from_its_right_edge(canvas):
    box = canvas.locator('[data-box="b1"]')
    before = box.bounding_box()
    resize(canvas, "b1", "right", 120)
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
    drag_header_by(canvas, "b1", 180, 0)
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
    """The box is as tall as its document when rendered, and edit mode matches it.

    CodeMirror builds only the lines near the view and the rest as the camera reaches
    them, so the tail of a long document is panned to rather than assumed. Asserting on
    the first screenful alone passes or fails on a handful of pixels of box chrome."""
    open_editor(canvas, "b1")
    zoom_to_fit(canvas)
    wait_for_camera(canvas)
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
    canvas.click(SAVE_BOTTOM.format(box="b1"))
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
    canvas.click(SAVE_TOP.format(box="b1"))
    expect(canvas.locator("[data-toast]")).to_contain_text("cannot be empty")
    expect(canvas.locator(EDITOR.format(box="b1"))).to_be_visible()


def test_an_edit_survives_a_reload(canvas):
    edit(canvas, "b1", EDITED)
    canvas.click(SAVE_TOP.format(box="b1"))
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
    canvas.click(SAVE_TOP.format(box="b1"))
    expect(canvas.locator('[data-box="b1"] mark[data-anchor]').first).to_contain_text(QUOTE)
    expect(canvas.locator('[data-edges] [data-edge="b2"]')).to_have_count(1)


def test_a_running_box_cannot_be_edited(canvas):
    ask(canvas, "b1", QUOTE, "Explain this [[fake:slow]]")
    canvas.wait_for_selector('[data-box="b2"][data-status="running"]')
    expect(canvas.locator(EDIT_BUTTON.format(box="b2"))).to_be_hidden()


# --- Enter saves, wherever the caret is -----------------------------------

# Markdown's own keymap used to bind Enter at a precedence the app's binding could not
# reach, and its command only claims the key where a list or a quote is being continued.
# So Enter saved in prose and did nothing anywhere else. One case per context it claimed.


def test_enter_saves_from_inside_a_list(canvas):
    edit(canvas, "b1", "# Kept\n\n- first item")
    canvas.keyboard.press("Enter")
    expect(canvas.locator(EDITOR.format(box="b1"))).to_be_hidden()
    expect(canvas.locator('[data-box="b1"] [data-body] li')).to_have_text("first item")


def test_enter_saves_from_inside_a_numbered_list(canvas):
    edit(canvas, "b1", "# Kept\n\n1. first item")
    canvas.keyboard.press("Enter")
    expect(canvas.locator(EDITOR.format(box="b1"))).to_be_hidden()
    expect(canvas.locator('[data-box="b1"] [data-body] ol li')).to_have_text("first item")


def test_enter_saves_from_inside_a_nested_list(canvas):
    edit(canvas, "b1", "# Kept\n\n- outer\n  - inner")
    canvas.keyboard.press("Enter")
    expect(canvas.locator(EDITOR.format(box="b1"))).to_be_hidden()
    expect(canvas.locator('[data-box="b1"] [data-body] li li')).to_have_text("inner")


def test_enter_saves_from_inside_a_blockquote(canvas):
    edit(canvas, "b1", "# Kept\n\n> A quoted line")
    canvas.keyboard.press("Enter")
    expect(canvas.locator(EDITOR.format(box="b1"))).to_be_hidden()
    expect(canvas.locator('[data-box="b1"] [data-body] blockquote')).to_contain_text(
        "A quoted line"
    )


# --- a Save button at each end --------------------------------------------

# The editor never scrolls inside itself, so a long document makes a tall box. One Save
# at the foot of it is a Save nobody can see.
LONG_EDIT = "# Long\n\n" + "\n\n".join(
    f"Paragraph {n} of a document that runs on." for n in range(120)
)


def test_the_save_button_sits_above_the_editing_surface(canvas):
    open_editor(canvas, "b1")
    save = canvas.locator(SAVE_TOP.format(box="b1")).bounding_box()
    editor = canvas.locator(EDITOR.format(box="b1")).bounding_box()
    assert save["y"] + save["height"] <= editor["y"]


def test_there_is_a_save_button_at_each_end_of_the_editor(canvas):
    open_editor(canvas, "b1")
    editor = canvas.locator(EDITOR.format(box="b1")).bounding_box()
    bottom = canvas.locator(SAVE_BOTTOM.format(box="b1")).bounding_box()
    expect(canvas.locator(SAVE_TOP.format(box="b1"))).to_be_visible()
    assert bottom["y"] >= editor["y"] + editor["height"]


def test_the_save_button_stays_on_screen_on_a_long_document(canvas):
    edit(canvas, "b1", LONG_EDIT)
    editor = canvas.locator(EDITOR.format(box="b1")).bounding_box()
    save = canvas.locator(SAVE_TOP.format(box="b1")).bounding_box()
    height = canvas.viewport_size["height"]
    assert editor["y"] + editor["height"] > height  # the source runs past the window
    assert 0 <= save["y"] < height  # and the way out of it is still in view


def test_typing_a_long_document_does_not_scroll_the_desk(canvas):
    """CodeMirror scrolls its caret into view by scrolling the nearest ancestor that
    will move, and `overflow:hidden` does not refuse a programmatic scroll. A scrolled
    desk slides the whole canvas out from under the camera."""
    edit(canvas, "b1", LONG_EDIT)
    desk = canvas.locator("[data-desk]")
    assert desk.evaluate("(el) => [el.scrollTop, el.scrollLeft]") == [0, 0]


def test_the_top_save_button_saves_the_edit(canvas):
    edit(canvas, "b1", EDITED)
    canvas.click(SAVE_TOP.format(box="b1"))
    expect(canvas.locator('[data-box="b1"] [data-body]')).to_contain_text(
        "carries the input forward"
    )
    expect(canvas.locator(EDITOR.format(box="b1"))).to_be_hidden()


def test_the_edit_button_is_hidden_while_the_box_is_being_edited(canvas):
    """Clicking it during an edit would reopen the editor and drop what was typed."""
    open_editor(canvas, "b1")
    expect(canvas.locator(EDIT_BUTTON.format(box="b1"))).to_be_hidden()
    canvas.keyboard.press("Escape")
    expect(canvas.locator(EDIT_BUTTON.format(box="b1"))).to_be_visible()


# --- double click to edit -------------------------------------------------


def test_double_clicking_the_body_opens_the_editor(canvas):
    canvas.dblclick('[data-box="b1"] [data-body] h1')
    canvas.wait_for_selector(CONTENT.format(box="b1"))
    assert source_of(canvas, "b1").startswith("# Attention Is All You Need")


def test_double_clicking_the_body_does_not_open_the_ask_popover(canvas):
    """The pair of clicks leaves a word selected, and a selection is a question."""
    canvas.dblclick('[data-box="b1"] [data-body] h1')
    canvas.wait_for_selector(CONTENT.format(box="b1"))
    canvas.wait_for_timeout(500)  # the selection is read back on a timeout
    expect(canvas.locator("[data-ask]")).to_have_count(0)


def test_double_clicking_inside_the_editor_keeps_the_unsaved_edit(canvas):
    edit(canvas, "b1", "# Kept\n\nNot saved yet.")
    canvas.dblclick(CONTENT.format(box="b1"))
    canvas.wait_for_timeout(500)  # a reopened editor would have thrown the text away
    expect(canvas.locator(EDITOR.format(box="b1"))).to_be_visible()
    assert "Not saved yet." in source_of(canvas, "b1")


def test_double_clicking_a_highlight_jumps_and_opens_nothing(canvas):
    """The first click of the pair flies the camera, so the second lands who knows
    where. The jump still happens; no editor anywhere, and no popover either."""
    ask(canvas, "b1", QUOTE, "What is a residual connection?")
    canvas.wait_for_selector('[data-box="b2"][data-status="done"]', timeout=20000)
    before = transform_of(canvas)
    canvas.locator('[data-box="b1"] mark[data-anchor]').first.dblclick()
    wait_for_camera(canvas)
    assert transform_of(canvas) != before
    expect(canvas.locator("[data-editor]")).to_have_count(0)
    expect(canvas.locator("[data-ask]")).to_have_count(0)


def test_double_clicking_a_link_follows_it_and_opens_no_editor(app):
    """A fragment, not a real address: a live link would navigate away from the app."""
    doc = "# A document with a link\n\nSee [the note](#note) for the rest of it."
    page = canvas_from(app, doc)
    page.dblclick('[data-box="b1"] [data-body] a')
    expect(page).to_have_url(re.compile(r"#note$"))
    expect(page.locator("[data-editor]")).to_have_count(0)


def test_double_clicking_an_unfinished_answer_does_not_open_the_editor(canvas):
    """Same rule as the Edit button, which is hidden until the answer lands."""
    ask(canvas, "b1", QUOTE, "Explain this [[fake:slow]]")
    canvas.wait_for_selector('[data-box="b2"][data-status="running"]')
    body = canvas.locator('[data-box="b2"] [data-body]')
    expect(body).not_to_be_empty()  # the stream has started, so there is text to click
    body.dblclick()
    canvas.wait_for_timeout(500)  # long enough for the editor's fetch to have landed
    expect(canvas.locator(EDITOR.format(box="b2"))).to_have_count(0)


# --- folding, framing, and finding your way back --------------------------

# The chrome bar sits over the desk, so a jump that parks a header under it has
# hidden the one row you need to grab.


# The edges layer has no viewBox, so a point on a path is already in canvas px.
EDGE_MIDPOINT = """(target) => {
  // The curve is the last path in the group; the dashed lead, when drawn, is first.
  const path = document.querySelector('[data-edge="' + target + '"] path:last-of-type');
  const at = path.getPointAtLength(path.getTotalLength() / 2);
  return [at.x, at.y];
}"""

# Computed CSS answers in seconds; the tests count in milliseconds.
FLASH_DURATION = """(box) => {
  const el = document.querySelector('[data-box="' + box + '"]');
  return parseFloat(getComputedStyle(el).animationDuration) * 1000;
}"""

# How far into the ring we are: the only way to see a restart that did not happen.
FLASH_ELAPSED = """(box) => {
  const [ring] = document.querySelector('[data-box="' + box + '"]')
    .getAnimations().filter((a) => a.animationName === 'lw-flash');
  return ring ? ring.currentTime : null;
}"""

# One line, however the stylesheet says so, rather than the property that says it.
ONE_LINE_TALL = """(el) => {
  const line = parseFloat(getComputedStyle(el).lineHeight);
  return el.offsetHeight < 2 * line;
}"""


QUOTE_BEFORE_QUESTION = """(id) => {
  const scope = document.querySelector('[data-box="' + id + '"]');
  const quote = scope.querySelector('[data-quote]');
  const question = scope.querySelector('[data-question]');
  return !!(quote.compareDocumentPosition(question) & Node.DOCUMENT_POSITION_FOLLOWING);
}"""


def overlap(a: dict, b: dict) -> bool:
    """Whether two canvas rects share any area at all."""
    return (
        a["x"] < b["x"] + b["w"]
        and b["x"] < a["x"] + a["w"]
        and a["y"] < b["y"] + b["h"]
        and b["y"] < a["y"] + a["h"]
    )


def gap_between(a: dict, b: dict) -> float:
    """The vertical space between two stacked boxes, in canvas pixels."""
    upper, lower = (a, b) if a["y"] <= b["y"] else (b, a)
    return lower["y"] - (upper["y"] + upper["h"])


def settled(page) -> None:
    """Give the open-time restack pass its frames.

    Opening a canvas schedules the pass behind two animation frames, and again behind
    the font swap. `wait_for_selector` returns as soon as the box exists, which can be
    before either has run, so a test that reads a rect right after it reads a race.
    """
    page.wait_for_function("() => document.fonts.status === 'loaded'")
    page.evaluate(
        """() => new Promise((done) => {
            let left = 4;
            const tick = () => (left-- ? requestAnimationFrame(tick) : done());
            requestAnimationFrame(tick);
        })"""
    )


def resize(page, box: str, edge: str, dx: float) -> None:
    """Drag one of a box's two handles sideways by dx screen pixels."""
    handle = page.locator(f'[data-box="{box}"] [data-resize="{edge}"]').bounding_box()
    x = handle["x"] + handle["width"] / 2
    # The handle runs the full height of a box that can be taller than the window.
    y = handle["y"] + min(200, handle["height"] / 2)
    page.mouse.move(x, y)
    page.mouse.down()
    page.mouse.move(x + dx, y, steps=8)
    page.mouse.up()


def answer_from_root(
    page, question: str = "What is a residual connection?", needle: str = QUOTE
) -> None:
    """Ask about a passage in the document and wait for the answer to land."""
    ask(page, "b1", needle, question)
    page.wait_for_selector('[data-box="b2"][data-status="done"]', timeout=20000)


def jump_to(page, box: str) -> None:
    """Click the highlight that opened a box and wait for the camera to settle."""
    page.locator(f'[data-box="b1"] mark[data-target="{box}"]').first.click()
    page.wait_for_timeout(700)


# --- resizing from either edge --------------------------------------------


def test_should_widen_the_box_when_its_left_handle_is_dragged_outwards(canvas):
    box = canvas.locator('[data-box="b1"]')
    before = box.bounding_box()
    resize(canvas, "b1", "left", -120)
    after = box.bounding_box()
    assert round(after["width"] - before["width"]) == 120
    # The left edge moves on its own. The right one must stay where the reader left it.
    assert round(after["x"] + after["width"]) == round(before["x"] + before["width"])


def test_should_stop_the_left_handle_at_the_minimum_width(canvas):
    box = canvas.locator('[data-box="b1"]')
    before = box.bounding_box()
    resize(canvas, "b1", "left", 900)
    after = box.bounding_box()
    assert round(after["width"]) == MIN_BOX_WIDTH
    # Clamped means stopped: the box must not keep sliding after the pointer.
    assert round(after["x"]) == round(before["x"] + before["width"]) - MIN_BOX_WIDTH


def test_should_keep_a_left_edge_resize_after_a_reload(canvas):
    box = canvas.locator('[data-box="b1"]')
    before = box.bounding_box()
    resize(canvas, "b1", "left", -120)
    canvas.wait_for_timeout(400)  # the patch is fire-and-forget
    canvas.reload()
    canvas.wait_for_selector('[data-box="b1"]')
    after = box.bounding_box()
    assert round(after["width"] - before["width"]) == 120
    assert round(after["x"] - before["x"]) == -120


# --- minimising a box -----------------------------------------------------


def test_should_fold_the_body_away_when_a_box_is_minimised(canvas):
    canvas.click('[data-box="b1"] [data-collapse]')
    expect(canvas.locator('[data-box="b1"] [data-body]')).to_be_hidden()
    # The header is all that is left to grab, to read, and to click again.
    expect(canvas.locator('[data-box="b1"] .box__head')).to_be_visible()


def test_should_mark_a_minimised_box_as_collapsed(canvas):
    canvas.click('[data-box="b1"] [data-collapse]')
    expect(canvas.locator('[data-box="b1"]')).to_have_attribute("data-collapsed", "1")


def test_should_unfold_the_body_when_a_box_is_expanded_again(canvas):
    collapse = canvas.locator('[data-box="b1"] [data-collapse]')
    collapse.click()
    collapse.click()
    expect(canvas.locator('[data-box="b1"] [data-body]')).to_be_visible()


def test_should_track_the_folded_state_on_the_collapse_button(canvas):
    collapse = canvas.locator('[data-box="b1"] [data-collapse]')
    expect(collapse).to_have_attribute("aria-expanded", "true")
    collapse.click()
    expect(collapse).to_have_attribute("aria-expanded", "false")


def test_should_put_the_minimise_button_last_in_the_header(canvas):
    """The fold is the outermost control: it is what a reader reaches for most."""
    answer_from_root(canvas)
    last = canvas.evaluate(
        """() => {
      const buttons = document.querySelectorAll('[data-box="b2"] .box__head button');
      return buttons[buttons.length - 1].dataset.collapse !== undefined;
    }"""
    )
    assert last


def test_should_draw_the_minimise_button_without_a_border(canvas):
    style = canvas.evaluate(
        """() => {
      const s = getComputedStyle(document.querySelector('[data-box="b1"] [data-collapse]'));
      return { border: s.borderTopWidth, background: s.backgroundColor };
    }"""
    )
    assert style["border"] == "0px"
    assert style["background"] == "rgba(0, 0, 0, 0)"


def test_should_say_what_the_collapse_button_will_do_next(canvas):
    collapse = canvas.locator('[data-box="b1"] [data-collapse]')
    expect(collapse).to_have_attribute("aria-label", "Minimise")
    collapse.click()
    expect(collapse).to_have_attribute("aria-label", "Expand")


def test_should_keep_a_box_minimised_after_a_reload(canvas):
    canvas.click('[data-box="b1"] [data-collapse]')
    canvas.wait_for_timeout(400)  # the collapsed flag is patched in the background
    canvas.reload()
    canvas.wait_for_selector('[data-box="b1"]')
    expect(canvas.locator('[data-box="b1"] [data-body]')).to_be_hidden()


def test_should_still_draw_the_edge_out_of_a_minimised_box(canvas):
    answer_from_root(canvas)
    canvas.click('[data-box="b1"] [data-collapse]')
    expect(canvas.locator('[data-edges] [data-edge="b2"]')).to_have_count(1)


def test_should_start_that_edge_at_the_box_not_at_the_canvas_origin(canvas):
    """Folding hides the mark the edge used to leave from, not the answer it leads to."""
    answer_from_root(canvas)
    canvas.click('[data-box="b1"] [data-collapse]')
    canvas.wait_for_selector('[data-edges] [data-edge="b2"]')
    canvas.wait_for_timeout(200)  # geometry is re-measured on the next frame
    rect = box_rect(canvas, "b1")
    start = edge_start(canvas, "b2")
    assert abs(start["x"] - (rect["x"] + rect["w"])) <= 60
    assert rect["y"] - 20 <= start["y"] <= rect["y"] + rect["h"] + 20


def test_should_not_count_find_matches_inside_a_minimised_box(canvas):
    canvas.click('[data-box="b1"] [data-collapse]')
    canvas.fill("[data-find]", "residual")
    expect(canvas.locator("[data-find-count]")).to_have_text("0/0")


def test_should_drop_the_find_count_when_a_box_is_folded_mid_search(canvas):
    """Folding while a search is live: the matches inside it stop being matches."""
    canvas.fill("[data-find]", "residual")
    expect(canvas.locator("[data-find-count]")).not_to_have_text("0/0")
    canvas.click('[data-box="b1"] [data-collapse]')
    expect(canvas.locator("[data-find-count]")).to_have_text("0/0")


def test_should_show_the_highlighted_passage_when_a_box_is_minimised(canvas):
    answer_from_root(canvas)
    jump_to(canvas, "b2")  # b2 opens beyond the right edge of the viewport
    canvas.click('[data-box="b2"] [data-collapse]')
    expect(canvas.locator('[data-box="b2"] [data-quote]')).to_be_visible()


def test_should_keep_the_quote_above_the_question_when_minimised(canvas):
    """DOM order is proved elsewhere; folded, the margins decide where each one sits."""
    answer_from_root(canvas)
    jump_to(canvas, "b2")
    canvas.click('[data-box="b2"] [data-collapse]')
    quote = canvas.locator('[data-box="b2"] [data-quote]').bounding_box()
    question = canvas.locator('[data-box="b2"] [data-question]').bounding_box()
    assert quote["y"] + quote["height"] <= question["y"]


# QUOTE never fills one line at any width down to MIN_BOX_WIDTH, so clipping needs a
# longer passage. The newline is the document's own line wrap, which find_offsets
# matches verbatim.
LONG_QUOTE = (
    "Self-attention layers are faster than recurrent layers when the sequence length is\n"
    "smaller than the representation dimensionality, which is"
)


def test_should_clip_a_long_minimised_quote_to_one_line(canvas):
    answer_from_root(canvas, "Why self-attention?", needle=LONG_QUOTE)
    jump_to(canvas, "b2")
    canvas.click('[data-box="b2"] [data-collapse]')
    quote = canvas.locator('[data-box="b2"] [data-quote]')
    assert quote.evaluate(ONE_LINE_TALL)


def test_should_not_quote_anything_on_a_minimised_document_box(canvas):
    canvas.click('[data-box="b1"] [data-collapse]')
    expect(canvas.locator('[data-box="b1"] [data-quote]')).to_have_count(0)


# --- folding every box at once ---------------------------------------------


def test_should_fold_every_box_including_the_document(canvas):
    answer_from_root(canvas)
    canvas.click("[data-fold-all]")
    expect(canvas.locator("[data-box]")).to_have_count(2)
    expect(canvas.locator('[data-box]:not([data-collapsed="1"])')).to_have_count(0)


def test_should_expand_every_box_again(canvas):
    answer_from_root(canvas)
    canvas.click("[data-fold-all]")
    canvas.click("[data-unfold-all]")
    expect(canvas.locator("[data-box][data-collapsed]")).to_have_count(0)
    expect(canvas.locator('[data-box="b2"] [data-body]')).to_be_visible()


def test_should_track_a_bulk_fold_on_every_box_button(canvas):
    """The header buttons are the way back out, so each one has to know it is folded."""
    answer_from_root(canvas)
    for button, expanded in (("[data-fold-all]", "false"), ("[data-unfold-all]", "true")):
        canvas.click(button)
        for box in ("b1", "b2"):
            expect(canvas.locator(f'[data-box="{box}"] [data-collapse]')).to_have_attribute(
                "aria-expanded", expanded
            )


def test_should_drop_the_find_count_when_every_box_is_folded(canvas):
    canvas.fill("[data-find]", "residual")
    expect(canvas.locator("[data-find-count]")).not_to_have_text("0/0")
    canvas.click("[data-fold-all]")
    expect(canvas.locator("[data-find-count]")).to_have_text("0/0")


def test_should_keep_a_bulk_fold_after_a_reload(canvas, server):
    answer_from_root(canvas)
    canvas.click("[data-fold-all]")
    canvas.wait_for_timeout(400)  # every fold rides in one background patch

    # The server's own copy, so a patch that carried only one box cannot pass.
    view = canvas.request.get(f"{server}/api/canvases/{canvas_id_of(canvas)}").json()
    assert all(box["collapsed"] for box in view["boxes"]), view["boxes"]

    canvas.reload()
    canvas.wait_for_selector('[data-box="b2"]')
    expect(canvas.locator('[data-box="b1"] [data-body]')).to_be_hidden()
    expect(canvas.locator('[data-box="b2"] [data-body]')).to_be_hidden()


def test_should_close_the_editor_when_every_box_is_folded(canvas):
    """There is nothing to edit inside a folded box, the same as the per-box fold."""
    open_editor(canvas, "b1")
    canvas.click("[data-fold-all]")
    expect(canvas.locator(CONTENT.format(box="b1"))).to_have_count(0)
    expect(canvas.locator('[data-box="b1"]')).to_have_attribute("data-collapsed", "1")


# --- the quote and the question on an answer ------------------------------


def test_should_quote_the_highlighted_passage_on_the_answer_box(canvas):
    answer_from_root(canvas)
    expect(canvas.locator('[data-box="b2"] blockquote[data-quote]')).to_have_text(QUOTE)


def test_should_put_the_quote_above_the_question(canvas):
    """You read what was asked about, then what was asked."""
    answer_from_root(canvas)
    assert canvas.evaluate(QUOTE_BEFORE_QUESTION, "b2")


def test_should_not_quote_anything_on_the_root_box(canvas):
    answer_from_root(canvas)
    expect(canvas.locator('[data-box="b1"] [data-quote]')).to_have_count(0)


# --- jumping to the answer ------------------------------------------------


def test_should_frame_the_answer_when_its_highlight_is_clicked(canvas):
    answer_from_root(canvas)
    jump_to(canvas, "b2")
    seen = canvas.locator('[data-box="b2"]').bounding_box()
    cx, cy = view_centre(canvas)
    # Generous: the camera aims a little high so a long answer reads from its top.
    assert abs(seen["x"] + seen["width"] / 2 - cx) <= 300
    assert abs(seen["y"] + seen["height"] / 2 - cy) <= 300


def test_should_keep_the_answer_header_clear_of_the_chrome_bar(canvas):
    answer_from_root(canvas)
    jump_to(canvas, "b2")
    assert canvas.locator('[data-box="b2"]').bounding_box()["y"] >= CHROME_HEIGHT


def test_should_flash_the_answer_box_when_its_highlight_is_clicked(canvas):
    answer_from_root(canvas)
    canvas.locator('[data-box="b1"] mark[data-anchor]').first.click()
    expect(canvas.locator('[data-box="b2"]')).to_have_attribute("data-flash", "1")


def test_should_draw_the_ring_for_a_five_second_css_duration(canvas):
    """The CSS duration, not just the attribute: a JS-only change would not be seen."""
    answer_from_root(canvas)
    canvas.locator('[data-box="b1"] mark[data-anchor]').first.click()
    assert canvas.evaluate(FLASH_DURATION, "b2") == 5000


def test_should_take_the_ring_down_on_its_own_after_five_seconds(canvas):
    answer_from_root(canvas)
    box = canvas.locator('[data-box="b2"]')
    canvas.locator('[data-box="b1"] mark[data-anchor]').first.click()
    canvas.wait_for_timeout(1500)  # well past the 900ms the ring used to last
    expect(box).to_have_attribute("data-flash", "1", timeout=1000)
    # And it does come down. Polling costs the ring's remaining life and no more, but
    # the wait has to clear 5s: that is also playwright's default, and the two would race.
    expect(box).not_to_have_attribute("data-flash", "1", timeout=8000)


def test_should_start_the_ring_over_when_the_answer_is_reached_again(canvas):
    """Clearing and re-setting the attribute in one task does not restart the animation."""
    answer_from_root(canvas)
    canvas.locator('[data-box="b1"] mark[data-anchor]').first.click()
    # Waiting on the camera rather than on the clock, so the second visit lands well
    # inside the ring rather than after it. The highlight is off screen by then; the
    # edge it drew is not, and leads to the same box.
    wait_for_camera(canvas)
    x, y = canvas.evaluate(EDGE_MIDPOINT, "b2")
    canvas.mouse.click(*to_client(canvas, x, y))
    assert canvas.evaluate(FLASH_ELAPSED, "b2") < 200


def test_should_hold_a_still_ring_when_motion_is_reduced(canvas):
    """No animation to end, so the timer in app.js is the only thing taking it down."""
    canvas.emulate_media(reduced_motion="reduce")
    answer_from_root(canvas)
    canvas.locator('[data-box="b1"] mark[data-anchor]').first.click()
    expect(canvas.locator('[data-box="b2"]')).to_have_attribute("data-flash", "1")
    assert canvas.evaluate(FLASH_ELAPSED, "b2") is None


def test_should_frame_and_flash_the_answer_when_its_edge_is_clicked(canvas):
    answer_from_root(canvas)
    x, y = canvas.evaluate(EDGE_MIDPOINT, "b2")
    canvas.mouse.click(*to_client(canvas, x, y))
    expect(canvas.locator('[data-box="b2"]')).to_have_attribute("data-flash", "1")
    canvas.wait_for_timeout(700)
    seen = canvas.locator('[data-box="b2"]').bounding_box()
    cx, _ = view_centre(canvas)
    assert abs(seen["x"] + seen["width"] / 2 - cx) <= 300


def test_should_leave_the_camera_alone_when_a_click_lands_on_the_bare_desk(canvas):
    """Making edges clickable must not turn an empty click into a pan."""
    answer_from_root(canvas)
    before = transform_of(canvas)
    height = canvas.evaluate("() => window.innerHeight")
    canvas.mouse.click(10, height - 10)
    canvas.wait_for_timeout(600)
    assert transform_of(canvas) == before


# --- getting back to the parent -------------------------------------------


def test_should_offer_a_way_back_to_the_document_from_a_first_answer(canvas):
    answer_from_root(canvas)
    expect(canvas.locator('[data-box="b2"] [data-goparent]')).to_have_text("Back to the document")


def test_should_name_the_parent_depth_on_a_deeper_answer(canvas):
    answer_from_root(canvas)
    ask(canvas, "b2", "carries the input", "Why add it back?")
    canvas.wait_for_selector('[data-box="b3"][data-status="done"]', timeout=20000)
    expect(canvas.locator('[data-box="b3"] [data-goparent]')).to_have_text("Back to depth 2")


def test_should_not_offer_a_way_back_from_the_root_box(canvas):
    expect(canvas.locator('[data-box="b1"] [data-goparent]')).to_have_count(0)


def test_should_go_back_to_the_passage_the_answer_came_from(canvas):
    answer_from_root(canvas)
    jump_to(canvas, "b2")  # walk away from the document first
    canvas.click('[data-box="b2"] [data-goparent]')
    canvas.wait_for_timeout(700)
    mark = canvas.locator('[data-box="b1"] mark[data-anchor]').first.bounding_box()
    _, cy = view_centre(canvas)
    assert abs(mark["y"] + mark["height"] / 2 - cy) <= 250


def test_should_flash_the_passage_it_goes_back_to(canvas):
    answer_from_root(canvas)
    jump_to(canvas, "b2")
    canvas.click('[data-box="b2"] [data-goparent]')
    expect(canvas.locator('[data-box="b1"] mark[data-anchor]').first).to_have_attribute(
        "data-flash", "1"
    )


def test_should_hide_the_way_back_while_the_box_is_being_edited(canvas):
    answer_from_root(canvas)
    jump_to(canvas, "b2")
    open_editor(canvas, "b2")
    expect(canvas.locator('[data-box="b2"] [data-goparent]')).to_be_hidden()


# --- a new answer inherits its parent's width -----------------------------


def test_should_open_an_answer_at_the_width_of_the_box_it_came_from(canvas):
    answer_from_root(canvas)
    width = canvas.locator('[data-box="b2"]').bounding_box()["width"]
    assert round(width) == ROOT_BOX_WIDTH


def test_should_inherit_the_resized_width_of_a_parent_answer(canvas):
    answer_from_root(canvas)
    jump_to(canvas, "b2")  # brings the handle on screen with the scale still at 1
    resize(canvas, "b2", "right", 120)
    ask(canvas, "b2", "carries the input", "Why add it back?")
    canvas.wait_for_selector('[data-box="b3"]')
    width = canvas.locator('[data-box="b3"]').bounding_box()["width"]
    assert round(width) == ROOT_BOX_WIDTH + 120


def test_should_not_overlap_two_answers_asked_off_the_same_box(canvas):
    """Now >= rather than exactly BOX_GAP: under the new rule each child keeps its own
    passage, so two answers this close on the parent are no longer packed to the bare
    minimum the way the old, height-guessing placement() left them. The exact-gap case
    is covered separately, by the [[fake:long]] collision tests below."""
    answer_from_root(canvas)
    ask(canvas, "b1", "layer normalisation", "What does it normalise?")
    canvas.wait_for_selector('[data-box="b3"][data-status="done"]', timeout=20000)
    b2, b3 = box_rect(canvas, "b2"), box_rect(canvas, "b3")
    assert not overlap(b2, b3)
    # BOX_GAP is a floor, not the target now: "not overlapping" alone would also pass
    # on spacing far wider than the minimum, so the floor is still worth asserting.
    assert gap_between(b2, b3) >= BOX_GAP - 1, f"b2={b2} b3={b3}"


# --- restack: a fixed gap between boxes stacked under the same parent -----

# Same phrase in every [[fake:long]] answer, regardless of the question asked, so a
# test asking off an answer (rather than off the root) always has something to select.
LONG_MARKER = "[[fake:long]]"
LONG_ANSWER_QUOTE = "plays a specific role in the transformer architecture"


def ask_long(page, parent: str, needle: str, question: str, box: str) -> None:
    """Ask for a tall answer off `parent`, and wait for `box` to finish."""
    ask(page, parent, needle, f"{question} {LONG_MARKER}")
    page.wait_for_selector(f'[data-box="{box}"][data-status="done"]', timeout=30000)


def three_long_answers(page) -> None:
    """b2, b3 and b4 under the root, each tall enough to overlap the next."""
    ask_long(page, "b1", "an encoder and a decoder", "Explain encoders", "b2")
    ask_long(page, "b1", QUOTE, "Explain residual connections", "b3")
    ask_long(page, "b1", "layer normalisation", "Explain layer normalisation", "b4")


def test_should_stack_two_answers_a_fixed_gap_apart_once_a_tall_one_lands(canvas):
    # Fired back to back, so b3 is placed while b2 is still a pending stub — the
    # exact case placement()'s height guess gets wrong once the real content lands.
    ask(canvas, "b1", QUOTE, f"Explain residual connections in depth {LONG_MARKER}")
    ask(canvas, "b1", "layer normalisation", f"Explain layer normalisation in depth {LONG_MARKER}")
    canvas.wait_for_selector('[data-box="b2"][data-status="done"]', timeout=30000)
    canvas.wait_for_selector('[data-box="b3"][data-status="done"]', timeout=30000)

    b2, b3 = box_rect(canvas, "b2"), box_rect(canvas, "b3")
    assert gap_between(b2, b3) == pytest.approx(BOX_GAP, abs=1), f"b2={b2} b3={b3}"


def test_should_keep_the_stacking_after_a_reload(canvas, server):
    ask(canvas, "b1", QUOTE, f"Explain residual connections in depth {LONG_MARKER}")
    ask(canvas, "b1", "layer normalisation", f"Explain layer normalisation in depth {LONG_MARKER}")
    canvas.wait_for_selector('[data-box="b2"][data-status="done"]', timeout=30000)
    canvas.wait_for_selector('[data-box="b3"][data-status="done"]', timeout=30000)
    canvas.reload()
    canvas.wait_for_selector('[data-box="b3"][data-status="done"]')
    # Read before settling on purpose. The open-time pass would re-derive the gap in the
    # browser and hide a PATCH that never landed, so this reads the first paint.
    b2, b3 = box_rect(canvas, "b2"), box_rect(canvas, "b3")
    assert gap_between(b2, b3) == pytest.approx(BOX_GAP, abs=1), f"b2={b2} b3={b3}"

    # And again from the server's own copy, which no browser pass can put right.
    view = canvas.request.get(f"{server}/api/canvases/{canvas_id_of(canvas)}").json()
    stored = {b["id"]: b["y"] for b in view["boxes"]}
    assert stored["b3"] - (stored["b2"] + b2["h"]) == pytest.approx(BOX_GAP, abs=1), stored


def test_should_stack_overlapping_boxes_when_the_canvas_is_opened(
    page, server, fresh_home, monkeypatch
):
    """Two same-parent boxes written straight to disk, overlapping, bypassing
    placement() entirely — this exercises the open-time restack pass on its own,
    with no ask and no drag involved, the way fixtures/big_canvas.py seeds its canvas."""
    from research_canvas import storage

    monkeypatch.setattr(storage, "CANVAS_ROOT", fresh_home)
    doc = "# A Document\n\nA paragraph long enough to pass the import minimum for a canvas.\n"
    canvas_obj = storage.create_canvas(doc, web_search=False)
    for box_id, question, y in (("b2", "First?", 0.0), ("b3", "Second?", 60.0)):
        box = storage.add_answer(
            canvas_obj, parent_id=canvas_obj.root_id, question=question, x=900.0, y=y
        )
        box.status = "done"
        storage.write_body(canvas_obj.id, box.id, f"The answer for {box_id}, short and plain.\n")
    storage.save(canvas_obj)

    page.goto(f"{server}/?c={canvas_obj.id}")
    page.wait_for_selector('[data-box="b3"]')
    settled(page)
    b2_rect, b3_rect = box_rect(page, "b2"), box_rect(page, "b3")
    # b3 was seeded at y=60, so the fixture started overlapped if b2 renders taller than
    # that. Read after the pass, which moves tops and never changes a height.
    assert b2_rect["h"] > 60, f"fixture did not start overlapped: b2={b2_rect}"
    assert gap_between(b2_rect, b3_rect) == pytest.approx(BOX_GAP, abs=1)


def test_should_close_the_gap_when_a_box_above_is_minimised(canvas):
    """Now >= rather than exactly BOX_GAP for both gaps: three_long_answers seats each
    box beside its own passage first, and folding b3 can leave either gap wider than
    the bare minimum. The exact-gap case is covered separately, by the [[fake:long]]
    collision tests below."""
    three_long_answers(canvas)

    settled(canvas)  # record where the stack really lands, not a mid-pass y
    before_b4_y = box_rect(canvas, "b4")["y"]
    canvas.click('[data-box="b3"] [data-collapse]')
    settled(canvas)

    b2, b3, b4 = box_rect(canvas, "b2"), box_rect(canvas, "b3"), box_rect(canvas, "b4")
    assert gap_between(b2, b3) >= BOX_GAP - 1, f"b2={b2} b3={b3}"
    assert gap_between(b3, b4) >= BOX_GAP - 1, f"b3={b3} b4={b4}"
    assert b4["y"] < before_b4_y


def test_should_reopen_the_gap_when_a_minimised_box_is_expanded(canvas):
    three_long_answers(canvas)

    settled(canvas)  # record where the stack really lands, not a mid-pass y
    settled_b4_y = box_rect(canvas, "b4")["y"]
    collapse = canvas.locator('[data-box="b3"] [data-collapse]')
    collapse.click()
    settled(canvas)
    collapse.click()
    settled(canvas)

    b2, b3, b4 = box_rect(canvas, "b2"), box_rect(canvas, "b3"), box_rect(canvas, "b4")
    assert gap_between(b2, b3) == pytest.approx(BOX_GAP, abs=1)
    assert gap_between(b3, b4) == pytest.approx(BOX_GAP, abs=1)
    assert b4["y"] == pytest.approx(settled_b4_y, abs=1)


def test_should_close_every_gap_when_every_box_is_folded(canvas):
    three_long_answers(canvas)

    settled(canvas)  # record where the stack really lands, not a mid-pass y
    before_b4_y = box_rect(canvas, "b4")["y"]
    canvas.click("[data-fold-all]")
    settled(canvas)

    b2, b3, b4 = box_rect(canvas, "b2"), box_rect(canvas, "b3"), box_rect(canvas, "b4")
    assert gap_between(b2, b3) == pytest.approx(BOX_GAP, abs=1)
    assert gap_between(b3, b4) == pytest.approx(BOX_GAP, abs=1)
    assert b4["y"] < before_b4_y


def test_should_still_stack_when_a_bulk_fold_closes_the_editor(canvas):
    """`restack` refuses to stack while an editor is open, so the close has to land
    before the queued pass reads it, not after."""
    three_long_answers(canvas)

    settled(canvas)
    open_editor(canvas, "b3")
    canvas.click("[data-fold-all]")
    settled(canvas)

    b2, b3, b4 = box_rect(canvas, "b2"), box_rect(canvas, "b3"), box_rect(canvas, "b4")
    assert gap_between(b2, b3) == pytest.approx(BOX_GAP, abs=1)
    assert gap_between(b3, b4) == pytest.approx(BOX_GAP, abs=1)


def test_should_leave_a_box_at_another_depth_alone(canvas):
    """A child is never stacked with its own parent, even if a drag makes them overlap.
    Still holds under the new rule too, but for a different reason now: the drag is a
    vertical one, so it pins b3, and a pinned box keeps exactly the y it was dropped
    at through every later settle pass."""
    answer_from_root(canvas)  # b2, depth 1
    ask(canvas, "b2", "carries the input", "Why add it back?")
    canvas.wait_for_selector('[data-box="b3"][data-status="done"]', timeout=20000)

    zoom_to_fit(canvas)  # both boxes on screen before the drag

    b2, b3 = box_rect(canvas, "b2"), box_rect(canvas, "b3")
    drag_header_by(canvas, "b3", b2["x"] - b3["x"], b2["y"] - b3["y"])

    dropped_b2, dropped_b3 = box_rect(canvas, "b2"), box_rect(canvas, "b3")
    assert overlap(dropped_b2, dropped_b3), (
        f"drag did not land on the parent: {dropped_b2} {dropped_b3}"
    )

    settled(canvas)
    settled_b2, settled_b3 = box_rect(canvas, "b2"), box_rect(canvas, "b3")
    assert settled_b2["y"] == pytest.approx(dropped_b2["y"], abs=1)
    assert settled_b3["y"] == pytest.approx(dropped_b3["y"], abs=1)


def test_should_push_an_unpinned_group_clear_of_the_one_a_drag_just_pinned(canvas):
    """Two depth-2 boxes with different parents can land in the same column (both
    parents are the same width, so both children sit one COLUMN_GAP further right).
    This used to be test_should_not_move_a_sibling_under_a_different_parent, and its
    premise — that dragging one onto the other moves nothing — is gone: dragging b5
    onto b4 now pins b5 exactly where it lands, and a pinned group is never shifted,
    so the settle pass owes a clear place only to b4's group. b4 is free to move; b5,
    holding the pin, is not."""
    ask(canvas, "b1", QUOTE, "What is a residual connection?")
    canvas.wait_for_selector('[data-box="b2"][data-status="done"]', timeout=20000)
    ask(canvas, "b1", "layer normalisation", "What does it normalise?")
    canvas.wait_for_selector('[data-box="b3"][data-status="done"]', timeout=20000)
    ask(canvas, "b2", "carries the input", "Why add it back?")
    canvas.wait_for_selector('[data-box="b4"][data-status="done"]', timeout=20000)
    ask(canvas, "b3", "carries the input", "Why write it that way?")
    canvas.wait_for_selector('[data-box="b5"][data-status="done"]', timeout=20000)

    zoom_to_fit(canvas)  # every box on screen before the drag

    b4, b5 = box_rect(canvas, "b4"), box_rect(canvas, "b5")
    assert b4["x"] == pytest.approx(b5["x"], abs=1), f"not in the same column: b4={b4} b5={b5}"

    drag_header_by(canvas, "b5", b4["x"] - b5["x"], b4["y"] - b5["y"])
    dropped_b4, dropped_b5 = box_rect(canvas, "b4"), box_rect(canvas, "b5")
    assert overlap(dropped_b4, dropped_b5), (
        f"drag did not land on the sibling: {dropped_b4} {dropped_b5}"
    )

    settled(canvas)
    settled_b4, settled_b5 = box_rect(canvas, "b4"), box_rect(canvas, "b5")
    # The pin holds b5 exactly where it was dropped.
    assert settled_b5["y"] == pytest.approx(dropped_b5["y"], abs=1), settled_b5
    # b4's group is the one free to move, and it must move clear rather than overlap.
    assert not overlap(settled_b4, settled_b5), f"b4={settled_b4} b5={settled_b5}"


def test_should_restack_when_a_box_is_dragged_onto_a_sibling(canvas):
    answer_from_root(canvas)  # b2
    ask(canvas, "b1", "layer normalisation", "What does it normalise?")
    canvas.wait_for_selector('[data-box="b3"][data-status="done"]', timeout=20000)

    b2, b3 = box_rect(canvas, "b2"), box_rect(canvas, "b3")
    lower, lower_rect, upper_rect = ("b3", b3, b2) if b3["y"] > b2["y"] else ("b2", b2, b3)
    drag_header_by(canvas, lower, 0, upper_rect["y"] - lower_rect["y"])
    settled(canvas)

    assert gap_between(box_rect(canvas, "b2"), box_rect(canvas, "b3")) == pytest.approx(
        BOX_GAP, abs=1
    )


STACKED = ("b2", "b3", "b4")


def test_should_move_nothing_on_a_second_refresh(canvas):
    ask_long(canvas, "b1", QUOTE, "Explain residual connections", "b2")
    ask_long(canvas, "b1", "layer normalisation", "Explain layer normalisation", "b3")
    ask_long(canvas, "b2", LONG_ANSWER_QUOTE, "Go deeper", "b4")

    canvas.reload()
    canvas.wait_for_selector('[data-box="b4"][data-status="done"]')
    settled(canvas)
    first = {box: box_rect(canvas, box) for box in STACKED}

    canvas.reload()
    canvas.wait_for_selector('[data-box="b4"][data-status="done"]')
    settled(canvas)
    second = {box: box_rect(canvas, box) for box in STACKED}

    for box in STACKED:
        assert second[box]["y"] == pytest.approx(first[box]["y"], abs=1), box


# --- restack: each child beside its own passage, and a drag that pins it -------

# ANCHOR_LEAD is imported inside the two tests that need it, not at module scope: a
# module-level import fails collection for the whole file the moment the constant is
# missing or renamed, which would take down every other test in it too. Everywhere
# else, `edge_start` already carries the anchor's position, so nothing needs it.


def test_should_seat_an_answer_anchor_lead_above_its_passage_underline(canvas):
    """`edge_start` reads the same point the edge itself leaves from — the mark's
    underline, already adjusted for the hairline the edge is drawn from the middle
    of — so subtracting ANCHOR_LEAD from it is the one exact check available; the
    mark's own bounding box is not, because it fragments across elements."""
    from research_canvas.config import ANCHOR_LEAD

    answer_from_root(canvas)  # b2, the only child, nothing above it to push it down
    settled(canvas)

    anchor = edge_start(canvas, "b2")
    box = box_rect(canvas, "b2")
    assert box["y"] == pytest.approx(anchor["y"] - ANCHOR_LEAD, abs=1), f"box={box} anchor={anchor}"


def test_should_space_siblings_further_apart_when_their_passages_sit_far_apart(canvas):
    """Each child keeps its own passage now, rather than being packed to the minimum
    the way the old, height-guessing restack left them: two passages far apart on the
    parent land the children further apart than BOX_GAP, not right at it."""
    ask(canvas, "b1", "an encoder and a decoder", "Explain encoders")
    canvas.wait_for_selector('[data-box="b2"][data-status="done"]', timeout=20000)
    ask(canvas, "b1", "layer normalisation", "What does it normalise?")
    canvas.wait_for_selector('[data-box="b3"][data-status="done"]', timeout=20000)
    settled(canvas)

    b2, b3 = box_rect(canvas, "b2"), box_rect(canvas, "b3")
    assert gap_between(b2, b3) > BOX_GAP + 1, f"b2={b2} b3={b3}"


def test_should_land_exactly_a_box_gap_apart_when_two_tall_answers_would_collide(canvas):
    """Even the two most distant passages in this document collide once both answers
    are long enough to tower over the space between their anchors; the settle pass
    still holds them to exactly BOX_GAP, the same fixed minimum the old height-blind
    stack produced, just reached by each box's own anchor now rather than by holding
    whichever box happened to be on top."""
    ask_long(canvas, "b1", "an encoder and a decoder", "Explain encoders", "b2")
    ask_long(canvas, "b1", "layer normalisation", "Explain layer normalisation", "b3")
    settled(canvas)

    b2, b3 = box_rect(canvas, "b2"), box_rect(canvas, "b3")
    assert gap_between(b2, b3) == pytest.approx(BOX_GAP, abs=1), f"b2={b2} b3={b3}"


def seat_of(page, box: str) -> float:
    """Where a box would sit if nothing else were in the column: ANCHOR_LEAD above the
    underline of its own passage."""
    from research_canvas.config import ANCHOR_LEAD

    return edge_start(page, box)["y"] - ANCHOR_LEAD


def test_should_balance_a_colliding_pair_evenly_around_their_passages(canvas):
    """Two boxes that collide are rigid: the gap between them is fixed, so all the
    layout chooses is where the pair as a whole sits. Hanging it off the upper box's
    passage leaves every pixel of the crowding to the lower box and wastes the space
    above the upper one. Split evenly, each box is the same distance from its own
    passage, one above and one below, which is the least either can be.
    """
    answer_from_root(canvas)  # b2, off QUOTE
    ask(canvas, "b1", "layer normalisation", "What does it normalise?")
    canvas.wait_for_selector('[data-box="b3"][data-status="done"]', timeout=20000)
    settled(canvas)

    b2, b3 = box_rect(canvas, "b2"), box_rect(canvas, "b3")
    assert gap_between(b2, b3) == pytest.approx(BOX_GAP, abs=1), f"b2={b2} b3={b3}"
    above = b2["y"] - seat_of(canvas, "b2")
    below = b3["y"] - seat_of(canvas, "b3")
    assert above < -1, f"b2 did not rise above its own passage: {above:.1f}"
    assert below > 1, f"b3 did not stay below its own passage: {below:.1f}"
    assert above == pytest.approx(-below, abs=1), f"above={above:.1f} below={below:.1f}"


def test_should_leave_siblings_that_do_not_collide_at_their_own_passages(canvas):
    """Balancing is for boxes that touch. Two short answers off passages far enough
    apart never touch, so neither has anything to share and both stay exactly on their
    own passage rather than drifting towards each other.
    """
    ask(canvas, "b1", "an encoder and a decoder", "Explain encoders")
    canvas.wait_for_selector('[data-box="b2"][data-status="done"]', timeout=20000)
    ask(canvas, "b1", "layer normalisation", "What does it normalise?")
    canvas.wait_for_selector('[data-box="b3"][data-status="done"]', timeout=20000)
    settled(canvas)

    for box in ("b2", "b3"):
        rect = box_rect(canvas, box)
        assert rect["y"] == pytest.approx(seat_of(canvas, box), abs=1), f"{box}={rect}"


def test_should_not_lift_a_family_above_the_top_of_its_parent(canvas):
    """A family taller than the passages it hangs off wants to climb, and left alone it
    would climb clean off the top of the document it came from. It stops at the parent's
    own top, and the boxes below it stay in order and clear of each other.
    """
    three_long_answers(canvas)
    settled(canvas)

    root = box_rect(canvas, "b1")
    boxes = [box_rect(canvas, b) for b in ("b2", "b3", "b4")]
    assert boxes[0]["y"] >= root["y"] - 1, f"root={root} b2={boxes[0]}"
    for upper, lower in pairwise(boxes):
        assert gap_between(upper, lower) >= BOX_GAP - 1, f"upper={upper} lower={lower}"
        assert not overlap(upper, lower), f"upper={upper} lower={lower}"


def test_should_stop_a_family_at_the_top_of_a_short_parent(canvas):
    """The floor matters most where the parent is small. Two long answers off two
    passages a line apart inside a short answer box want to climb hundreds of pixels to
    balance, and there is no document underneath them to make that look reasonable.
    They stop dead on their parent's own top edge.
    """
    answer_from_root(canvas)  # b2, a short answer, the parent here
    ask_long(canvas, "b2", "carries the input", "Why add it back?", "b3")
    ask_long(canvas, "b2", "adds it back", "And then what?", "b4")
    settled(canvas)

    parent = box_rect(canvas, "b2")
    b3, b4 = box_rect(canvas, "b3"), box_rect(canvas, "b4")
    assert b3["y"] == pytest.approx(parent["y"], abs=1), f"parent={parent} b3={b3}"
    assert gap_between(b3, b4) == pytest.approx(BOX_GAP, abs=1), f"b3={b3} b4={b4}"


def test_should_order_siblings_by_passage_not_by_when_they_were_asked(canvas):
    """A question asked from a passage higher in the parent opens its box above one
    asked earlier from a passage lower down: order follows the passage, not the ask."""
    lower_start, _ = find_offsets(canvas, "b1", "layer normalisation")
    higher_start, _ = find_offsets(canvas, "b1", QUOTE)
    assert higher_start < lower_start  # sanity: QUOTE really does sit above in the doc

    ask(canvas, "b1", "layer normalisation", "What does it normalise?")
    canvas.wait_for_selector('[data-box="b2"][data-status="done"]', timeout=20000)
    ask(canvas, "b1", QUOTE, "What is a residual connection?")
    canvas.wait_for_selector('[data-box="b3"][data-status="done"]', timeout=20000)
    settled(canvas)

    b2, b3 = box_rect(canvas, "b2"), box_rect(canvas, "b3")
    assert b3["y"] < b2["y"], f"b2={b2} b3={b3}"


def test_should_let_a_box_rise_back_to_its_own_passage_once_the_box_above_is_minimised(
    canvas,
):
    """The tall neighbour above no longer blocks it once folded: b3 has to return to
    its own anchor position exactly, not merely to somewhere higher than before."""
    from research_canvas.config import ANCHOR_LEAD

    ask_long(canvas, "b1", "an encoder and a decoder", "Explain encoders", "b2")
    ask(canvas, "b1", QUOTE, "What is a residual connection?")
    canvas.wait_for_selector('[data-box="b3"][data-status="done"]', timeout=20000)
    settled(canvas)

    canvas.click('[data-box="b2"] [data-collapse]')
    settled(canvas)

    anchor = edge_start(canvas, "b3")
    b3 = box_rect(canvas, "b3")
    assert b3["y"] == pytest.approx(anchor["y"] - ANCHOR_LEAD, abs=1), f"b3={b3} anchor={anchor}"


def test_should_carry_a_child_down_when_its_parent_is_dragged(canvas):
    """A child's seat is held as an offset from its parent's top, so moving the parent
    moves every child under it by the same amount."""
    answer_from_root(canvas)  # b2
    settled(canvas)
    child_before = box_rect(canvas, "b2")

    drag_header_by(canvas, "b1", 0, 150)
    settled(canvas)

    child_after = box_rect(canvas, "b2")
    assert child_after["y"] - child_before["y"] == pytest.approx(150, abs=1), (
        f"before={child_before} after={child_after}"
    )


def test_should_keep_two_families_in_one_column_clear_of_each_other(canvas):
    """b4 and b5 have different parents but land in the same column, because their
    parents (b2 and b3) are the same width. A tall b4 must not be left overlapping
    b5, even with no drag involved and the two families never mixed at any depth.
    Checked again after a reload, since the cross-family shift is the one part of
    the pass no other idempotence test in this file already covers."""
    ask(canvas, "b1", QUOTE, "What is a residual connection?")
    canvas.wait_for_selector('[data-box="b2"][data-status="done"]', timeout=20000)
    ask(canvas, "b1", "layer normalisation", "What does it normalise?")
    canvas.wait_for_selector('[data-box="b3"][data-status="done"]', timeout=20000)
    ask_long(canvas, "b2", "carries the input", "Go deeper", "b4")
    ask(canvas, "b3", "carries the input", "Why write it that way?")
    canvas.wait_for_selector('[data-box="b5"][data-status="done"]', timeout=20000)
    settled(canvas)

    b4, b5 = box_rect(canvas, "b4"), box_rect(canvas, "b5")
    assert b4["x"] == pytest.approx(b5["x"], abs=1), f"not in the same column: b4={b4} b5={b5}"
    assert not overlap(b4, b5), f"b4={b4} b5={b5}"

    canvas.reload()
    canvas.wait_for_selector('[data-box="b5"][data-status="done"]')
    settled(canvas)
    reloaded_b4, reloaded_b5 = box_rect(canvas, "b4"), box_rect(canvas, "b5")
    assert reloaded_b4["y"] == pytest.approx(b4["y"], abs=1), f"b4 moved on reload: {b4}"
    assert reloaded_b5["y"] == pytest.approx(b5["y"], abs=1), f"b5 moved on reload: {b5}"


def test_should_stay_where_it_was_dropped_after_a_vertical_drag(canvas):
    """Dropping a box at a height of your own choosing pins it there: the settle pass
    that runs right after the drag must not pull it back to its own passage."""
    answer_from_root(canvas)  # b2
    zoom_to_fit(canvas)  # b2 opens to the right of the root, past the edge of the window
    settled(canvas)
    before = box_rect(canvas, "b2")

    drag_header_by(canvas, "b2", 0, 300)
    settled(canvas)

    after = box_rect(canvas, "b2")
    assert after["y"] == pytest.approx(before["y"] + 300, abs=1), f"before={before} after={after}"


def test_should_keep_a_pin_after_a_reload(canvas, server):
    """The pin is stored on the box, not just held in memory: a reload must not let
    the settle pass move it back to its passage, and the server's own copy must say
    why, since that is the one place a browser-only pass could never put right."""
    answer_from_root(canvas)  # b2
    zoom_to_fit(canvas)  # b2 opens to the right of the root, past the edge of the window
    settled(canvas)
    before = box_rect(canvas, "b2")

    drag_header_by(canvas, "b2", 0, 300)
    canvas.wait_for_timeout(400)  # the pin is patched in the background
    canvas.reload()
    canvas.wait_for_selector('[data-box="b2"]')
    settled(canvas)

    after = box_rect(canvas, "b2")
    assert after["y"] == pytest.approx(before["y"] + 300, abs=1), f"before={before} after={after}"

    view = canvas.request.get(f"{server}/api/canvases/{canvas_id_of(canvas)}").json()
    stored = {b["id"]: b for b in view["boxes"]}
    assert stored["b2"].get("pinned") is True, stored


def test_should_only_show_the_unpin_button_on_a_pinned_box(canvas):
    """Mirrors test_should_track_the_folded_state_on_the_collapse_button: the button's
    visibility is what the box's own pinned flag drives, checked before and after."""
    answer_from_root(canvas)  # b2
    zoom_to_fit(canvas)  # b2 opens to the right of the root, past the edge of the window
    unpin = canvas.locator('[data-box="b2"] [data-unpin]')
    expect(unpin).to_be_hidden()

    drag_header_by(canvas, "b2", 0, 300)
    settled(canvas)

    expect(unpin).to_be_visible()


def test_should_return_a_box_to_its_passage_when_unpin_is_clicked(canvas):
    """Compared against the position the box held before the drag, not the
    ANCHOR_LEAD constant directly: whatever the layout's own maths puts there is
    what "back beside its passage" has to mean once the pin is gone."""
    answer_from_root(canvas)  # b2
    zoom_to_fit(canvas)  # b2 opens to the right of the root, past the edge of the window
    settled(canvas)
    natural = box_rect(canvas, "b2")

    # Up, not down: the minimap sits fixed in the bottom-right corner of the window,
    # and a downward drag from a zoomed-to-fit view can land the header behind it.
    drag_header_by(canvas, "b2", 0, -150)
    settled(canvas)
    assert box_rect(canvas, "b2")["y"] != pytest.approx(natural["y"], abs=1)  # sanity: it moved

    canvas.click('[data-box="b2"] [data-unpin]')
    settled(canvas)

    after = box_rect(canvas, "b2")
    assert after["y"] == pytest.approx(natural["y"], abs=1), f"natural={natural} after={after}"


def test_should_move_an_unpinned_sibling_clear_of_a_pinned_one(canvas):
    """Same parent this time, not a different one: dragging b2 onto b3's seat pins b2
    there, and b3 — never touched, never pinned — has to step aside rather than sit
    on top of it."""
    answer_from_root(canvas)  # b2
    ask(canvas, "b1", "layer normalisation", "What does it normalise?")
    canvas.wait_for_selector('[data-box="b3"][data-status="done"]', timeout=20000)
    zoom_to_fit(canvas)  # both children open to the right of the root, past the window edge
    settled(canvas)

    b2, b3 = box_rect(canvas, "b2"), box_rect(canvas, "b3")
    drag_header_by(canvas, "b2", 0, b3["y"] - b2["y"])
    dropped_b2, dropped_b3 = box_rect(canvas, "b2"), box_rect(canvas, "b3")
    assert overlap(dropped_b2, dropped_b3), (
        f"drag did not land on the sibling: {dropped_b2} {dropped_b3}"
    )

    settled(canvas)
    settled_b2, settled_b3 = box_rect(canvas, "b2"), box_rect(canvas, "b3")
    assert settled_b2["y"] == pytest.approx(dropped_b2["y"], abs=1), settled_b2
    assert not overlap(settled_b2, settled_b3), f"b2={settled_b2} b3={settled_b3}"


def test_should_clear_an_unpinned_box_of_a_pin_that_sits_out_of_passage_order(canvas):
    """Pins do not have to agree with reading order. Drag the third answer up onto the
    first one's seat and pin the second where it stands, and the pinned tops no longer
    descend down the column. The box still free has to clear every pin around it, not
    only the one next to it in reading order, which is what a canvas of hand-dragged
    boxes shows up.
    """
    ask(canvas, "b1", "encoder-decoder", "What is that structure?")
    canvas.wait_for_selector('[data-box="b2"][data-status="done"]', timeout=20000)
    answer_from_root(canvas)  # b3, off a passage below the first
    canvas.wait_for_selector('[data-box="b3"][data-status="done"]', timeout=20000)
    ask(canvas, "b1", "layer normalisation", "What does it normalise?")
    canvas.wait_for_selector('[data-box="b4"][data-status="done"]', timeout=20000)
    zoom_to_fit(canvas)  # all three open to the right of the root, past the window edge
    settled(canvas)

    # b3 is pinned where it already sits, in the middle of the column.
    drag_header_by(canvas, "b3", 0, 60)
    settled(canvas)

    # b4, last by passage, is pinned at the top of the column, above both of them.
    b2, b4 = box_rect(canvas, "b2"), box_rect(canvas, "b4")
    drag_header_by(canvas, "b4", 0, b2["y"] - b4["y"])
    settled(canvas)

    after = {box: box_rect(canvas, box) for box in ("b2", "b3", "b4")}
    assert not overlap(after["b2"], after["b4"]), after
    assert not overlap(after["b2"], after["b3"]), after


def test_should_not_pin_a_box_from_a_sideways_only_drag(canvas):
    """Moving x is a width choice, not a height choice: it must leave the box free
    for the next settle pass to place it beside its passage, same as it always was."""
    answer_from_root(canvas)  # b2
    zoom_to_fit(canvas)  # b2 opens to the right of the root, past the edge of the window
    drag_header_by(canvas, "b2", 150, 0)
    settled(canvas)
    expect(canvas.locator('[data-box="b2"] [data-unpin]')).to_be_hidden()
