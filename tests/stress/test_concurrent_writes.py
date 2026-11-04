"""Many writers on one canvas at once. The per-canvas lock is all that keeps every change.

Without it, two writers load the same canvas.json, change different things, and the
second save drops the first change. These tests fail the moment the lock goes away.
"""

from __future__ import annotations

from research_canvas import storage
from research_canvas.config import STRESS_WRITERS, STRESS_WRITES_PER_WRITER
from tests.stress.conftest import all_at_once


def test_should_keep_every_change_when_threads_edit_one_canvas_at_once(
    canvas_root, sample_markdown
):
    canvas = storage.create_canvas(sample_markdown)

    def bump(_):
        for _ in range(STRESS_WRITES_PER_WRITER):
            with storage.edit(canvas.id) as held:
                held.camera.tx += 1

    all_at_once(bump, STRESS_WRITERS)

    assert storage.load(canvas.id).camera.tx == STRESS_WRITERS * STRESS_WRITES_PER_WRITER


def _many_boxes(client, canvas) -> list[str]:
    ask = {"boxId": "b1", "question": "Why?", "x": 900, "y": 0}
    return [
        client.post(f"/api/canvases/{canvas['id']}/ask", json=ask).json()["box"]["id"]
        for _ in range(STRESS_WRITERS)
    ]


def test_should_keep_every_box_move_when_patches_race(client, canvas):
    boxes = _many_boxes(client, canvas)

    def move(i):
        patch = {"boxes": {boxes[i]: {"x": 1000.0 + i}}}
        return client.patch(f"/api/canvases/{canvas['id']}", json=patch).status_code

    all_at_once(move, len(boxes))

    saved = {b["id"]: b["x"] for b in client.get(f"/api/canvases/{canvas['id']}").json()["boxes"]}
    assert [saved[box] for box in boxes] == [1000.0 + i for i in range(len(boxes))]


def test_should_answer_every_racing_patch_with_200(client, canvas):
    boxes = _many_boxes(client, canvas)

    def move(i):
        patch = {"boxes": {boxes[i]: {"y": float(i)}}}
        return client.patch(f"/api/canvases/{canvas['id']}", json=patch).status_code

    assert set(all_at_once(move, len(boxes))) == {200}


def test_should_never_show_a_reader_a_half_written_canvas(client, canvas):
    # Readers do not take the lock. Only the atomic replace keeps them off a torn file.
    url = f"/api/canvases/{canvas['id']}"

    def read_or_write(i):
        codes = set()
        for n in range(STRESS_WRITES_PER_WRITER):
            if i % 2:
                codes.add(client.patch(url, json={"camera": {"tx": float(n)}}).status_code)
            else:
                codes.add(client.get(url).status_code)
        return codes

    assert set().union(*all_at_once(read_or_write, STRESS_WRITERS)) == {200}
