"""Layer 8: the small validation edges of the API (#52).

Two of these are decisions, not bugs. A PATCH naming a box that is gone is ignored, like
a correction for a gone anchor, because a layout patch can race a delete and a 404 would
drop the camera move riding with it. A DELETE of a box that is gone answers 200 with the
view, because a delete must be safe to repeat.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from research_canvas import config, storage
from research_canvas.config import BOX_DIR


def _ask(client, canvas_id: str, box_id: str = "b1") -> str:
    body = {"boxId": box_id, "question": "Why self-attention?", "x": 900, "y": 0}
    return client.post(f"/api/canvases/{canvas_id}/ask", json=body).json()["box"]["id"]


def _answered(client, canvas, fake_answer, box_id: str = "b1") -> str:
    event = fake_answer.Event
    fake_answer([event(kind="text", text="It is parallel."), event(kind="done")])
    asked = _ask(client, canvas["id"], box_id)
    client.get(f"/api/canvases/{canvas['id']}/boxes/{asked}/stream")
    return asked


# --- PATCH --------------------------------------------------------------------


def test_should_accept_a_patch_for_a_box_that_is_gone(client, canvas):
    response = client.patch(f"/api/canvases/{canvas['id']}", json={"boxes": {"b9": {"x": 5}}})
    assert response.status_code == 200


def test_should_not_create_a_box_from_a_patch_for_one_that_is_gone(client, canvas):
    client.patch(f"/api/canvases/{canvas['id']}", json={"boxes": {"b9": {"x": 5}}})
    view = client.get(f"/api/canvases/{canvas['id']}").json()
    assert [b["id"] for b in view["boxes"]] == ["b1"]


def test_should_keep_the_rest_of_a_patch_that_names_a_gone_box(client, canvas):
    patch = {"camera": {"tx": 42}, "boxes": {"b9": {"x": 5}}}
    client.patch(f"/api/canvases/{canvas['id']}", json=patch)
    assert client.get(f"/api/canvases/{canvas['id']}").json()["camera"]["tx"] == 42


def test_should_ignore_a_theme_that_is_neither_light_nor_dark(client, canvas):
    client.patch(f"/api/canvases/{canvas['id']}", json={"theme": "purple"})
    assert client.get(f"/api/canvases/{canvas['id']}").json()["theme"] == "light"


def test_should_accept_a_patch_with_a_theme_it_ignores(client, canvas):
    response = client.patch(f"/api/canvases/{canvas['id']}", json={"theme": "purple"})
    assert response.status_code == 200


# --- asking -------------------------------------------------------------------


def test_should_404_a_question_asked_from_a_box_that_is_gone(client, canvas):
    body = {"boxId": "b9", "question": "Why?", "x": 0, "y": 0}
    response = client.post(f"/api/canvases/{canvas['id']}/ask", json=body)
    assert response.status_code == 404


def test_should_say_no_such_box_for_a_question_asked_from_a_box_that_is_gone(client, canvas):
    body = {"boxId": "b9", "question": "Why?", "x": 0, "y": 0}
    response = client.post(f"/api/canvases/{canvas['id']}/ask", json=body)
    assert response.json()["detail"] == "No such box."


# --- DELETE -------------------------------------------------------------------


def test_should_answer_200_to_deleting_a_box_that_is_gone(client, canvas):
    assert client.delete(f"/api/canvases/{canvas['id']}/boxes/b9").status_code == 200


def test_should_leave_the_canvas_alone_when_deleting_a_box_that_is_gone(client, canvas):
    before = client.get(f"/api/canvases/{canvas['id']}").json()["boxes"]
    client.delete(f"/api/canvases/{canvas['id']}/boxes/b9")
    assert client.get(f"/api/canvases/{canvas['id']}").json()["boxes"] == before


@pytest.fixture
def family(client, canvas, fake_answer):
    """b2 asked from the document, b3 asked from b2, then b2 deleted."""
    child = _answered(client, canvas, fake_answer)
    grandchild = _answered(client, canvas, fake_answer, box_id=child)
    client.delete(f"/api/canvases/{canvas['id']}/boxes/{child}")
    return canvas, child, grandchild


def test_should_delete_the_answers_asked_below_a_deleted_box(client, family):
    canvas, _, _ = family
    view = client.get(f"/api/canvases/{canvas['id']}").json()
    assert [b["id"] for b in view["boxes"]] == ["b1"]


def test_should_delete_the_files_of_the_answers_below_a_deleted_box(client, family, canvas_root):
    canvas, _, grandchild = family
    assert not (canvas_root / canvas["id"] / BOX_DIR / f"{grandchild}.md").exists()


def test_should_delete_the_anchors_of_the_answers_below_a_deleted_box(client, family):
    canvas, _, _ = family
    assert client.get(f"/api/canvases/{canvas['id']}").json()["anchors"] == []


# --- 999 canvases with one title ----------------------------------------------


@pytest.fixture
def full_title(canvas_root):
    """Every folder name one title can take, already used."""
    stem = f"{datetime.now(UTC):%Y-%m-%d}-python-releases"
    (canvas_root / stem).mkdir()
    for n in range(2, 1000):
        (canvas_root / f"{stem}-{n}").mkdir()


def test_should_refuse_a_canvas_once_its_title_has_no_folder_name_left(full_title):
    with pytest.raises(storage.ImportRefused, match=config.TOO_MANY_TITLES_MESSAGE):
        storage.create_canvas("# Python releases\n\nlong enough to be a document at all.")


def test_should_say_why_a_pasted_canvas_with_no_folder_name_left_is_refused(client, full_title):
    body = {"markdown": "# Python releases\n\nlong enough to be a document at all."}
    response = client.post("/api/canvases", json=body)
    assert response.json()["detail"] == config.TOO_MANY_TITLES_MESSAGE


def test_should_say_why_research_with_no_folder_name_left_is_refused(client, full_title):
    body = {"topic": "python releases", "prompt": "Find the latest stable release."}
    response = client.post("/api/research", json=body)
    assert response.json()["detail"] == config.TOO_MANY_TITLES_MESSAGE
