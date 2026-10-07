"""Layer 6: persistence. US-18 says every change survives a restart."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from research_canvas import config, merge, storage
from research_canvas.config import (
    CANVAS_FILE,
    DEFAULT_ASK_PRESETS,
    FORMAT_VERSION,
    INSTRUCTIONS_FILE,
    MAX_BOX_WIDTH,
    MAX_INSTRUCTIONS_CHARS,
    MAX_PRESET_LABEL_CHARS,
    MAX_PRESET_QUESTION_CHARS,
    MAX_PRESETS,
    MERGE_DIR,
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


# --- renaming: the title rule and the id it must not disturb --------------------


def test_should_trim_a_title(canvas_root):
    assert storage.clean_title("  Attention  \n") == "Attention"


def test_should_turn_a_newline_inside_a_title_into_a_space(canvas_root):
    assert storage.clean_title("Attention\nIs All") == "Attention Is All"


def test_should_refuse_a_blank_title(canvas_root):
    with pytest.raises(storage.TitleInvalid):
        storage.clean_title("")


def test_should_refuse_a_title_of_only_whitespace(canvas_root):
    with pytest.raises(storage.TitleInvalid):
        storage.clean_title(" \n\t ")


def test_should_refuse_a_title_over_the_cap(canvas_root):
    with pytest.raises(storage.TitleInvalid):
        storage.clean_title("x" * (config.MAX_TITLE_CHARS + 1))


def test_should_accept_a_title_of_exactly_the_cap(canvas_root):
    title = "x" * config.MAX_TITLE_CHARS
    assert storage.clean_title(title) == title


def test_should_make_the_title_error_a_value_error(canvas_root):
    assert issubclass(storage.TitleInvalid, ValueError)


def test_should_build_the_id_from_today_and_the_whole_short_slug(canvas_root):
    today = f"{datetime.now(UTC):%Y-%m-%d}"
    assert storage._reserve_id("Attention Is All") == f"{today}-attention-is-all"


def test_should_cut_a_long_slug_at_the_slug_cap(canvas_root):
    slug = storage._reserve_id("word " * 40).removeprefix(f"{datetime.now(UTC):%Y-%m-%d}-")
    assert len(slug) <= config.MAX_SLUG_CHARS


def test_should_drop_the_dash_a_cut_leaves_behind(canvas_root):
    # The cut lands right after the dash between the two words.
    title = "a" * (config.MAX_SLUG_CHARS - 1) + " bbbb"
    assert storage._slug(title) == "a" * (config.MAX_SLUG_CHARS - 1)


def test_should_follow_the_configured_slug_cap(canvas_root, monkeypatch):
    monkeypatch.setattr(storage, "MAX_SLUG_CHARS", 10)
    assert storage._slug("abcdefghijklmnopqrstuvwxyz") == "abcdefghij"


# --- merge proposals ----------------------------------------------------------
# A proposal is a decision waiting to be made, written down so closing the tab does not
# throw the reading away. It sits beside the canvas, never inside canvas.json, because it
# is machinery rather than research.


@pytest.fixture
def proposal(canvas_root, sample_markdown):
    canvas = storage.create_canvas(sample_markdown)
    child = storage.add_answer(canvas, parent_id=canvas.root_id, question="Why attention?")
    child.status = "done"
    storage.save(canvas)
    return canvas, child


def make_proposal(child_id, **over):
    fields = {
        "child": child_id,
        "prompt": "keep it short",
        "status": "done",
        "edits": [merge.Edit(id="e1", why="w", find="a", replace="b")],
    }
    return storage.Proposal(**{**fields, **over})


def test_should_start_a_box_unmerged(proposal):
    _canvas, child = proposal
    assert child.merged is False


def test_should_remember_that_a_box_was_merged(proposal):
    canvas, child = proposal
    child.merged = True
    storage.save(canvas)
    assert storage.load(canvas.id).box(child.id).merged is True


def test_should_load_a_canvas_written_before_boxes_could_be_merged(proposal, canvas_root):
    canvas, child = proposal
    path = canvas_root / canvas.id / CANVAS_FILE
    raw = json.loads(path.read_text(encoding="utf-8"))
    for box in raw["boxes"]:
        box.pop("merged", None)
    path.write_text(json.dumps(raw), encoding="utf-8")
    assert storage.load(canvas.id).box(child.id).merged is False


def test_should_have_no_proposal_to_begin_with(proposal):
    canvas, child = proposal
    assert storage.read_merge(canvas.id, child.id) is None


def test_should_write_a_proposal_beside_the_canvas(proposal, canvas_root):
    canvas, child = proposal
    storage.write_merge(canvas.id, make_proposal(child.id))
    assert (canvas_root / canvas.id / MERGE_DIR / f"{child.id}.json").is_file()


def test_should_read_a_proposal_back(proposal):
    canvas, child = proposal
    storage.write_merge(canvas.id, make_proposal(child.id))
    assert storage.read_merge(canvas.id, child.id).child == child.id


def test_should_round_trip_the_reworded_text_of_an_edit(proposal):
    canvas, child = proposal
    written = make_proposal(child.id)
    written.edits[0].replace = "the wording I typed"
    storage.write_merge(canvas.id, written)
    assert storage.read_merge(canvas.id, child.id).edits[0].replace == "the wording I typed"


def test_should_round_trip_the_document_under_review(proposal):
    canvas, child = proposal
    written = make_proposal(child.id)
    written.proposed = "# The document as the reader left it\n"
    storage.write_merge(canvas.id, written)
    read = storage.read_merge(canvas.id, child.id)
    assert read.proposed == "# The document as the reader left it\n"


def test_should_load_a_proposal_written_before_the_document_was_reviewable(proposal, canvas_root):
    canvas, child = proposal
    storage.write_merge(canvas.id, make_proposal(child.id))
    path = canvas_root / canvas.id / MERGE_DIR / f"{child.id}.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw.pop("proposed", None)
    path.write_text(json.dumps(raw), encoding="utf-8")
    assert storage.read_merge(canvas.id, child.id).proposed == ""


def test_should_drop_a_proposal(proposal):
    canvas, child = proposal
    storage.write_merge(canvas.id, make_proposal(child.id))
    storage.delete_merge(canvas.id, child.id)
    assert storage.read_merge(canvas.id, child.id) is None


def test_should_list_the_boxes_holding_a_proposal(proposal):
    canvas, child = proposal
    storage.write_merge(canvas.id, make_proposal(child.id))
    assert storage.list_merges(canvas.id) == [child.id]


def test_should_surface_a_proposal_the_app_died_on_as_interrupted(proposal):
    canvas, child = proposal
    storage.write_merge(canvas.id, make_proposal(child.id, status="pending", edits=[]))
    assert storage.read_merge(canvas.id, child.id).status == "interrupted"


def test_should_explain_why_an_interrupted_proposal_stopped(proposal):
    canvas, child = proposal
    storage.write_merge(canvas.id, make_proposal(child.id, status="pending", edits=[]))
    assert storage.read_merge(canvas.id, child.id).reason


def test_should_leave_a_running_proposal_alone_while_it_is_live(proposal):
    canvas, child = proposal
    storage.write_merge(canvas.id, make_proposal(child.id, status="pending", edits=[]))
    with storage.live(canvas.id, child.id):
        assert storage.read_merge(canvas.id, child.id).status == "pending"


def test_should_refuse_a_proposal_path_outside_the_canvas(proposal):
    canvas, _child = proposal
    with pytest.raises(storage.CanvasNotFound):
        storage.read_merge(canvas.id, "../../escape")
