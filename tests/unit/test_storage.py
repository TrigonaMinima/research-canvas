"""Layer 6: persistence. US-18 says every change survives a restart."""

from __future__ import annotations

import json

import pytest

from research_canvas import storage
from research_canvas.config import FORMAT_VERSION, MAX_BOX_WIDTH, MIN_BOX_WIDTH, ROOT_BOX_WIDTH


def test_should_use_first_heading_as_title(canvas_root, sample_markdown):
    canvas = storage.create_canvas(sample_markdown)
    assert canvas.title == "Attention Is All You Need"


def test_should_title_untitled_when_no_heading(canvas_root):
    canvas = storage.create_canvas("just some prose with no heading at all, long enough")
    assert canvas.title == "Untitled"


def test_should_refuse_paste_shorter_than_the_minimum(canvas_root):
    with pytest.raises(storage.ImportRefused):
        storage.create_canvas("too short")


def test_should_write_the_document_verbatim(canvas_root, sample_markdown):
    canvas = storage.create_canvas(sample_markdown)
    assert storage.read_body(canvas.id, canvas.root_id) == sample_markdown


def test_should_stamp_the_format_version(canvas_root, sample_markdown):
    canvas = storage.create_canvas(sample_markdown)
    on_disk = json.loads((canvas_root / canvas.id / "canvas.json").read_text())
    assert on_disk["formatVersion"] == FORMAT_VERSION


def test_should_give_colliding_titles_distinct_ids(canvas_root, sample_markdown):
    first = storage.create_canvas(sample_markdown)
    second = storage.create_canvas(sample_markdown)
    assert first.id != second.id


def test_should_round_trip_a_canvas_through_disk(canvas_root, sample_markdown):
    canvas = storage.create_canvas(sample_markdown)
    canvas.camera = storage.Camera(tx=-120.5, ty=44.0, scale=0.75)
    storage.save(canvas)
    assert storage.load(canvas.id).camera.scale == 0.75


def test_should_keep_answer_bodies_in_their_own_files(canvas_root, sample_markdown):
    canvas = storage.create_canvas(sample_markdown)
    box = storage.add_answer(canvas, parent_id=canvas.root_id, question="Why self-attention?")
    storage.write_body(canvas.id, box.id, "Because it is parallel.")
    assert (canvas_root / canvas.id / "boxes" / f"{box.id}.md").read_text() == (
        "Because it is parallel."
    )


def test_should_nest_depth_under_the_parent(canvas_root, sample_markdown):
    canvas = storage.create_canvas(sample_markdown)
    first = storage.add_answer(canvas, parent_id=canvas.root_id, question="a")
    second = storage.add_answer(canvas, parent_id=first.id, question="b")
    assert second.depth == 2


def test_should_list_canvases_newest_first(canvas_root, sample_markdown):
    older = storage.create_canvas(sample_markdown)
    newer = storage.create_canvas("# Second Paper\n\n" + sample_markdown)
    storage.save(storage.load(newer.id))
    listed = [c.id for c in storage.list_canvases()]
    assert listed.index(newer.id) < listed.index(older.id)


def test_should_mark_running_boxes_interrupted_on_load(canvas_root, sample_markdown):
    """A force-quit leaves 'running' on disk. Reopening must surface it, not resume it."""
    canvas = storage.create_canvas(sample_markdown)
    box = storage.add_answer(canvas, parent_id=canvas.root_id, question="a")
    box.status = "running"
    storage.save(canvas)
    assert storage.load(canvas.id).box(box.id).status == "interrupted"


def test_should_leave_no_partial_file_when_a_save_fails(canvas_root, sample_markdown, monkeypatch):
    canvas = storage.create_canvas(sample_markdown)
    good = (canvas_root / canvas.id / "canvas.json").read_text()

    def explode(*_args, **_kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(storage.json, "dumps", explode)
    with pytest.raises(OSError):
        storage.save(canvas)
    assert (canvas_root / canvas.id / "canvas.json").read_text() == good


def test_should_reject_a_canvas_id_that_escapes_the_root(canvas_root):
    with pytest.raises(storage.CanvasNotFound):
        storage.load("../../etc")


# --- answer width ------------------------------------------------------------


def test_should_give_an_answer_the_width_of_its_parent(canvas_root, sample_markdown):
    canvas = storage.create_canvas(sample_markdown)
    box = storage.add_answer(canvas, parent_id=canvas.root_id, question="Why self-attention?")
    assert box.w == float(ROOT_BOX_WIDTH)


def test_should_clamp_an_inherited_width_to_the_maximum(canvas_root, sample_markdown):
    canvas = storage.create_canvas(sample_markdown)
    canvas.box(canvas.root_id).w = float(MAX_BOX_WIDTH) * 2
    box = storage.add_answer(canvas, parent_id=canvas.root_id, question="a")
    assert box.w == float(MAX_BOX_WIDTH)


def test_should_clamp_an_inherited_width_to_the_minimum(canvas_root, sample_markdown):
    canvas = storage.create_canvas(sample_markdown)
    canvas.box(canvas.root_id).w = 10.0
    box = storage.add_answer(canvas, parent_id=canvas.root_id, question="a")
    assert box.w == float(MIN_BOX_WIDTH)


def test_should_prefer_an_explicit_width_over_the_inherited_one(canvas_root, sample_markdown):
    canvas = storage.create_canvas(sample_markdown)
    box = storage.add_answer(canvas, parent_id=canvas.root_id, question="a", w=320.0)
    assert box.w == 320.0
