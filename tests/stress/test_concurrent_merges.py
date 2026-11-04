"""Merges racing each other, and asks racing merges, on one canvas."""

from __future__ import annotations

import json

from research_canvas import storage
from research_canvas.config import STRESS_ROUNDS
from tests.fixtures.merging import EDITS, answer, ask_body, open_merge
from tests.stress.conftest import all_at_once

# One change for the root and one for an answer, so a merge into either parent finds
# something to place.
INTO_ANSWER = {"why": "says how", "find": "It is parallel.", "replace": "It runs in parallel."}
CHUNKS = [json.dumps(EDITS[0]) + "\n", json.dumps(INTO_ANSWER) + "\n"]


def _drive(fake_answer) -> None:
    event = fake_answer.Event
    fake_answer(
        [event(kind="init", tools=[])]
        + [event(kind="text", text=chunk) for chunk in CHUNKS]
        + [event(kind="done")]
    )


def test_should_let_one_of_two_racing_merges_into_one_parent_win(client, canvas, fake_answer):
    outcomes = []
    for _ in range(STRESS_ROUNDS):
        pair = [answer(client, canvas, fake_answer), answer(client, canvas, fake_answer)]
        codes = all_at_once(lambda i, pair=pair: open_merge(client, canvas, pair[i]).status_code, 2)
        outcomes.append(sorted(codes))
        for child in pair:
            client.delete(f"/api/canvases/{canvas['id']}/boxes/{child}/merge")
    assert outcomes == [[200, 409]] * STRESS_ROUNDS


def test_should_leave_one_proposal_after_racing_merges_into_one_parent(client, canvas, fake_answer):
    pair = [answer(client, canvas, fake_answer), answer(client, canvas, fake_answer)]
    all_at_once(lambda i: open_merge(client, canvas, pair[i]), 2)
    assert len(storage.list_merges(canvas["id"])) == 1


def _two_merges_running(client, canvas, fake_answer) -> list[str]:
    """A merge into the root and one into an answer, both streamed at the same moment."""
    first = answer(client, canvas, fake_answer)
    second = answer(client, canvas, fake_answer, box_id=first, quote="parallel")
    pair = [first, second]
    for child in pair:
        open_merge(client, canvas, child)
    _drive(fake_answer)
    all_at_once(
        lambda i: client.get(f"/api/canvases/{canvas['id']}/boxes/{pair[i]}/merge/stream"), 2
    )
    return pair


def test_should_finish_two_merges_streaming_on_one_canvas(client, canvas, fake_answer):
    pair = _two_merges_running(client, canvas, fake_answer)
    reviews = [client.get(f"/api/canvases/{canvas['id']}/boxes/{c}/merge").json() for c in pair]
    assert [review["status"] for review in reviews] == ["done", "done"]


def test_should_land_both_merges_accepted_at_once(client, canvas, fake_answer):
    pair = _two_merges_running(client, canvas, fake_answer)
    url = f"/api/canvases/{canvas['id']}/boxes/{{}}/merge/accept"
    all_at_once(lambda i: client.post(url.format(pair[i]), json={}), 2)
    boxes = {b["id"]: b for b in client.get(f"/api/canvases/{canvas['id']}").json()["boxes"]}
    assert [boxes[child]["merged"] for child in pair] == [True, True]


def test_should_keep_an_ask_that_races_an_accepted_merge(client, canvas, fake_answer):
    kept = []
    for _ in range(STRESS_ROUNDS):
        child = answer(client, canvas, fake_answer)
        open_merge(client, canvas, child)
        _drive(fake_answer)
        client.get(f"/api/canvases/{canvas['id']}/boxes/{child}/merge/stream")

        def ask_or_accept(i, child=child):
            if i:
                return client.post(
                    f"/api/canvases/{canvas['id']}/boxes/{child}/merge/accept", json={}
                ).json()
            return client.post(f"/api/canvases/{canvas['id']}/ask", json=ask_body()).json()

        asked, _ = all_at_once(ask_or_accept, 2)
        boxes = {b["id"]: b for b in client.get(f"/api/canvases/{canvas['id']}").json()["boxes"]}
        kept.append(asked["box"]["id"] in boxes and boxes[child]["merged"])
    assert kept == [True] * STRESS_ROUNDS
