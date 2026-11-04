"""A merge is a list of edits: read them off the run and place them in the document.

The run may change anything in the parent, so nothing here is scoped to the passage.
What keeps it honest is that an edit names the text it replaces: text no edit names is
byte-identical afterwards, and an edit that cannot be placed is reported, never guessed.
"""

from __future__ import annotations

import json

from research_canvas import merge

DOC = """# Auth

Free tier is generous.

WorkOS charges from $125 per month for SSO.

Sessions are opaque cookies.
"""


def edit(find, replace, *, id="e1", why="because"):
    return merge.Edit(id=id, why=why, find=find, replace=replace)


def line(find, replace, why="because"):
    return json.dumps({"find": find, "replace": replace, "why": why})


# --- reading the run ----------------------------------------------------------


def test_should_read_one_edit_per_line():
    stream = merge.EditStream()

    edits = stream.feed(line("a", "b") + "\n" + line("c", "d") + "\n")

    assert len(edits) == 2


def test_should_carry_the_reason_for_each_edit():
    stream = merge.EditStream()

    edits = stream.feed(line("a", "b", why="names the stale figure") + "\n")

    assert edits[0].why == "names the stale figure"


def test_should_strip_a_fence_the_model_wrapped_around_the_edits():
    stream = merge.EditStream()

    edits = stream.feed("```json\n" + line("a", "b") + "\n```\n")

    assert len(edits) == 1


def test_should_skip_a_line_that_will_not_parse():
    stream = merge.EditStream()

    edits = stream.feed("Here are the edits:\n" + line("a", "b") + "\n")

    assert len(edits) == 1


def test_should_reject_a_line_missing_the_text_to_find():
    stream = merge.EditStream()

    edits = stream.feed(json.dumps({"replace": "b", "why": "c"}) + "\n")

    assert edits == []


def test_should_hold_a_partial_line_back_until_it_completes():
    stream = merge.EditStream()

    edits = stream.feed(line("a", "b")[:10])

    assert edits == []


def test_should_emit_the_held_line_once_the_rest_arrives():
    stream = merge.EditStream()
    whole = line("a", "b")

    stream.feed(whole[:10])
    edits = stream.feed(whole[10:] + "\n")

    assert len(edits) == 1


def test_should_emit_a_final_line_that_never_got_a_newline():
    stream = merge.EditStream()
    stream.feed(line("a", "b"))

    edits = stream.close()

    assert len(edits) == 1


def test_should_discard_a_final_line_the_run_truncated():
    stream = merge.EditStream()
    stream.feed(line("a", "b")[:-5])

    edits = stream.close()

    assert edits == []


def test_should_give_every_edit_its_own_id():
    stream = merge.EditStream()

    edits = stream.feed(line("a", "b") + "\n" + line("c", "d") + "\n")

    assert edits[0].id != edits[1].id


# --- placing the edits --------------------------------------------------------


def test_should_replace_the_text_an_edit_names():
    body, _ = merge.apply(DOC, [edit("from $125 per month", "from $35 per month")])

    assert "from $35 per month" in body


def test_should_leave_every_other_character_alone():
    body, _ = merge.apply(DOC, [edit("from $125 per month", "from $35 per month")])

    assert body == DOC.replace("from $125 per month", "from $35 per month")


def test_should_mark_a_placed_edit_applied():
    _, results = merge.apply(DOC, [edit("Free tier is generous.", "Free tier is ample.")])

    assert results[0].result == "applied"


def test_should_place_several_edits_at_once():
    body, _ = merge.apply(
        DOC,
        [
            edit("Free tier is generous.", "Free tier is ample.", id="e1"),
            edit("Sessions are opaque cookies.", "Sessions are opaque tokens.", id="e2"),
        ],
    )

    assert "ample" in body and "opaque tokens" in body


def test_should_not_let_an_early_edit_shift_a_later_one():
    body, results = merge.apply(
        DOC,
        [
            edit("# Auth", "# Authentication and authorization, at length", id="e1"),
            edit("Sessions are opaque cookies.", "Sessions are opaque tokens.", id="e2"),
        ],
    )

    assert "opaque tokens" in body and all(r.result == "applied" for r in results)


def test_should_report_an_edit_whose_text_is_gone():
    _, results = merge.apply(DOC, [edit("text that was never here", "anything")])

    assert results[0].result == "missing"


def test_should_not_change_the_document_for_an_edit_whose_text_is_gone():
    body, _ = merge.apply(DOC, [edit("text that was never here", "anything")])

    assert body == DOC


def test_should_report_an_edit_whose_text_appears_twice():
    doc = "Sessions are opaque cookies.\n\nSessions are opaque cookies.\n"

    _, results = merge.apply(doc, [edit("Sessions are opaque cookies.", "changed")])

    assert results[0].result == "ambiguous"


def test_should_never_apply_an_ambiguous_edit_to_the_first_match():
    doc = "Sessions are opaque cookies.\n\nSessions are opaque cookies.\n"

    body, _ = merge.apply(doc, [edit("Sessions are opaque cookies.", "changed")])

    assert body == doc


def test_should_place_an_edit_across_a_soft_wrap():
    doc = "WorkOS charges from $125\nper month for SSO.\n"

    body, _ = merge.apply(doc, [edit("charges from $125 per month", "charges from $35 per month")])

    assert "$35" in body


def test_should_use_the_readers_wording_when_they_reworded_it():
    body, _ = merge.apply(DOC, [edit("Free tier is generous.", "Free tier is what I say it is.")])

    assert "what I say it is" in body


# --- an edit as stored data ---------------------------------------------------


def test_should_round_trip_an_edit_through_a_dict():
    original = edit("a", "b")

    assert merge.Edit.from_dict(original.to_dict()) == original


# --- where a change sits ------------------------------------------------------
#
# Ordering and section labels both need one offset per edit, measured against the
# document as the reader has it, before any edit is written.


def test_should_report_where_an_edit_lands():
    doc = "alpha beta gamma"
    assert merge.where(doc, merge.Edit(id="e1", why="", find="beta", replace="BETA")) == 6


def test_should_report_no_place_for_an_edit_that_does_not_match():
    doc = "alpha beta gamma"
    assert merge.where(doc, merge.Edit(id="e1", why="", find="delta", replace="x")) is None


def test_should_find_a_soft_wrapped_edit_when_reporting_where_it_lands():
    doc = "alpha beta\ngamma delta"
    at = merge.where(doc, merge.Edit(id="e1", why="", find="beta gamma", replace="x"))
    assert at == 6
