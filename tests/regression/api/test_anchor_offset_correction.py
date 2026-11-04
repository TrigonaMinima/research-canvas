"""The API stores the offset the browser corrected after an edit."""

# Guards 662ef1d (fix: follow a passage's offset through an edit).

from __future__ import annotations


def _ask() -> dict:
    return {
        "boxId": "b1",
        "question": "Why self-attention?",
        "x": 500,
        "y": 0,
        "anchor": {"start": 4, "end": 15, "quote": "Transformer"},
    }


# --- an offset corrected after an edit ----------------------------------------
#
# An anchor keeps the offset of its quote. Editing the document moves the text, and
# only the browser can say where to: offsets are measured against the rendered plain
# text of a body, which is the browser's own projection. It sends the new numbers here.


def _anchored(client, canvas) -> str:
    """One answer off "Transformer", and the id of the anchor that opened it."""
    asked = client.post(f"/api/canvases/{canvas['id']}/ask", json=_ask()).json()
    return asked["anchor"]["id"]


def _anchor_of(client, canvas, anchor_id: str) -> dict:
    view = client.get(f"/api/canvases/{canvas['id']}").json()
    return next(a for a in view["anchors"] if a["id"] == anchor_id)


def test_should_save_a_corrected_anchor_offset(client, canvas):
    anchor_id = _anchored(client, canvas)
    client.patch(
        f"/api/canvases/{canvas['id']}", json={"anchors": {anchor_id: {"start": 90, "end": 101}}}
    )
    corrected = _anchor_of(client, canvas, anchor_id)
    assert (corrected["start"], corrected["end"]) == (90, 101)


def test_should_keep_the_quote_when_an_offset_is_corrected(client, canvas):
    """The quote is what finds the passage next time. Only the numbers move."""
    anchor_id = _anchored(client, canvas)
    client.patch(
        f"/api/canvases/{canvas['id']}", json={"anchors": {anchor_id: {"start": 90, "end": 101}}}
    )
    assert _anchor_of(client, canvas, anchor_id)["quote"] == "Transformer"


def test_should_ignore_a_correction_for_an_anchor_that_is_gone(client, canvas):
    """A box deleted in one tab while another was still rendering it."""
    _anchored(client, canvas)
    response = client.patch(
        f"/api/canvases/{canvas['id']}", json={"anchors": {"a9": {"start": 5, "end": 9}}}
    )
    assert response.status_code == 200


def test_should_refuse_a_negative_anchor_offset(client, canvas):
    anchor_id = _anchored(client, canvas)
    response = client.patch(
        f"/api/canvases/{canvas['id']}", json={"anchors": {anchor_id: {"start": -1, "end": 9}}}
    )
    assert response.status_code == 422
