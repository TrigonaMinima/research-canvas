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
    canvas_id_of,
    edge_start,
    rect_of,
    scale_of,
    to_client,
    transform_of,
    view_centre,
    zoom_to_fit,
)

from research_canvas.config import BOX_GAP, CHROME_HEIGHT, MIN_BOX_WIDTH, ROOT_BOX_WIDTH

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


def answer_from_root(page, question: str = "What is a residual connection?") -> None:
    """Ask about the stock passage and wait for the answer to land."""
    ask(page, "b1", QUOTE, question)
    page.wait_for_selector('[data-box="b2"][data-status="done"]', timeout=20000)


def jump_to(page, box: str) -> None:
    """Click the highlight that opened a box and wait for the camera to settle."""
    page.locator(f'[data-box="b1"] mark[data-target="{box}"]').first.click()
    page.wait_for_timeout(700)


def drag_header_by(page, box: str, dx_canvas: float, dy_canvas: float) -> None:
    """Drag a box by its header, moving it a given distance in canvas pixels."""
    scale = scale_of(page)
    handle = page.locator(f'[data-box="{box}"] .box__head').bounding_box()
    x = handle["x"] + handle["width"] / 2
    y = handle["y"] + handle["height"] / 2
    page.mouse.move(x, y)
    page.mouse.down()
    page.mouse.move(x + dx_canvas * scale, y + dy_canvas * scale, steps=8)
    page.mouse.up()


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
    answer_from_root(canvas)
    ask(canvas, "b1", "layer normalisation", "What does it normalise?")
    canvas.wait_for_selector('[data-box="b3"][data-status="done"]', timeout=20000)
    b2, b3 = box_rect(canvas, "b2"), box_rect(canvas, "b3")
    assert not overlap(b2, b3)
    # A fixed gap is the requirement; "not overlapping" alone would also pass on the
    # accidental spacing the old, height-guessing placement() already produces.
    assert gap_between(b2, b3) == pytest.approx(BOX_GAP, abs=1), f"b2={b2} b3={b3}"


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
    three_long_answers(canvas)

    settled(canvas)  # record where the stack really lands, not a mid-pass y
    before_b4_y = box_rect(canvas, "b4")["y"]
    canvas.click('[data-box="b3"] [data-collapse]')
    settled(canvas)

    b2, b3, b4 = box_rect(canvas, "b2"), box_rect(canvas, "b3"), box_rect(canvas, "b4")
    assert gap_between(b2, b3) == pytest.approx(BOX_GAP, abs=1)
    assert gap_between(b3, b4) == pytest.approx(BOX_GAP, abs=1)
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
    """A child is never stacked with its own parent, even if a drag makes them overlap."""
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


def test_should_not_move_a_sibling_under_a_different_parent(canvas):
    """Two depth-2 boxes with different parents can land in the same column (both
    parents are the same width, so both children sit one COLUMN_GAP further right).
    Forcing them to overlap, the way test_should_leave_a_box_at_another_depth_alone
    forces a child onto its own parent, is the only way this test can actually go red
    if a restack pass ever groups by depth instead of by parent: recording "before"
    and "after" a mere reload cannot, because a depth-grouped restack would already
    have coupled them the first time it ran, on the earlier run finishing, and every
    later trigger would just reproduce that same, already-wrong pair of positions."""
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
    assert settled_b4["y"] == pytest.approx(dropped_b4["y"], abs=1)
    assert settled_b5["y"] == pytest.approx(dropped_b5["y"], abs=1)


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
