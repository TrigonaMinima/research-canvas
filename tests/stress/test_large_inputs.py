"""The biggest inputs the app is meant to take, and one past the picture cap."""

from __future__ import annotations

import time

from research_canvas import context, storage
from research_canvas.config import (
    IMPORT_BUDGET_MS,
    MAX_IMAGE_BYTES,
    PROMPT_BUILD_BUDGET_MS,
    STRESS_CANVASES,
    STRESS_TREE_DEPTH,
)
from tests.fixtures.big_canvas import WORDS, big_markdown
from tests.fixtures.images import PNG


def _timed_ms(call):
    began = time.perf_counter()
    result = call()
    return result, (time.perf_counter() - began) * 1000


# --- a paste at the release size ----------------------------------------------
# There is no paste cap. The PRD's 20,000-word document is the largest the app promises
# to hold, so that is the size these run at.


def test_should_import_a_paste_of_the_release_size(client):
    response = client.post("/api/canvases", json={"markdown": big_markdown(WORDS, 0)})
    assert response.status_code == 201


def test_should_import_a_paste_of_the_release_size_within_budget(client):
    _, took = _timed_ms(
        lambda: client.post("/api/canvases", json={"markdown": big_markdown(WORDS, 0)})
    )
    assert took < IMPORT_BUDGET_MS


def test_should_keep_every_word_of_a_paste_of_the_release_size(client):
    markdown = big_markdown(WORDS, 0)
    canvas = client.post("/api/canvases", json={"markdown": markdown}).json()
    saved = client.get(f"/api/canvases/{canvas['id']}/boxes/b1/body").json()["markdown"]
    assert saved == markdown


# --- a picture at the cap -----------------------------------------------------


def _picture(size: int) -> bytes:
    # Trailing bytes after IEND: the sniff reads the magic number, the cap reads the length.
    return PNG + b"\x00" * (size - len(PNG))


def test_should_keep_a_picture_of_exactly_the_cap(client, canvas):
    response = client.post(
        f"/api/canvases/{canvas['id']}/assets", content=_picture(MAX_IMAGE_BYTES)
    )
    assert response.status_code == 201


def test_should_refuse_a_picture_one_byte_over_the_cap(client, canvas):
    response = client.post(
        f"/api/canvases/{canvas['id']}/assets", content=_picture(MAX_IMAGE_BYTES + 1)
    )
    assert response.status_code == 413


def test_should_store_every_byte_of_a_picture_of_exactly_the_cap(client, canvas):
    data = _picture(MAX_IMAGE_BYTES)
    path = client.post(f"/api/canvases/{canvas['id']}/assets", content=data).json()["path"]
    assert client.get(f"/api/canvases/{canvas['id']}/{path}").content == data


# --- hundreds of canvases -----------------------------------------------------


def _many_canvases(sample_markdown) -> set[str]:
    return {storage.create_canvas(sample_markdown).id for _ in range(STRESS_CANVASES)}


def test_should_list_every_one_of_hundreds_of_canvases(client, sample_markdown):
    made = _many_canvases(sample_markdown)
    listed = {c["id"] for c in client.get("/api/canvases").json()}
    assert listed == made


# --- a deep tree of answers ---------------------------------------------------


def _deep_tree(canvas_root, sample_markdown):
    """A chain of answers STRESS_TREE_DEPTH deep, each one asked from the one above."""
    canvas = storage.create_canvas(sample_markdown)
    parent = canvas.root_id
    for depth in range(1, STRESS_TREE_DEPTH + 1):
        box = storage.add_answer(canvas, parent_id=parent, question=f"Question {depth}?")
        box.status = "done"
        storage.write_body(canvas.id, box.id, f"Answer at depth {depth}. " * 40)
        parent = box.id
    deepest = storage.add_answer(canvas, parent_id=parent, question="And the last one?")
    storage.save(canvas)
    return canvas, deepest


def test_should_send_every_ancestor_in_a_deep_tree(canvas_root, sample_markdown):
    canvas, deepest = _deep_tree(canvas_root, sample_markdown)
    prompt = context.build_prompt(canvas, deepest)
    assert prompt.count("## An earlier question at depth") == STRESS_TREE_DEPTH


def test_should_build_the_prompt_of_a_deep_tree_within_budget(canvas_root, sample_markdown):
    canvas, deepest = _deep_tree(canvas_root, sample_markdown)
    _, took = _timed_ms(lambda: context.build_prompt(canvas, deepest))
    assert took < PROMPT_BUILD_BUDGET_MS


def test_should_stream_an_answer_at_the_bottom_of_a_deep_tree(
    client, canvas_root, sample_markdown, fake_answer
):
    canvas, deepest = _deep_tree(canvas_root, sample_markdown)
    fake_answer([fake_answer.Event(kind="text", text="Deep."), fake_answer.Event(kind="done")])
    client.get(f"/api/canvases/{canvas.id}/boxes/{deepest.id}/stream")
    assert storage.load(canvas.id).box(deepest.id).status == "done"
