"""The disk is the database (#50). A bad file costs that one canvas, never the list.

Each test breaks one file the way a crash, a hand edit, or a full disk would, then asks
the API for what the reader would ask for next.
"""

from __future__ import annotations

import errno
import json

import pytest

from research_canvas import config, storage
from research_canvas.config import (
    BOX_DIR,
    CANVAS_FILE,
    INSTRUCTIONS_FILE,
    PRESETS_FILE,
    PRESETS_UNREADABLE_MESSAGE,
    RESEARCH_FILE,
    ROOT_DOC_FILE,
)

BRIEF = {"topic": "python releases", "prompt": "Find the latest stable release."}


def _ask(client, canvas_id: str) -> str:
    body = {"boxId": "b1", "question": "Why self-attention?", "x": 900, "y": 0}
    return client.post(f"/api/canvases/{canvas_id}/ask", json=body).json()["box"]["id"]


def _answered(client, canvas, fake_answer) -> str:
    event = fake_answer.Event
    fake_answer([event(kind="text", text="It is parallel."), event(kind="done")])
    box_id = _ask(client, canvas["id"])
    client.get(f"/api/canvases/{canvas['id']}/boxes/{box_id}/stream")
    return box_id


def _rewrite_canvas_json(canvas_root, canvas_id: str, change) -> None:
    path = canvas_root / canvas_id / CANVAS_FILE
    data = json.loads(path.read_text(encoding="utf-8"))
    change(data)
    path.write_text(json.dumps(data), encoding="utf-8")


@pytest.fixture
def second(client, sample_markdown):
    """A healthy canvas beside the broken one, which the list must still show."""
    return client.post("/api/canvases", json={"markdown": sample_markdown}).json()


@pytest.fixture
def research(client):
    return client.post("/api/research", json=BRIEF).json()


# --- canvas.json --------------------------------------------------------------


def test_should_still_list_the_other_canvases_when_one_is_missing_a_key(
    client, canvas, second, canvas_root
):
    _rewrite_canvas_json(canvas_root, canvas["id"], lambda data: data.pop("anchors"))
    listed = [c["id"] for c in client.get("/api/canvases").json()]
    assert listed == [second["id"]]


def test_should_404_a_canvas_that_is_missing_a_key(client, canvas, canvas_root):
    _rewrite_canvas_json(canvas_root, canvas["id"], lambda data: data.pop("camera"))
    assert client.get(f"/api/canvases/{canvas['id']}").status_code == 404


def test_should_404_a_canvas_whose_box_is_missing_a_key(client, canvas, canvas_root):
    _rewrite_canvas_json(canvas_root, canvas["id"], lambda data: data["boxes"][0].pop("kind"))
    assert client.get(f"/api/canvases/{canvas['id']}").status_code == 404


def test_should_still_list_the_other_canvases_when_one_has_a_bad_date(
    client, canvas, second, canvas_root
):
    # A non-string date used to break the sort for every canvas, not just this one.
    _rewrite_canvas_json(canvas_root, canvas["id"], lambda data: data.update(updatedAt=None))
    listed = [c["id"] for c in client.get("/api/canvases").json()]
    assert listed == [second["id"]]


def test_should_still_list_the_other_canvases_when_one_does_not_parse(
    client, canvas, second, canvas_root
):
    (canvas_root / canvas["id"] / CANVAS_FILE).write_text("{ not json", encoding="utf-8")
    listed = [c["id"] for c in client.get("/api/canvases").json()]
    assert listed == [second["id"]]


def test_should_404_a_canvas_that_does_not_parse(client, canvas, canvas_root):
    (canvas_root / canvas["id"] / CANVAS_FILE).write_text("{ not json", encoding="utf-8")
    assert client.get(f"/api/canvases/{canvas['id']}").status_code == 404


def test_should_404_a_canvas_json_that_is_not_utf8(client, canvas, canvas_root):
    (canvas_root / canvas["id"] / CANVAS_FILE).write_bytes(b'{"id": "\xff\xfe"}')
    assert client.get(f"/api/canvases/{canvas['id']}").status_code == 404


# --- bodies -------------------------------------------------------------------


def test_should_open_a_canvas_whose_body_is_not_utf8(client, canvas, canvas_root):
    (canvas_root / canvas["id"] / ROOT_DOC_FILE).write_bytes(b"# Kept\n\nbad \xff byte\n")
    assert client.get(f"/api/canvases/{canvas['id']}").status_code == 200


def test_should_keep_the_readable_text_of_a_body_that_is_not_utf8(client, canvas, canvas_root):
    (canvas_root / canvas["id"] / ROOT_DOC_FILE).write_bytes(b"# Kept\n\nbad \xff byte\n")
    body = client.get(f"/api/canvases/{canvas['id']}/boxes/b1/body").json()["markdown"]
    assert body == "# Kept\n\nbad � byte\n"


def test_should_mark_a_finished_answer_failed_when_its_file_is_gone(
    client, canvas, fake_answer, canvas_root
):
    box_id = _answered(client, canvas, fake_answer)
    (canvas_root / canvas["id"] / BOX_DIR / f"{box_id}.md").unlink()
    view = client.get(f"/api/canvases/{canvas['id']}").json()
    assert next(b for b in view["boxes"] if b["id"] == box_id)["status"] == "failed"


def test_should_say_why_a_finished_answer_with_no_file_failed(
    client, canvas, fake_answer, canvas_root
):
    box_id = _answered(client, canvas, fake_answer)
    (canvas_root / canvas["id"] / BOX_DIR / f"{box_id}.md").unlink()
    view = client.get(f"/api/canvases/{canvas['id']}").json()
    reason = next(b for b in view["boxes"] if b["id"] == box_id)["reason"]
    assert reason == config.BODY_MISSING_REASON


def test_should_mark_the_document_failed_when_its_file_is_gone(client, canvas, canvas_root):
    (canvas_root / canvas["id"] / ROOT_DOC_FILE).unlink()
    view = client.get(f"/api/canvases/{canvas['id']}").json()
    assert view["boxes"][0]["status"] == "failed"


def test_should_not_touch_the_disk_when_it_finds_a_body_gone(client, canvas, canvas_root):
    (canvas_root / canvas["id"] / ROOT_DOC_FILE).unlink()
    before = (canvas_root / canvas["id"] / CANVAS_FILE).read_text(encoding="utf-8")
    client.get(f"/api/canvases/{canvas['id']}")
    assert (canvas_root / canvas["id"] / CANVAS_FILE).read_text(encoding="utf-8") == before


def test_should_leave_an_unfinished_answer_with_no_file_alone(client, canvas):
    # No file yet is normal: a run writes its body only when it ends.
    box_id = _ask(client, canvas["id"])
    view = client.get(f"/api/canvases/{canvas['id']}").json()
    assert next(b for b in view["boxes"] if b["id"] == box_id)["reason"] == (
        storage.INTERRUPTED_REASON
    )


# --- research.json ------------------------------------------------------------


def test_should_refuse_to_stream_research_whose_file_does_not_parse(client, research, canvas_root):
    (canvas_root / research["id"] / RESEARCH_FILE).write_text("{ not json", encoding="utf-8")
    response = client.get(f"/api/canvases/{research['id']}/boxes/b1/stream")
    assert response.status_code == 422


def test_should_say_why_research_whose_file_does_not_parse_cannot_stream(
    client, research, canvas_root
):
    (canvas_root / research["id"] / RESEARCH_FILE).write_text("{ not json", encoding="utf-8")
    response = client.get(f"/api/canvases/{research['id']}/boxes/b1/stream")
    assert response.json()["detail"] == config.RESEARCH_UNREADABLE_MESSAGE


def test_should_refuse_to_stream_research_whose_file_has_no_topic(client, research, canvas_root):
    (canvas_root / research["id"] / RESEARCH_FILE).write_text('{"prompt": "x"}', encoding="utf-8")
    response = client.get(f"/api/canvases/{research['id']}/boxes/b1/stream")
    assert response.json()["detail"] == config.RESEARCH_UNREADABLE_MESSAGE


def test_should_say_why_research_whose_file_does_not_parse_cannot_be_retried(
    client, research, canvas_root
):
    # Not "a pasted document has no run": the canvas was researched, its file broke.
    (canvas_root / research["id"] / RESEARCH_FILE).write_text("{ not json", encoding="utf-8")
    response = client.post(f"/api/canvases/{research['id']}/boxes/b1/retry")
    assert response.json()["detail"] == config.RESEARCH_UNREADABLE_MESSAGE


def test_should_keep_a_broken_research_file_as_it_was_after_a_refused_retry(
    client, research, canvas_root
):
    path = canvas_root / research["id"] / RESEARCH_FILE
    path.write_text("{ not json", encoding="utf-8")
    client.post(f"/api/canvases/{research['id']}/boxes/b1/retry")
    assert path.read_text(encoding="utf-8") == "{ not json"


def test_should_open_a_canvas_whose_research_file_does_not_parse(client, research, canvas_root):
    (canvas_root / research["id"] / RESEARCH_FILE).write_text("{ not json", encoding="utf-8")
    assert client.get(f"/api/canvases/{research['id']}").status_code == 200


# --- presets.json -------------------------------------------------------------


def test_should_refuse_presets_with_no_presets_key(client, canvas_root):
    (canvas_root / PRESETS_FILE).write_text('{"chips": []}', encoding="utf-8")
    assert client.get("/api/presets").json()["detail"] == PRESETS_UNREADABLE_MESSAGE


def test_should_refuse_presets_written_as_a_bare_list(client, canvas_root):
    (canvas_root / PRESETS_FILE).write_text('[{"label": "a", "question": "b"}]', encoding="utf-8")
    assert client.get("/api/presets").status_code == 422


def test_should_say_why_presets_written_as_a_bare_list_are_refused(client, canvas_root):
    (canvas_root / PRESETS_FILE).write_text('[{"label": "a", "question": "b"}]', encoding="utf-8")
    assert client.get("/api/presets").json()["detail"] == PRESETS_UNREADABLE_MESSAGE


def test_should_refuse_presets_that_are_not_utf8(client, canvas_root):
    (canvas_root / PRESETS_FILE).write_bytes(b'{"presets": ["\xff"]}')
    assert client.get("/api/presets").json()["detail"] == PRESETS_UNREADABLE_MESSAGE


# --- instructions.md ----------------------------------------------------------


@pytest.fixture
def instructions_folder(canvas_root):
    (canvas_root / INSTRUCTIONS_FILE).mkdir()


def test_should_refuse_to_read_instructions_that_are_a_folder(client, instructions_folder):
    assert client.get("/api/instructions").status_code == 422


def test_should_say_why_instructions_that_are_a_folder_cannot_be_read(client, instructions_folder):
    detail = client.get("/api/instructions").json()["detail"]
    assert detail == config.INSTRUCTIONS_UNREADABLE_MESSAGE


def test_should_say_why_an_answer_cannot_run_without_its_instructions(
    client, canvas, instructions_folder
):
    box_id = _ask(client, canvas["id"])
    response = client.get(f"/api/canvases/{canvas['id']}/boxes/{box_id}/stream")
    assert response.json()["detail"] == config.INSTRUCTIONS_UNREADABLE_MESSAGE


def test_should_say_why_a_brief_cannot_be_drafted_without_its_instructions(
    client, instructions_folder
):
    response = client.get("/api/research/expand", params={"topic": "python releases"})
    assert response.json()["detail"] == config.INSTRUCTIONS_UNREADABLE_MESSAGE


# --- a save that fails --------------------------------------------------------


@pytest.fixture
def disk_full(monkeypatch):
    def refuse(*_args, **_kwargs):
        raise OSError(errno.ENOSPC, "No space left on device")

    # Under the atomic write, so the real temp-file cleanup and error path run.
    monkeypatch.setattr(storage.os, "replace", refuse)


def test_should_answer_a_save_on_a_full_disk_with_json(client, canvas, disk_full):
    response = client.put(f"/api/canvases/{canvas['id']}/boxes/b1/body", json={"markdown": "x"})
    assert response.json()["detail"] == config.SAVE_FAILED_MESSAGE


def test_should_answer_a_save_on_a_full_disk_with_a_server_fault(client, canvas, disk_full):
    response = client.put(f"/api/canvases/{canvas['id']}/boxes/b1/body", json={"markdown": "x"})
    assert response.status_code == 507


def test_should_keep_the_old_body_when_a_save_hits_a_full_disk(
    client, canvas, canvas_root, disk_full
):
    path = canvas_root / canvas["id"] / ROOT_DOC_FILE
    before = path.read_text(encoding="utf-8")
    client.put(f"/api/canvases/{canvas['id']}/boxes/b1/body", json={"markdown": "x"})
    assert path.read_text(encoding="utf-8") == before


def test_should_leave_no_temp_file_behind_a_save_on_a_full_disk(
    client, canvas, disk_full, canvas_root
):
    client.put(f"/api/canvases/{canvas['id']}/boxes/b1/body", json={"markdown": "x"})
    assert not list((canvas_root / canvas["id"]).glob(".*.tmp"))
