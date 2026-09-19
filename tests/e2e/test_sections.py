"""Collapsible sections, derived straight from a document's own headings.

A long answer is not one wall of text, it is a table of contents a reader can fold.
`sections.js` wraps each heading and everything under it in a `<section>`, nested by
level, so a reader can hide the parts already understood without losing the parts
still in question. The one rule everything else stands on: an anchor is a character
offset into the box's rendered plain text, and the transform only ever moves nodes
about, so that plain text has to read identically before sectioning, after it, and
again once a section is folded away. Wrapping a heading must not cost it a single
character, or every stored anchor in the document silently drifts.

The control has to earn its place too: a chevron folds one section and nothing wider,
a crossed fold has to open before a selection is measured rather than after, and the
way back has to land on the passage itself, not just the box that holds it.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import expect
from tests.fixtures.editor import SAVE_TOP, edit
from tests.fixtures.selection import SELECT, ask, find_offsets, highlight, plain_text
from tests.fixtures.viewport import box_rect, canvas_id_of, edge_start

from .conftest import FIXTURES, canvas_from

pytestmark = pytest.mark.e2e

SECTIONS_DOC = (FIXTURES / "sections_doc.md").read_text(encoding="utf-8")

QUESTION = "Why do gradients vanish?"
NEEDLE = "Gradients shrink"


@pytest.fixture
def canvas(app):
    """A document with a paragraph before the first heading, a repeated heading, and
    a section nested three levels deep, so every shape the transform must handle is
    on the page at once."""
    return canvas_from(app, SECTIONS_DOC)


def chevron(page, key: str, box: str = "b1"):
    """The fold button that belongs to one section, and no other of the same name.
    The heading is the section's first child whatever its level, and the chevron is
    the first thing inside it."""
    return page.locator(f'[data-box="{box}"] [data-sec="{key}"] > * > [data-sec-toggle]')


def section_body(page, key: str, box: str = "b1"):
    """The part of a section a fold hides. The heading stays on screen, so the folded
    state is read here and not on the section."""
    return page.locator(f'[data-box="{box}"] [data-sec="{key}"] > [data-sec-body]')


def ask_about(page, box: str, needle: str, question: str) -> None:
    """Highlight a passage and wait for the answer to land, the way a reader asks."""
    ask(page, box, needle, question)
    page.wait_for_selector('[data-box="b2"][data-status="done"]', timeout=20000)


def answer_about_vanishing_gradients(page) -> None:
    """The one passage nested three headings deep, asked about and answered."""
    ask_about(page, "b1", NEEDLE, QUESTION)


def answer_then_fold(page) -> None:
    """That answer, with the passage it came from then folded out of sight."""
    answer_about_vanishing_gradients(page)
    chevron(page, "vanishing-gradients").click()


def select_across_the_fold(page) -> tuple[int, int]:
    """Fold the deepest section, then drag from above the fold to below it."""
    chevron(page, "vanishing-gradients").click()
    start, _ = find_offsets(page, "b1", "hard to parallelise")
    _, end = find_offsets(page, "b1", "distance penalty")
    page.evaluate(SELECT, ["b1", start, end])
    return start, end


def stored_sections(page, server, box: str = "b1") -> list[str]:
    """The folded keys the server holds for one box."""
    view = page.request.get(f"{server}/api/canvases/{canvas_id_of(page)}").json()
    return next(b for b in view["boxes"] if b["id"] == box)["sections"]


# --- structure and the invariant -------------------------------------------


def test_should_wrap_each_heading_in_a_section(canvas):
    # One heading of each level in the fixture, plus the repeated h2: five in all.
    expect(canvas.locator('[data-box="b1"] [data-sec]')).to_have_count(5)


def test_should_nest_a_deeper_heading_inside_the_section_above_it(canvas):
    nested = canvas.locator(
        '[data-box="b1"] [data-sec="background"] [data-sec-body] > [data-sec="recurrent-networks"]'
    )
    expect(nested).to_have_count(1)


def test_should_close_a_section_at_the_next_heading_of_the_same_level(canvas):
    # The second "Background" is a sibling of the first, not a child of it.
    sibling = canvas.locator(
        '[data-box="b1"] [data-sec="background"] [data-sec-body] [data-sec="background-2"]'
    )
    expect(sibling).to_have_count(0)


UNWRAPPED_INTRO = """() => {
  const body = document.querySelector('[data-box="b1"] [data-body]');
  const p = [...body.children].find((el) => el.tagName === 'P');
  return p ? p.closest('[data-sec]') === null : null;
}"""


def test_should_leave_the_text_before_the_first_heading_unwrapped(canvas):
    # Sectioning has to have actually run, or "unwrapped" would be true for nothing.
    expect(canvas.locator('[data-box="b1"] [data-sec]').first).to_be_visible()
    assert canvas.evaluate(UNWRAPPED_INTRO)


def test_should_leave_the_rendered_plain_text_unchanged(canvas):
    canvas.wait_for_selector('[data-box="b1"] [data-sec]')
    text = plain_text(canvas, "b1")
    assert NEEDLE in text
    assert "Sections And Folding" in text
    assert "distance penalty a" in text


def test_should_leave_the_rendered_plain_text_unchanged_when_a_section_is_folded(canvas):
    before = plain_text(canvas, "b1")
    chevron(canvas, "vanishing-gradients").click()
    after = plain_text(canvas, "b1")
    assert after == before


def test_should_give_two_headings_of_the_same_name_different_keys(canvas):
    first = canvas.locator('[data-box="b1"] [data-sec="background"]')
    second = canvas.locator('[data-box="b1"] [data-sec="background-2"]')
    expect(first).to_have_count(1)
    expect(second).to_have_count(1)


# --- the control -------------------------------------------------------------


def test_should_fold_a_section_from_its_chevron(canvas):
    chevron(canvas, "background").click()
    expect(section_body(canvas, "background")).to_have_attribute("data-collapsed", "1")


def test_should_unfold_a_section_from_its_chevron(canvas):
    toggle = chevron(canvas, "background")
    toggle.click()
    toggle.click()
    expect(section_body(canvas, "background")).to_be_visible()


def test_should_track_aria_expanded_on_the_chevron(canvas):
    toggle = chevron(canvas, "background")
    expect(toggle).to_have_attribute("aria-expanded", "true")
    toggle.click()
    expect(toggle).to_have_attribute("aria-expanded", "false")


def test_should_name_the_chevron_for_a_screen_reader(canvas):
    expect(chevron(canvas, "background")).to_have_attribute("aria-label", "Fold this section")


def test_should_not_fold_the_box_when_a_section_chevron_is_clicked(canvas):
    chevron(canvas, "background").click()
    expect(canvas.locator('[data-box="b1"]')).not_to_have_attribute("data-collapsed", "1")


def test_should_not_fold_a_section_when_its_heading_text_is_selected(canvas):
    canvas.wait_for_selector('[data-box="b1"] [data-sec="recurrent-networks"]')
    highlight(canvas, "b1", "Recurrent Networks")
    expect(section_body(canvas, "recurrent-networks")).not_to_have_attribute("data-collapsed", "1")


# --- anchors and edges ---------------------------------------------------------


def test_should_keep_an_anchor_quote_after_the_section_holding_it_folds(canvas):
    answer_then_fold(canvas)
    expect(canvas.locator('[data-box="b2"] [data-quote]')).to_have_text(NEEDLE)


def test_should_draw_the_edge_from_the_box_when_its_anchor_is_folded_away(canvas):
    answer_then_fold(canvas)
    canvas.wait_for_timeout(200)  # geometry is re-measured on the next frame
    rect = box_rect(canvas, "b1")
    start = edge_start(canvas, "b2")
    assert abs(start["x"] - (rect["x"] + rect["w"])) <= 60


def test_should_unfold_a_section_to_land_on_the_passage_behind_it(canvas):
    answer_then_fold(canvas)
    canvas.click('[data-box="b2"] [data-quote]')
    expect(section_body(canvas, "vanishing-gradients")).not_to_have_attribute("data-collapsed", "1")


def test_should_anchor_a_heading_first_word_with_the_chevron_present(canvas):
    # The chevron sits inside the heading, first child, holding no text of its own.
    expect(chevron(canvas, "recurrent-networks")).to_have_count(1)
    ask_about(canvas, "b1", "Recurrent Networks", "What is this section about?")
    expect(canvas.locator('[data-box="b1"] mark[data-anchor]')).to_have_text("Recurrent Networks")


# --- a selection across a fold ---------------------------------------------


def test_should_unfold_a_section_a_selection_crosses(canvas):
    select_across_the_fold(canvas)
    expect(section_body(canvas, "vanishing-gradients")).not_to_have_attribute("data-collapsed", "1")


def test_should_quote_only_what_is_on_screen_after_crossing_a_fold(canvas):
    start, end = select_across_the_fold(canvas)
    expected = plain_text(canvas, "b1")[start:end]
    expect(canvas.locator("[data-ask-quote]")).to_have_text(expected)


# --- find and layout -----------------------------------------------------------


def test_should_stop_counting_find_matches_hidden_by_a_folded_section(canvas):
    """The word "shrink" sits in the folded paragraph and nowhere else, so nothing is
    left to count once that paragraph is away."""
    chevron(canvas, "vanishing-gradients").click()
    canvas.fill("[data-find]", "shrink")
    expect(canvas.locator("[data-find-count]")).to_have_text("0/0")


def test_should_still_find_the_heading_of_a_folded_section(canvas):
    """A fold hides the body and leaves the heading on screen, so the heading has to
    stay findable: it is how a reader searches for the section they put away."""
    chevron(canvas, "vanishing-gradients").click()
    canvas.fill("[data-find]", "Vanishing Gradients")
    expect(canvas.locator("[data-find-count]")).to_have_text("1/1")


def test_should_recount_find_matches_when_a_section_unfolds(canvas):
    toggle = chevron(canvas, "vanishing-gradients")
    toggle.click()
    canvas.fill("[data-find]", "Gradients")
    toggle.click()
    # "Vanishing Gradients" the heading, "Gradients shrink" the paragraph: the heading
    # counted all along, and unfolding brings the paragraph back. The counter reads the
    # current one of the total rather than a tally of both.
    expect(canvas.locator("[data-find-count]")).to_have_text("1/2")


def test_should_raise_the_boxes_below_when_a_section_folds(canvas):
    """Folding a section earlier in the document shortens what sits above the
    passage this answer was seated beside, so the answer rises with it."""
    ask_about(canvas, "b1", "distance penalty", "Why does attention help?")
    canvas.wait_for_timeout(400)  # the seating pass settles behind a frame
    before_y = box_rect(canvas, "b2")["y"]
    chevron(canvas, "vanishing-gradients").click()
    canvas.wait_for_timeout(400)
    after_y = box_rect(canvas, "b2")["y"]
    assert after_y < before_y


# --- persistence -----------------------------------------------------------


def test_should_keep_a_folded_section_after_a_reload(canvas):
    chevron(canvas, "vanishing-gradients").click()
    canvas.wait_for_timeout(400)  # the fold is patched in the background
    canvas.reload()
    canvas.wait_for_selector('[data-box="b1"]')
    expect(section_body(canvas, "vanishing-gradients")).to_have_attribute("data-collapsed", "1")


def test_should_send_the_fold_to_the_server_in_one_patch(canvas, server):
    chevron(canvas, "vanishing-gradients").click()
    canvas.wait_for_timeout(400)
    assert stored_sections(canvas, server) == ["vanishing-gradients"]


# The heading renamed, nothing else touched: the stored key now matches no section.
RENAMED = SECTIONS_DOC.replace("Vanishing Gradients", "Diminishing Gradients")


def test_should_ignore_a_stored_key_whose_heading_was_edited_away(canvas):
    chevron(canvas, "vanishing-gradients").click()
    canvas.wait_for_timeout(400)  # the fold is patched in the background

    edit(canvas, "b1", RENAMED)
    canvas.click(SAVE_TOP.format(box="b1"))
    canvas.wait_for_selector('[data-box="b1"] [data-sec="diminishing-gradients"]')

    # A key nobody claims folds nothing, and the console stays clean (the `app`
    # fixture fails the test outright if it does not).
    expect(section_body(canvas, "diminishing-gradients")).not_to_have_attribute(
        "data-collapsed", "1"
    )


def test_should_drop_a_dead_key_on_the_next_fold(canvas, server):
    """The stale key is not chased down when the edit lands, because an edit is not a
    fold. It leaves on the next fold, the one path that already knows every live
    section, so a renamed heading cannot reclaim its old fold later."""
    chevron(canvas, "vanishing-gradients").click()
    canvas.wait_for_timeout(400)
    edit(canvas, "b1", RENAMED)
    canvas.click(SAVE_TOP.format(box="b1"))
    canvas.wait_for_selector('[data-box="b1"] [data-sec="diminishing-gradients"]')

    chevron(canvas, "background").click()
    canvas.wait_for_timeout(400)
    assert stored_sections(canvas, server) == ["background"]
