"""Layer 6: persistence. US-18 says every change survives a restart."""

from __future__ import annotations

import json

import pytest

from research_canvas import storage
from research_canvas.config import (
    DEFAULT_ASK_PRESETS,
    FORMAT_VERSION,
    INSTRUCTIONS_FILE,
    MAX_BOX_WIDTH,
    MAX_INSTRUCTIONS_CHARS,
    MAX_PRESET_LABEL_CHARS,
    MAX_PRESET_QUESTION_CHARS,
    MAX_PRESETS,
    MIN_BOX_WIDTH,
    PRESETS_FILE,
    ROOT_BOX_WIDTH,
)


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


# --- pinning a box ------------------------------------------------------------


def test_should_start_an_answer_unpinned(canvas_root, sample_markdown):
    canvas = storage.create_canvas(sample_markdown)
    box = storage.add_answer(canvas, parent_id=canvas.root_id, question="a")
    assert box.pinned is False


def test_should_round_trip_a_pinned_box_through_disk(canvas_root, sample_markdown):
    canvas = storage.create_canvas(sample_markdown)
    box = storage.add_answer(canvas, parent_id=canvas.root_id, question="a")
    box.pinned = True
    storage.save(canvas)
    assert storage.load(canvas.id).box(box.id).pinned is True


def test_should_load_a_canvas_saved_before_pinning_existed(canvas_root, sample_markdown):
    """A canvas.json written by an older build has no pinned key at all."""
    canvas = storage.create_canvas(sample_markdown)
    path = canvas_root / canvas.id / "canvas.json"
    data = json.loads(path.read_text())
    del data["boxes"][0]["pinned"]
    path.write_text(json.dumps(data))
    assert storage.load(canvas.id).box(canvas.root_id).pinned is False


# --- collapsible sections -----------------------------------------------------


def test_should_default_sections_to_empty_when_absent(canvas_root, sample_markdown):
    """A canvas.json written by an older build has no sections key at all."""
    canvas = storage.create_canvas(sample_markdown)
    path = canvas_root / canvas.id / "canvas.json"
    data = json.loads(path.read_text())
    data["boxes"][0].pop("sections", None)
    path.write_text(json.dumps(data))
    assert storage.load(canvas.id).box(canvas.root_id).sections == []


def test_should_round_trip_folded_sections(canvas_root, sample_markdown):
    canvas = storage.create_canvas(sample_markdown)
    box = storage.add_answer(canvas, parent_id=canvas.root_id, question="a")
    box.sections = ["model-architecture"]
    storage.save(canvas)
    assert storage.load(canvas.id).box(box.id).sections == ["model-architecture"]


# --- standing instructions ----------------------------------------------------


def test_should_return_empty_instructions_when_the_file_is_missing(canvas_root):
    assert storage.read_instructions() == ""


def test_should_round_trip_the_instructions(canvas_root):
    storage.write_instructions("Answer in British English.")
    assert storage.read_instructions() == "Answer in British English."


def test_should_keep_the_instructions_as_a_plain_file_on_disk(canvas_root):
    storage.write_instructions("Be brief.")
    assert (canvas_root / INSTRUCTIONS_FILE).read_text(encoding="utf-8") == "Be brief."


def test_should_refuse_instructions_over_the_cap(canvas_root):
    with pytest.raises(storage.InstructionsTooLong):
        storage.write_instructions("x" * (MAX_INSTRUCTIONS_CHARS + 1))


def test_should_keep_the_earlier_instructions_when_a_save_is_refused(canvas_root):
    storage.write_instructions("Be brief.")
    with pytest.raises(storage.InstructionsTooLong):
        storage.write_instructions("x" * (MAX_INSTRUCTIONS_CHARS + 1))
    assert storage.read_instructions() == "Be brief."


def test_should_not_list_the_instructions_file_as_a_canvas(canvas_root, sample_markdown):
    storage.create_canvas(sample_markdown)
    storage.write_instructions("Be brief.")
    assert len(storage.list_canvases()) == 1


# --- question chips -----------------------------------------------------------


def test_should_serve_the_default_chips_when_the_file_is_missing(canvas_root):
    assert storage.read_presets() == [dict(p) for p in DEFAULT_ASK_PRESETS]


def test_should_round_trip_the_chips(canvas_root):
    storage.write_presets([{"label": "Explain", "question": "Explain this."}])
    assert storage.read_presets() == [{"label": "Explain", "question": "Explain this."}]


def test_should_keep_the_chips_as_a_plain_json_file_on_disk(canvas_root):
    storage.write_presets([{"label": "Explain", "question": "Explain this."}])
    written = json.loads((canvas_root / PRESETS_FILE).read_text(encoding="utf-8"))
    assert written == {"presets": [{"label": "Explain", "question": "Explain this."}]}


def test_should_store_the_chips_trimmed(canvas_root):
    storage.write_presets([{"label": "  Explain  ", "question": "  Explain this.  "}])
    assert storage.read_presets() == [{"label": "Explain", "question": "Explain this."}]


def test_should_accept_having_no_chips_at_all(canvas_root):
    storage.write_presets([])
    assert storage.read_presets() == []


def test_should_refuse_more_chips_than_the_cap(canvas_root):
    too_many = [{"label": f"C{n}", "question": "Explain this."} for n in range(MAX_PRESETS + 1)]
    with pytest.raises(storage.PresetsInvalid):
        storage.write_presets(too_many)


def test_should_refuse_a_chip_with_a_blank_name(canvas_root):
    with pytest.raises(storage.PresetsInvalid):
        storage.write_presets([{"label": "   ", "question": "Explain this."}])


def test_should_refuse_a_chip_with_a_blank_question(canvas_root):
    with pytest.raises(storage.PresetsInvalid):
        storage.write_presets([{"label": "Explain", "question": "   "}])


def test_should_refuse_a_chip_name_over_the_cap(canvas_root):
    long_label = "x" * (MAX_PRESET_LABEL_CHARS + 1)
    with pytest.raises(storage.PresetsInvalid):
        storage.write_presets([{"label": long_label, "question": "Explain this."}])


def test_should_refuse_a_chip_question_over_the_cap(canvas_root):
    long_question = "x" * (MAX_PRESET_QUESTION_CHARS + 1)
    with pytest.raises(storage.PresetsInvalid):
        storage.write_presets([{"label": "Explain", "question": long_question}])


def test_should_keep_the_earlier_chips_when_a_save_is_refused(canvas_root):
    storage.write_presets([{"label": "Explain", "question": "Explain this."}])
    with pytest.raises(storage.PresetsInvalid):
        storage.write_presets([{"label": "", "question": ""}])
    assert storage.read_presets() == [{"label": "Explain", "question": "Explain this."}]


def test_should_refuse_to_read_a_chips_file_that_is_not_valid_json(canvas_root):
    (canvas_root / PRESETS_FILE).write_text("{not json", encoding="utf-8")
    with pytest.raises(storage.PresetsInvalid):
        storage.read_presets()


def test_should_not_reset_to_the_defaults_when_the_chips_file_is_broken(canvas_root):
    (canvas_root / PRESETS_FILE).write_text('{"presets": "nonsense"}', encoding="utf-8")
    with pytest.raises(storage.PresetsInvalid):
        storage.read_presets()


def test_should_not_list_the_chips_file_as_a_canvas(canvas_root, sample_markdown):
    storage.create_canvas(sample_markdown)
    storage.write_presets([{"label": "Explain", "question": "Explain this."}])
    assert len(storage.list_canvases()) == 1
