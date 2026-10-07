"""Layer 2: folding an answer back into the document it came from.

The merge endpoints are keyed by the *child* box, even though the review renders in
the parent. One answer is what is being folded in; the parent is where it lands.
"""

from __future__ import annotations

import json

from tests.fixtures.merging import EDITS, answer, ask_body, open_merge, run_merge

from research_canvas import storage
from research_canvas.config import (
    ALREADY_MERGED_MESSAGE,
    CANVAS_FILE,
    EDIT_WHILE_MERGING_MESSAGE,
    MERGE_IN_PROGRESS_MESSAGE,
    MERGE_ROOT_MESSAGE,
    MERGE_UNREADABLE_MESSAGE,
    MERGE_WHILE_RUNNING_MESSAGE,
    NOTHING_TO_MERGE_MESSAGE,
)

# --- starting a merge ---------------------------------------------------------


def test_should_refuse_to_merge_the_document_box(client, canvas):
    response = open_merge(client, canvas, "b1", "Fold it in.")
    assert response.status_code == 422


def test_should_explain_why_the_document_box_cannot_be_merged(client, canvas):
    response = open_merge(client, canvas, "b1", "Fold it in.")
    assert response.json()["detail"] == MERGE_ROOT_MESSAGE


def test_should_refuse_to_merge_an_answer_that_is_not_finished(client, canvas):
    asked = client.post(f"/api/canvases/{canvas['id']}/ask", json=ask_body()).json()["box"]
    response = open_merge(client, canvas, asked["id"], "Fold it in.")
    assert response.status_code == 409


def test_should_explain_why_an_unfinished_answer_cannot_be_merged(client, canvas):
    asked = client.post(f"/api/canvases/{canvas['id']}/ask", json=ask_body()).json()["box"]
    response = open_merge(client, canvas, asked["id"], "Fold it in.")
    assert response.json()["detail"] == MERGE_WHILE_RUNNING_MESSAGE


def test_should_open_a_merge_on_a_finishedanswer(client, canvas, fake_answer):
    child = answer(client, canvas, fake_answer)
    response = open_merge(client, canvas, child, "Fold it in.")
    assert response.status_code == 200


def test_should_start_a_merge_with_no_changes_yet(client, canvas, fake_answer):
    child = answer(client, canvas, fake_answer)
    opened = open_merge(client, canvas, child, "Fold it in.").json()
    assert opened["changes"] == []


def test_should_name_the_box_a_merge_lands_in(client, canvas, fake_answer):
    child = answer(client, canvas, fake_answer)
    opened = open_merge(client, canvas, child, "Fold it in.").json()
    assert opened["parentId"] == "b1"


def test_should_refuse_a_second_merge_into_the_same_parent(client, canvas, fake_answer):
    first = answer(client, canvas, fake_answer)
    second = answer(client, canvas, fake_answer)
    open_merge(client, canvas, first, "Fold it in.")
    response = open_merge(client, canvas, second, "Fold it in.")
    assert response.status_code == 409


def test_should_explain_why_a_second_merge_into_one_parent_is_refused(client, canvas, fake_answer):
    first = answer(client, canvas, fake_answer)
    second = answer(client, canvas, fake_answer)
    open_merge(client, canvas, first, "Fold it in.")
    response = open_merge(client, canvas, second, "Fold it in.")
    assert response.json()["detail"] == MERGE_IN_PROGRESS_MESSAGE


def test_should_send_the_parent_document_to_the_merge_run(client, canvas, fake_answer):
    child = answer(client, canvas, fake_answer)
    run_merge(client, canvas, child, fake_answer)
    assert "sequence transduction models" in fake_answer.prompts[-1]


def test_should_send_the_readers_guidance_to_the_merge_run(client, canvas, fake_answer):
    child = answer(client, canvas, fake_answer)
    run_merge(client, canvas, child, fake_answer, guidance="Keep it to one sentence.")
    assert "Keep it to one sentence." in fake_answer.prompts[-1]


# --- reading the run ----------------------------------------------------------


def test_should_stream_a_change_as_soon_as_its_line_parses(client, canvas, fake_answer):
    child = answer(client, canvas, fake_answer)
    stream = run_merge(client, canvas, child, fake_answer)
    assert "event: edit" in stream


def test_should_stream_one_event_per_change(client, canvas, fake_answer):
    child = answer(client, canvas, fake_answer)
    stream = run_merge(client, canvas, child, fake_answer)
    assert stream.count("event: edit") == len(EDITS)


def test_should_keep_the_changes_after_the_run(client, canvas, fake_answer):
    child = answer(client, canvas, fake_answer)
    run_merge(client, canvas, child, fake_answer)
    proposal = client.get(f"/api/canvases/{canvas['id']}/boxes/{child}/merge").json()
    assert len(proposal["changes"]) == len(EDITS)


def test_should_mark_a_finished_merge_done(client, canvas, fake_answer):
    child = answer(client, canvas, fake_answer)
    run_merge(client, canvas, child, fake_answer)
    proposal = client.get(f"/api/canvases/{canvas['id']}/boxes/{child}/merge").json()
    assert proposal["status"] == "done"


def test_should_read_a_change_split_across_stream_chunks(client, canvas, fake_answer):
    child = answer(client, canvas, fake_answer)
    line = json.dumps(EDITS[0])
    run_merge(client, canvas, child, fake_answer, chunks=[line[:20], line[20:] + "\n"])
    proposal = client.get(f"/api/canvases/{canvas['id']}/boxes/{child}/merge").json()
    assert [c["why"] for c in proposal["changes"]] == [EDITS[0]["why"]]


def test_should_read_changes_wrapped_in_a_code_fence(client, canvas, fake_answer):
    child = answer(client, canvas, fake_answer)
    fenced = "```json\n" + json.dumps(EDITS[0]) + "\n```\n"
    run_merge(client, canvas, child, fake_answer, chunks=[fenced])
    proposal = client.get(f"/api/canvases/{canvas['id']}/boxes/{child}/merge").json()
    assert len(proposal["changes"]) == 1


def test_should_fail_a_merge_whose_output_holds_no_change(client, canvas, fake_answer):
    child = answer(client, canvas, fake_answer)
    run_merge(client, canvas, child, fake_answer, chunks=["I am afraid I cannot do that.\n"])
    proposal = client.get(f"/api/canvases/{canvas['id']}/boxes/{child}/merge").json()
    assert proposal["status"] == "failed"


def test_should_say_why_an_unreadable_merge_failed(client, canvas, fake_answer):
    child = answer(client, canvas, fake_answer)
    run_merge(client, canvas, child, fake_answer, chunks=["I am afraid I cannot do that.\n"])
    proposal = client.get(f"/api/canvases/{canvas['id']}/boxes/{child}/merge").json()
    assert proposal["reason"] == MERGE_UNREADABLE_MESSAGE


def test_should_keep_the_changes_a_cut_short_run_managed(client, canvas, fake_answer):
    child = answer(client, canvas, fake_answer)
    event = fake_answer.Event
    fake_answer(
        [
            event(kind="text", text=json.dumps(EDITS[0]) + "\n"),
            event(kind="failed", reason="Usage limit reached on your Claude plan."),
        ]
    )
    open_merge(client, canvas, child, "Fold it in.")
    client.get(f"/api/canvases/{canvas['id']}/boxes/{child}/merge/stream")
    proposal = client.get(f"/api/canvases/{canvas['id']}/boxes/{child}/merge").json()
    assert len(proposal["changes"]) == 1


def test_should_say_a_cut_short_run_was_cut_short(client, canvas, fake_answer):
    child = answer(client, canvas, fake_answer)
    event = fake_answer.Event
    fake_answer(
        [
            event(kind="text", text=json.dumps(EDITS[0]) + "\n"),
            event(kind="failed", reason="Usage limit reached on your Claude plan."),
        ]
    )
    open_merge(client, canvas, child, "Fold it in.")
    client.get(f"/api/canvases/{canvas['id']}/boxes/{child}/merge/stream")
    proposal = client.get(f"/api/canvases/{canvas['id']}/boxes/{child}/merge").json()
    assert "Usage limit" in proposal["reason"]


def test_should_404_a_merge_that_was_never_started(client, canvas, fake_answer):
    child = answer(client, canvas, fake_answer)
    assert client.get(f"/api/canvases/{canvas['id']}/boxes/{child}/merge").status_code == 404


# --- reviewing ----------------------------------------------------------------


def test_should_report_a_change_that_places_cleanly(client, canvas, fake_answer):
    changes = _reviewed(client, canvas, fake_answer)
    assert changes[0]["result"] == "applied"


def test_should_report_a_change_that_cannot_be_placed(client, canvas, fake_answer):
    changes = _reviewed(client, canvas, fake_answer)
    assert changes[-1]["result"] == "missing"


def test_should_label_a_change_with_the_section_it_lands_in(client, canvas, fake_answer):
    changes = _reviewed(client, canvas, fake_answer)
    assert changes[0]["section"] == "Attention Is All You Need"


# The review lets a reader take one change and leave another, and a change is finer than
# a chunk of the diff: two of them can land in one paragraph. So the text a change looks
# for and the text it writes travel with it, and the browser swaps between the two.


def test_should_carry_the_text_a_change_looks_for(client, canvas, fake_answer):
    changes = _reviewed(client, canvas, fake_answer)
    assert changes[0]["find"] == EDITS[0]["find"]


def test_should_carry_the_text_a_change_writes(client, canvas, fake_answer):
    changes = _reviewed(client, canvas, fake_answer)
    assert changes[0]["replace"] == EDITS[0]["replace"]


def test_should_propose_the_document_with_every_change_written(client, canvas, fake_answer):
    child = answer(client, canvas, fake_answer)
    run_merge(client, canvas, child, fake_answer)
    proposed = client.get(f"/api/canvases/{canvas['id']}/boxes/{child}/merge").json()["proposed"]
    assert (
        "with no recurrence" in proposed and "beat recurrent layers on short sequences" in proposed
    )


def test_should_leave_an_unplaceable_change_out_of_the_proposed_document(
    client, canvas, fake_answer
):
    child = answer(client, canvas, fake_answer)
    run_merge(client, canvas, child, fake_answer)
    proposed = client.get(f"/api/canvases/{canvas['id']}/boxes/{child}/merge").json()["proposed"]
    assert "nothing lands here" not in proposed


def test_should_leave_the_document_alone_while_a_merge_is_only_proposed(
    client, canvas, fake_answer
):
    before = _parent_markdown(client, canvas)
    child = answer(client, canvas, fake_answer)
    run_merge(client, canvas, child, fake_answer)
    assert _parent_markdown(client, canvas) == before


def test_should_save_the_document_the_reader_reviewed(client, canvas, fake_answer):
    child = answer(client, canvas, fake_answer)
    run_merge(client, canvas, child, fake_answer)
    saved = client.patch(
        f"/api/canvases/{canvas['id']}/boxes/{child}/merge",
        json={"proposed": "# Reviewed\n"},
    ).json()
    assert saved["saved"] is True


def test_should_keep_the_reviewed_document_after_a_reload(client, canvas, fake_answer):
    child = answer(client, canvas, fake_answer)
    run_merge(client, canvas, child, fake_answer)
    client.patch(
        f"/api/canvases/{canvas['id']}/boxes/{child}/merge",
        json={"proposed": "# Reviewed\n"},
    )
    reopened = client.get(f"/api/canvases/{canvas['id']}/boxes/{child}/merge").json()
    assert reopened["proposed"] == "# Reviewed\n"


def test_should_still_report_the_changes_after_the_document_is_reviewed(
    client, canvas, fake_answer
):
    child = answer(client, canvas, fake_answer)
    run_merge(client, canvas, child, fake_answer)
    client.patch(
        f"/api/canvases/{canvas['id']}/boxes/{child}/merge",
        json={"proposed": "# Reviewed\n"},
    )
    reopened = client.get(f"/api/canvases/{canvas['id']}/boxes/{child}/merge").json()
    assert [c["why"] for c in reopened["changes"]] == [edit["why"] for edit in EDITS]


def test_should_not_touch_the_canvas_when_the_review_is_saved(
    client, canvas, canvas_root, fake_answer
):
    child = answer(client, canvas, fake_answer)
    run_merge(client, canvas, child, fake_answer)
    # A proposal lives beside the canvas, not in it. Backdated rather than compared to a
    # fresh read: `updatedAt` is stamped to the second, so a rewrite within the same
    # second would look untouched.
    path = canvas_root / canvas["id"] / CANVAS_FILE
    saved = json.loads(path.read_text(encoding="utf-8"))
    saved["updatedAt"] = "2020-01-01T00:00:00Z"
    path.write_text(json.dumps(saved), encoding="utf-8")

    client.patch(
        f"/api/canvases/{canvas['id']}/boxes/{child}/merge",
        json={"proposed": "# Reviewed\n"},
    )

    view = client.get(f"/api/canvases/{canvas['id']}").json()
    assert view["updatedAt"] == "2020-01-01T00:00:00Z"


def test_should_refuse_a_review_that_carries_no_document(client, canvas, fake_answer):
    child = answer(client, canvas, fake_answer)
    run_merge(client, canvas, child, fake_answer)
    response = client.patch(f"/api/canvases/{canvas['id']}/boxes/{child}/merge", json={})
    assert response.status_code == 422


def test_should_refuse_to_review_a_merge_that_is_still_running(client, canvas, fake_answer):
    child = answer(client, canvas, fake_answer)
    open_merge(client, canvas, child, "Fold it in.")
    # A proposal only reads back as pending while the process that started it is still
    # running it, which is what `live` stands in for here.
    with storage.live(canvas["id"], child):
        response = client.patch(
            f"/api/canvases/{canvas['id']}/boxes/{child}/merge",
            json={"proposed": "# Reviewed\n"},
        )
    assert response.status_code == 409


# --- accepting ----------------------------------------------------------------


def test_should_write_an_accepted_change_into_the_parent(client, canvas, fake_answer):
    child = answer(client, canvas, fake_answer)
    run_merge(client, canvas, child, fake_answer)
    client.post(f"/api/canvases/{canvas['id']}/boxes/{child}/merge/accept")
    assert "with no recurrence" in _parent_markdown(client, canvas)


def test_should_write_changes_in_more_than_one_place(client, canvas, fake_answer):
    child = answer(client, canvas, fake_answer)
    run_merge(client, canvas, child, fake_answer)
    client.post(f"/api/canvases/{canvas['id']}/boxes/{child}/merge/accept")
    body = _parent_markdown(client, canvas)
    assert "with no recurrence" in body and "beat recurrent layers on short sequences" in body


def test_should_write_exactly_the_document_the_reader_reviewed(client, canvas, fake_answer):
    child = answer(client, canvas, fake_answer)
    run_merge(client, canvas, child, fake_answer)
    reviewed = _proposed(client, canvas, child) + "\nA line the reader added.\n"
    client.patch(f"/api/canvases/{canvas['id']}/boxes/{child}/merge", json={"proposed": reviewed})
    client.post(f"/api/canvases/{canvas['id']}/boxes/{child}/merge/accept")
    assert _parent_markdown(client, canvas) == reviewed


def test_should_leave_a_dropped_change_out_of_the_parent(client, canvas, fake_answer):
    child = answer(client, canvas, fake_answer)
    run_merge(client, canvas, child, fake_answer)
    # Dropping a chunk in the review puts the current text back. Here that is the
    # find text the change was written over.
    kept = _proposed(client, canvas, child).replace(EDITS[0]["replace"], EDITS[0]["find"])
    client.patch(f"/api/canvases/{canvas['id']}/boxes/{child}/merge", json={"proposed": kept})
    client.post(f"/api/canvases/{canvas['id']}/boxes/{child}/merge/accept")
    assert "with no recurrence" not in _parent_markdown(client, canvas)


def test_should_write_a_reworded_change_exactly_as_the_reader_left_it(client, canvas, fake_answer):
    child = answer(client, canvas, fake_answer)
    run_merge(client, canvas, child, fake_answer)
    reworded = _proposed(client, canvas, child).replace(
        EDITS[0]["replace"], "a wholly new architecture"
    )
    client.patch(f"/api/canvases/{canvas['id']}/boxes/{child}/merge", json={"proposed": reworded})
    client.post(f"/api/canvases/{canvas['id']}/boxes/{child}/merge/accept")
    assert "a wholly new architecture" in _parent_markdown(client, canvas)


def test_should_leave_text_no_change_names_byte_identical(client, canvas, fake_answer):
    before = _parent_markdown(client, canvas)
    child = answer(client, canvas, fake_answer)
    run_merge(client, canvas, child, fake_answer)
    client.post(f"/api/canvases/{canvas['id']}/boxes/{child}/merge/accept")
    after = _parent_markdown(client, canvas)
    assert after.splitlines()[0] == before.splitlines()[0]


def test_should_refuse_an_accept_that_changes_nothing(client, canvas, fake_answer):
    child = answer(client, canvas, fake_answer)
    run_merge(client, canvas, child, fake_answer)
    client.patch(
        f"/api/canvases/{canvas['id']}/boxes/{child}/merge",
        json={"proposed": _parent_markdown(client, canvas)},
    )
    response = client.post(f"/api/canvases/{canvas['id']}/boxes/{child}/merge/accept")
    assert response.status_code == 422


def test_should_explain_an_accept_that_changes_nothing(client, canvas, fake_answer):
    child = answer(client, canvas, fake_answer)
    run_merge(client, canvas, child, fake_answer)
    client.patch(
        f"/api/canvases/{canvas['id']}/boxes/{child}/merge",
        json={"proposed": _parent_markdown(client, canvas)},
    )
    response = client.post(f"/api/canvases/{canvas['id']}/boxes/{child}/merge/accept")
    assert response.json()["detail"] == NOTHING_TO_MERGE_MESSAGE


def test_should_mark_the_child_merged_after_accepting(client, canvas, fake_answer):
    child = answer(client, canvas, fake_answer)
    run_merge(client, canvas, child, fake_answer)
    view = client.post(f"/api/canvases/{canvas['id']}/boxes/{child}/merge/accept").json()
    assert next(b for b in view["boxes"] if b["id"] == child)["merged"] is True


def test_should_fold_the_child_after_accepting(client, canvas, fake_answer):
    child = answer(client, canvas, fake_answer)
    run_merge(client, canvas, child, fake_answer)
    view = client.post(f"/api/canvases/{canvas['id']}/boxes/{child}/merge/accept").json()
    assert next(b for b in view["boxes"] if b["id"] == child)["collapsed"] is True


def test_should_keep_the_child_after_accepting(client, canvas, fake_answer):
    child = answer(client, canvas, fake_answer)
    run_merge(client, canvas, child, fake_answer)
    view = client.post(f"/api/canvases/{canvas['id']}/boxes/{child}/merge/accept").json()
    assert child in {b["id"] for b in view["boxes"]}


def test_should_keep_an_answer_asked_from_inside_the_merged_child(client, canvas, fake_answer):
    child = answer(client, canvas, fake_answer)
    deeper = answer(client, canvas, fake_answer, box_id=child)
    run_merge(client, canvas, child, fake_answer)
    view = client.post(f"/api/canvases/{canvas['id']}/boxes/{child}/merge/accept").json()
    assert deeper in {b["id"] for b in view["boxes"]}


# --- accepting and clearing the answer away -----------------------------------
#
# The other half of accept: the text goes into the document and the answer goes away,
# for a reader who folded it in and has no further use for the box. One request, so the
# canvas is never left holding an answer that was merged but not removed.


def test_should_remove_the_child_when_the_accept_asks_for_it(client, canvas, fake_answer):
    child = answer(client, canvas, fake_answer)
    run_merge(client, canvas, child, fake_answer)
    view = client.post(
        f"/api/canvases/{canvas['id']}/boxes/{child}/merge/accept", json={"removeChild": True}
    ).json()
    assert child not in {b["id"] for b in view["boxes"]}


def test_should_still_write_the_document_when_the_child_is_removed(client, canvas, fake_answer):
    child = answer(client, canvas, fake_answer)
    run_merge(client, canvas, child, fake_answer)
    client.post(
        f"/api/canvases/{canvas['id']}/boxes/{child}/merge/accept", json={"removeChild": True}
    )
    assert "with no recurrence" in _parent_markdown(client, canvas)


def test_should_take_the_anchor_with_a_removed_child(client, canvas, fake_answer):
    child = answer(client, canvas, fake_answer)
    run_merge(client, canvas, child, fake_answer)
    view = client.post(
        f"/api/canvases/{canvas['id']}/boxes/{child}/merge/accept", json={"removeChild": True}
    ).json()
    assert not [a for a in view["anchors"] if a["target"] == child]


def test_should_take_a_deeper_answer_with_a_removed_child(client, canvas, fake_answer):
    child = answer(client, canvas, fake_answer)
    deeper = answer(client, canvas, fake_answer, box_id=child)
    run_merge(client, canvas, child, fake_answer)
    view = client.post(
        f"/api/canvases/{canvas['id']}/boxes/{child}/merge/accept", json={"removeChild": True}
    ).json()
    assert deeper not in {b["id"] for b in view["boxes"]}


def test_should_keep_the_child_when_the_accept_does_not_ask(client, canvas, fake_answer):
    child = answer(client, canvas, fake_answer)
    run_merge(client, canvas, child, fake_answer)
    view = client.post(
        f"/api/canvases/{canvas['id']}/boxes/{child}/merge/accept", json={"removeChild": False}
    ).json()
    assert child in {b["id"] for b in view["boxes"]}


def test_should_drop_the_proposal_of_a_removed_child(client, canvas, fake_answer):
    child = answer(client, canvas, fake_answer)
    run_merge(client, canvas, child, fake_answer)
    client.post(
        f"/api/canvases/{canvas['id']}/boxes/{child}/merge/accept", json={"removeChild": True}
    )
    assert client.get(f"/api/canvases/{canvas['id']}/boxes/{child}/merge").status_code == 404


def test_should_refuse_to_remove_a_child_whose_merge_is_still_running(client, canvas, fake_answer):
    child = answer(client, canvas, fake_answer)
    open_merge(client, canvas, child, "Fold it in.")
    # `live` stands in for the process that is still running the merge, which is the
    # only time a proposal reads back as pending.
    with storage.live(canvas["id"], child):
        response = client.post(
            f"/api/canvases/{canvas['id']}/boxes/{child}/merge/accept", json={"removeChild": True}
        )
    assert response.status_code == 409


def test_should_drop_the_proposal_after_accepting(client, canvas, fake_answer):
    child = answer(client, canvas, fake_answer)
    run_merge(client, canvas, child, fake_answer)
    client.post(f"/api/canvases/{canvas['id']}/boxes/{child}/merge/accept")
    assert client.get(f"/api/canvases/{canvas['id']}/boxes/{child}/merge").status_code == 404


def test_should_refuse_to_merge_an_answer_twice(client, canvas, fake_answer):
    child = answer(client, canvas, fake_answer)
    run_merge(client, canvas, child, fake_answer)
    client.post(f"/api/canvases/{canvas['id']}/boxes/{child}/merge/accept")
    response = open_merge(client, canvas, child, "Fold it in.")
    assert response.json()["detail"] == ALREADY_MERGED_MESSAGE


def test_should_move_an_anchor_the_merge_rewrote(client, canvas, fake_answer):
    # A passage one of the changes rewrites away, so the anchor cannot stay where it is.
    child = answer(client, canvas, fake_answer, quote="are faster than recurrent layers")
    run_merge(client, canvas, child, fake_answer)
    view = client.post(f"/api/canvases/{canvas['id']}/boxes/{child}/merge/accept").json()
    anchor = next(a for a in view["anchors"] if a["target"] == child)
    assert anchor["quote"] != "are faster than recurrent layers"


def test_should_leave_an_anchor_the_merge_did_not_touch(client, canvas, fake_answer):
    child = answer(client, canvas, fake_answer, quote="neural networks")
    run_merge(client, canvas, child, fake_answer)
    view = client.post(f"/api/canvases/{canvas['id']}/boxes/{child}/merge/accept").json()
    anchor = next(a for a in view["anchors"] if a["target"] == child)
    assert anchor["quote"] == "neural networks"


# --- rejecting, and getting out of the way ------------------------------------


def test_should_drop_a_rejected_merge(client, canvas, fake_answer):
    child = answer(client, canvas, fake_answer)
    run_merge(client, canvas, child, fake_answer)
    client.delete(f"/api/canvases/{canvas['id']}/boxes/{child}/merge")
    assert client.get(f"/api/canvases/{canvas['id']}/boxes/{child}/merge").status_code == 404


def test_should_leave_the_parent_alone_when_a_merge_is_rejected(client, canvas, fake_answer):
    before = _parent_markdown(client, canvas)
    child = answer(client, canvas, fake_answer)
    run_merge(client, canvas, child, fake_answer)
    client.delete(f"/api/canvases/{canvas['id']}/boxes/{child}/merge")
    assert _parent_markdown(client, canvas) == before


def test_should_refuse_to_edit_a_parent_with_a_merge_waiting(client, canvas, fake_answer):
    child = answer(client, canvas, fake_answer)
    run_merge(client, canvas, child, fake_answer)
    response = client.put(
        f"/api/canvases/{canvas['id']}/boxes/b1/body", json={"markdown": "# Rewritten\n"}
    )
    assert response.status_code == 409


def test_should_explain_why_a_parent_under_review_cannot_be_edited(client, canvas, fake_answer):
    child = answer(client, canvas, fake_answer)
    run_merge(client, canvas, child, fake_answer)
    response = client.put(
        f"/api/canvases/{canvas['id']}/boxes/b1/body", json={"markdown": "# Rewritten\n"}
    )
    assert response.json()["detail"] == EDIT_WHILE_MERGING_MESSAGE


def test_should_still_edit_a_parent_once_the_merge_is_gone(client, canvas, fake_answer):
    child = answer(client, canvas, fake_answer)
    run_merge(client, canvas, child, fake_answer)
    client.delete(f"/api/canvases/{canvas['id']}/boxes/{child}/merge")
    response = client.put(
        f"/api/canvases/{canvas['id']}/boxes/b1/body", json={"markdown": "# Rewritten\n"}
    )
    assert response.status_code == 200


def test_should_list_a_waiting_merge_on_the_canvas(client, canvas, fake_answer):
    child = answer(client, canvas, fake_answer)
    run_merge(client, canvas, child, fake_answer)
    assert client.get(f"/api/canvases/{canvas['id']}").json()["merges"] == [child]


def test_should_list_no_merge_on_an_untouched_canvas(client, canvas):
    assert client.get(f"/api/canvases/{canvas['id']}").json()["merges"] == []


def test_should_drop_the_proposal_when_the_child_is_deleted(client, canvas, fake_answer):
    child = answer(client, canvas, fake_answer)
    run_merge(client, canvas, child, fake_answer)
    client.delete(f"/api/canvases/{canvas['id']}/boxes/{child}")
    assert client.get(f"/api/canvases/{canvas['id']}").json()["merges"] == []


# --- helpers ------------------------------------------------------------------


def _reviewed(client, canvas, fake_answer) -> list[dict]:
    child = answer(client, canvas, fake_answer)
    run_merge(client, canvas, child, fake_answer)
    return client.get(f"/api/canvases/{canvas['id']}/boxes/{child}/merge").json()["changes"]


def _proposed(client, canvas, child) -> str:
    return client.get(f"/api/canvases/{canvas['id']}/boxes/{child}/merge").json()["proposed"]


def _parent_markdown(client, canvas) -> str:
    return client.get(f"/api/canvases/{canvas['id']}/boxes/b1/body").json()["markdown"]
