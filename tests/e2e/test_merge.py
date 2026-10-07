"""Folding an answer back into the document it came from.

A merge is never taken on trust. The parent box turns into a diff of the whole document,
side by side, and the proposed side is a real editor: a change is dropped by the control
on its chunk and reworded by typing. These tests drive that review the way a reader does,
and then read the markdown the server actually holds, because that file is what the merge
is judged by.
"""

from __future__ import annotations

import pytest
from tests.fixtures.merging import (
    ACCEPT,
    ACCEPT_DELETE,
    CHANGE,
    CHANGES,
    CURRENT,
    DIFF,
    DROP,
    KEEP,
    MERGE_BUTTON,
    ONE_CHUNK,
    ONLY,
    PANE,
    PROPOSED,
    REJECT,
    SKIP,
    change_state,
    proposed_text,
    reword,
    source_of,
    start_merge,
)
from tests.fixtures.selection import QUOTE, ask, highlight
from tests.fixtures.viewport import drag_popover, transform_of

from research_canvas.config import CHROME_HEIGHT

pytestmark = pytest.mark.e2e

MERGED = "a new simple network architecture with no recurrence"
REPLACED = "Self-attention layers beat recurrent layers on short sequences"
UNPLACEABLE = "nothing lands here"

# What the two changes of a one-chunk run write, when they are asked for by name.
DATED = "The dominant sequence transduction models of 2017"
STACK = "that include an encoder and a decoder stack"


def one_answer(page, box: str = "b1", needle: str = QUOTE) -> str:
    """One finished answer, ready to be folded into the box it was asked from."""
    ask(page, box, needle, "What is a residual connection?")
    page.wait_for_selector('[data-box="b2"][data-status="done"]', timeout=20000)
    return "b2"


def test_should_offer_merge_on_an_answer_and_never_on_the_document(canvas):
    child = one_answer(canvas)

    assert canvas.is_visible(MERGE_BUTTON.format(box=child))
    assert not canvas.is_visible(MERGE_BUTTON.format(box="b1"))


def test_should_say_what_every_change_the_run_proposed_does(canvas):
    child = one_answer(canvas)

    start_merge(canvas, child)

    assert canvas.locator(CHANGES.format(box="b1")).count() == 3


def test_should_show_the_document_as_it_is_beside_the_document_proposed(canvas):
    child = one_answer(canvas)

    start_merge(canvas, child)

    assert canvas.is_visible(CURRENT.format(box="b1"))
    assert canvas.is_visible(PROPOSED.format(box="b1"))


def test_should_number_the_lines_of_both_documents(canvas):
    child = one_answer(canvas)

    start_merge(canvas, child)

    assert canvas.locator(CURRENT.format(box="b1") + " .cm-lineNumbers").count() == 1
    assert canvas.locator(PROPOSED.format(box="b1") + " .cm-lineNumbers").count() == 1


def test_should_mark_the_words_a_change_touches_inside_the_line(canvas):
    child = one_answer(canvas)

    start_merge(canvas, child)

    marked = canvas.locator(PROPOSED.format(box="b1") + " .cm-changedText")
    assert marked.count() > 0
    assert "recurrence" in " ".join(marked.all_inner_texts())


def test_should_fold_the_stretches_no_change_touches(canvas):
    child = one_answer(canvas)

    start_merge(canvas, child)

    folded = canvas.locator(DIFF.format(box="b1") + " .cm-collapsedLines")
    assert folded.count() > 0


def test_should_open_a_folded_stretch_when_it_is_clicked(canvas):
    child = one_answer(canvas)
    start_merge(canvas, child)
    folded = canvas.locator(DIFF.format(box="b1") + " .cm-collapsedLines")
    before = folded.count()

    folded.first.click()

    assert canvas.locator(DIFF.format(box="b1") + " .cm-collapsedLines").count() < before


def test_should_widen_the_document_while_it_is_under_review(canvas):
    child = one_answer(canvas)
    narrow = canvas.locator('[data-box="b1"]').bounding_box()["width"]

    start_merge(canvas, child)

    assert canvas.locator('[data-box="b1"]').bounding_box()["width"] > narrow


def test_should_give_the_width_back_when_the_review_closes(canvas):
    child = one_answer(canvas)
    narrow = canvas.locator('[data-box="b1"]').bounding_box()["width"]
    start_merge(canvas, child)

    canvas.click(REJECT.format(box="b1"))
    canvas.wait_for_selector(PANE.format(box="b1"), state="detached")

    assert canvas.locator('[data-box="b1"]').bounding_box()["width"] == narrow


def test_should_hide_the_document_body_while_it_is_under_review(canvas):
    child = one_answer(canvas)

    start_merge(canvas, child)

    assert not canvas.is_visible('[data-box="b1"] [data-body]')


def test_should_not_open_the_ask_popover_while_the_parent_is_under_review(canvas):
    child = one_answer(canvas)
    start_merge(canvas, child)

    highlight(canvas, child, "residual connection")  # the child still reads normally
    canvas.wait_for_selector("[data-ask]")
    canvas.keyboard.press("Escape")
    assert canvas.locator('[data-box="b1"] [data-body]').count() == 1
    assert not canvas.is_visible('[data-box="b1"] [data-body]')


def test_should_name_the_section_a_change_lands_in(canvas):
    child = one_answer(canvas)

    start_merge(canvas, child)

    first = CHANGE.format(box="b1", change="e1")
    assert "attention is all you need" in canvas.inner_text(first).lower()


def test_should_say_which_change_could_not_be_placed(canvas):
    child = one_answer(canvas)

    start_merge(canvas, child)

    gone = canvas.locator('[data-box="b1"] [data-change][data-result="missing"]')
    assert gone.count() == 1
    assert "no longer in the document" in gone.inner_text()


def test_should_write_every_kept_change_on_accept(canvas, server):
    child = one_answer(canvas)
    start_merge(canvas, child)

    canvas.click(ACCEPT.format(box="b1"))
    canvas.wait_for_selector(PANE.format(box="b1"), state="detached")

    source = source_of(canvas, server)
    assert MERGED in source
    assert REPLACED in source
    assert UNPLACEABLE not in source


def test_should_leave_out_a_change_the_reader_dropped(canvas, server):
    child = one_answer(canvas)
    start_merge(canvas, child)

    # The first chunk in document order is the first change. Dropping it copies the
    # current text back over the proposal, which is what skipping a change means here.
    canvas.locator(DROP.format(box="b1")).first.click()
    canvas.click(ACCEPT.format(box="b1"))
    canvas.wait_for_selector(PANE.format(box="b1"), state="detached")

    source = source_of(canvas, server)
    assert MERGED not in source
    # Untouched, not removed, and still soft-wrapped where the document wrapped it.
    assert "a\nnew simple network architecture" in source
    assert REPLACED in source


def test_should_put_the_accept_button_to_sleep_when_every_change_is_dropped(canvas):
    child = one_answer(canvas)
    start_merge(canvas, child)

    drops = canvas.locator(DROP.format(box="b1"))
    while drops.count():
        drops.first.click()

    canvas.wait_for_selector(ACCEPT.format(box="b1") + "[disabled]")


# --- taking one change and leaving the next -----------------------------------
#
# A chunk of the diff is a run of changed lines, and two changes can land inside one of
# them. The arrow on the chunk therefore cannot speak for either change on its own, so
# every change that landed carries its own pair of buttons, and the two controls read
# the same document: press one and the other says so.


def test_should_offer_keep_and_skip_on_every_change_that_landed(canvas):
    child = one_answer(canvas)

    start_merge(canvas, child)

    # Two of the three landed. The one that could not be placed has nothing to toggle.
    assert canvas.locator(CHANGES.format(box="b1") + " [data-change-skip]").count() == 2


def test_should_call_a_change_kept_when_the_review_opens(canvas):
    child = one_answer(canvas)

    start_merge(canvas, child)

    assert change_state(canvas, "e1") == "kept"


def test_should_take_a_change_out_of_the_document_when_it_is_skipped(canvas):
    child = one_answer(canvas)
    start_merge(canvas, child)

    canvas.click(SKIP.format(box="b1", change="e1"))

    reviewed = proposed_text(canvas)
    assert MERGED not in reviewed
    assert REPLACED in reviewed


def test_should_put_the_document_back_as_it_was_wrapped_when_a_change_is_skipped(canvas):
    child = one_answer(canvas)
    start_merge(canvas, child)

    canvas.click(SKIP.format(box="b1", change="e1"))

    # Byte for byte the old text, soft wrap and all, so skipping leaves no trace.
    assert "a\nnew simple network architecture" in proposed_text(canvas)


def test_should_put_a_skipped_change_back_when_it_is_kept(canvas):
    child = one_answer(canvas)
    start_merge(canvas, child)

    canvas.click(SKIP.format(box="b1", change="e1"))
    canvas.click(KEEP.format(box="b1", change="e1"))

    assert MERGED in proposed_text(canvas)


def test_should_say_a_change_is_skipped_once_it_is(canvas):
    child = one_answer(canvas)
    start_merge(canvas, child)

    canvas.click(SKIP.format(box="b1", change="e1"))

    assert change_state(canvas, "e1") == "skipped"
    assert change_state(canvas, "e2") == "kept"


def test_should_say_a_change_is_skipped_when_its_chunk_is_dropped_in_the_diff(canvas):
    child = one_answer(canvas)
    start_merge(canvas, child)

    canvas.locator(DROP.format(box="b1")).first.click()

    # One document, two controls: the arrow in the diff moves the row in the list.
    assert change_state(canvas, "e1") == "skipped"


def test_should_write_only_the_changes_left_standing_on_accept(canvas, server):
    child = one_answer(canvas)
    start_merge(canvas, child)

    canvas.click(SKIP.format(box="b1", change="e1"))
    canvas.click(ACCEPT.format(box="b1"))
    canvas.wait_for_selector(PANE.format(box="b1"), state="detached")

    source = source_of(canvas, server)
    assert MERGED not in source
    assert REPLACED in source


def test_should_take_one_change_out_of_a_chunk_that_holds_two(canvas, server):
    child = one_answer(canvas)
    start_merge(canvas, child, guidance=f"Fold it in. {ONE_CHUNK}")
    # Two changes, and the diff shows them as one chunk with one arrow between them.
    assert canvas.locator(CHANGES.format(box="b1")).count() == 2
    assert canvas.locator(DROP.format(box="b1")).count() == 1

    canvas.click(SKIP.format(box="b1", change="e1"))
    canvas.click(ACCEPT.format(box="b1"))
    canvas.wait_for_selector(PANE.format(box="b1"), state="detached")

    source = source_of(canvas, server)
    assert DATED not in source
    assert STACK in source


def test_should_leave_one_change_standing_when_only_this_is_pressed(canvas):
    child = one_answer(canvas)
    start_merge(canvas, child)

    canvas.locator(ONLY.format(box="b1")).first.click()

    reviewed = proposed_text(canvas)
    assert MERGED in reviewed
    assert REPLACED not in reviewed


def test_should_leave_the_last_change_standing_when_only_this_is_pressed_on_it(canvas):
    child = one_answer(canvas)
    start_merge(canvas, child)

    # The last chunk ends the document, which is where a revert has a line break to
    # think about. Pressing it here is the only way that branch is ever run.
    canvas.locator(ONLY.format(box="b1")).last.click()

    reviewed = proposed_text(canvas)
    assert REPLACED in reviewed
    assert MERGED not in reviewed


def test_should_put_the_buttons_of_a_change_to_sleep_when_its_text_is_gone(canvas):
    child = one_answer(canvas)
    start_merge(canvas, child)

    canvas.locator(PROPOSED.format(box="b1") + " .cm-line").first.click()
    canvas.keyboard.press("ControlOrMeta+a")
    canvas.keyboard.type("The reader wrote the document over.")

    # Neither the old text nor the new one is there to swap, so there is nothing the
    # buttons could do, and they say so rather than moving text at random.
    assert canvas.locator(CHANGES.format(box="b1") + " [data-change-keep][disabled]").count() == 2
    assert change_state(canvas, "e1") == "adrift"


def test_should_write_a_rewording_exactly_as_it_was_typed(canvas, server):
    child = one_answer(canvas)
    start_merge(canvas, child)

    reword(canvas, "A note the reader typed.\n")
    canvas.click(ACCEPT.format(box="b1"))
    canvas.wait_for_selector(PANE.format(box="b1"), state="detached")

    assert source_of(canvas, server).startswith("A note the reader typed.\n")


def test_should_fold_the_answer_and_mark_it_merged_on_accept(canvas):
    child = one_answer(canvas)
    start_merge(canvas, child)

    canvas.click(ACCEPT.format(box="b1"))
    canvas.wait_for_selector(f'[data-box="{child}"][data-merged="1"]')

    assert "merged" in canvas.inner_text(f'[data-box="{child}"] [data-label]').lower()
    assert not canvas.is_visible(MERGE_BUTTON.format(box=child))


def test_should_keep_a_deeper_answer_when_its_box_is_merged(canvas):
    child = one_answer(canvas)
    ask(canvas, child, "residual connection", "How deep does it go?")
    canvas.wait_for_selector('[data-box="b3"][data-status="done"]', timeout=20000)

    start_merge(canvas, child)
    canvas.click(ACCEPT.format(box="b1"))
    canvas.wait_for_selector(f'[data-box="{child}"][data-merged="1"]')

    assert canvas.is_visible('[data-box="b3"]')
    assert canvas.locator('[data-box="b3"][data-merged="1"]').count() == 0


# --- accepting and clearing the answer away -----------------------------------
#
# The other half of accept, for a reader who has folded the answer in and has no further
# use for the box. One press, so the canvas is never left holding an answer that was
# merged into the document but is still sitting beside it.


def test_should_delete_the_answer_when_accept_and_delete_is_pressed(canvas):
    child = one_answer(canvas)
    start_merge(canvas, child)

    canvas.click(ACCEPT_DELETE.format(box="b1"))

    canvas.wait_for_selector(f'[data-box="{child}"]', state="detached")


def test_should_still_write_the_document_when_the_answer_is_deleted(canvas, server):
    child = one_answer(canvas)
    start_merge(canvas, child)

    canvas.click(ACCEPT_DELETE.format(box="b1"))
    canvas.wait_for_selector(PANE.format(box="b1"), state="detached")

    assert MERGED in source_of(canvas, server)


def test_should_keep_the_answer_when_plain_accept_is_pressed(canvas):
    child = one_answer(canvas)
    start_merge(canvas, child)

    canvas.click(ACCEPT.format(box="b1"))
    canvas.wait_for_selector(f'[data-box="{child}"][data-merged="1"]')

    assert canvas.is_visible(f'[data-box="{child}"]')


def test_should_put_accept_and_delete_to_sleep_when_every_change_is_dropped(canvas):
    child = one_answer(canvas)
    start_merge(canvas, child)

    drops = canvas.locator(DROP.format(box="b1"))
    while drops.count():
        drops.first.click()

    canvas.wait_for_selector(ACCEPT_DELETE.format(box="b1") + "[disabled]")


def test_should_leave_the_document_alone_when_the_merge_is_rejected(canvas, server):
    child = one_answer(canvas)
    before = source_of(canvas, server)
    start_merge(canvas, child)

    canvas.click(REJECT.format(box="b1"))
    canvas.wait_for_selector(PANE.format(box="b1"), state="detached")

    assert source_of(canvas, server) == before
    assert canvas.is_visible('[data-box="b1"] [data-body]')
    assert canvas.is_visible(MERGE_BUTTON.format(box=child))


def test_should_keep_a_review_when_escape_closes_the_pane(canvas):
    child = one_answer(canvas)
    start_merge(canvas, child)

    canvas.keyboard.press("Escape")
    canvas.wait_for_selector(PANE.format(box="b1"), state="detached")
    canvas.reload()

    canvas.wait_for_selector(PANE.format(box="b1"))


def test_should_keep_a_drop_and_a_rewording_across_a_reload(canvas):
    child = one_answer(canvas)
    start_merge(canvas, child)

    # The save is debounced, and the drop sends one of its own, so the wait is for the
    # save that carries the typing rather than for the next save of any kind.
    typed = "a rewording that has to survive\n"
    with canvas.expect_response(
        lambda response: (
            response.request.method == "PATCH"
            and typed.strip() in (response.request.post_data or "")
        )
    ):
        canvas.locator(DROP.format(box="b1")).first.click()
        reword(canvas, typed)

    canvas.reload()
    canvas.wait_for_selector(PANE.format(box="b1"))
    canvas.wait_for_selector(PROPOSED.format(box="b1"))

    reviewed = proposed_text(canvas)
    assert reviewed.startswith(typed)
    assert MERGED not in reviewed
    assert REPLACED in reviewed


def test_should_send_the_merge_when_enter_is_pressed_in_the_guidance(canvas):
    child = one_answer(canvas)

    canvas.click(MERGE_BUTTON.format(box=child))
    canvas.wait_for_selector("[data-merge-ask]")
    canvas.fill("[data-merge-input]", "Fold it in.")
    canvas.keyboard.press("Enter")

    canvas.wait_for_selector(PANE.format(box="b1"))


def test_should_close_the_review_when_the_answer_under_it_is_deleted(canvas):
    child = one_answer(canvas)
    start_merge(canvas, child)

    canvas.click(f'[data-box="{child}"] [data-delete]')

    canvas.wait_for_selector(PANE.format(box="b1"), state="detached")
    assert canvas.is_visible('[data-box="b1"] [data-body]')


# --- moving the guidance popup out of the way ---------------------------------------

POPUP = "[data-merge-ask]"


def open_merge_popup(page) -> None:
    page.click(MERGE_BUTTON.format(box=one_answer(page)))
    page.wait_for_selector(POPUP)


def test_should_move_the_merge_popup_when_its_header_is_dragged(canvas):
    open_merge_popup(canvas)
    before = canvas.locator(POPUP).bounding_box()

    drag_popover(canvas, POPUP, -150, -90)

    after = canvas.locator(POPUP).bounding_box()
    assert (round(after["x"] - before["x"]), round(after["y"] - before["y"])) == (-150, -90)


def test_should_keep_the_merge_popup_below_the_bar_when_dragged_past_the_top(canvas):
    open_merge_popup(canvas)

    drag_popover(canvas, POPUP, 0, -5000)

    assert canvas.locator(POPUP).bounding_box()["y"] >= CHROME_HEIGHT


def test_should_keep_the_merge_popup_inside_the_window_when_dragged_past_the_edge(canvas):
    open_merge_popup(canvas)

    drag_popover(canvas, POPUP, 5000, 0)

    popup = canvas.locator(POPUP).bounding_box()
    assert popup["x"] + popup["width"] <= canvas.viewport_size["width"]


def test_should_not_pan_the_desk_when_the_merge_popup_is_dragged(canvas):
    open_merge_popup(canvas)
    before = transform_of(canvas)

    drag_popover(canvas, POPUP, -150, -90)

    assert transform_of(canvas) == before


def test_should_keep_the_merge_popup_open_after_it_is_dragged(canvas):
    open_merge_popup(canvas)

    drag_popover(canvas, POPUP, -150, -90)

    assert canvas.is_visible(POPUP)


def test_should_still_send_the_merge_after_the_popup_is_moved(canvas):
    open_merge_popup(canvas)
    drag_popover(canvas, POPUP, -150, -90)

    canvas.fill("[data-merge-input]", "Fold it in.")
    canvas.click("[data-merge-send]")

    canvas.wait_for_selector(PANE.format(box="b1"))
