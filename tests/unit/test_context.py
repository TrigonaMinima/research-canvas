"""US-3: a run sees the path only. Root, ancestors, the highlight, the question."""

from __future__ import annotations

import re

import pytest

from research_canvas import context, storage
from research_canvas.config import (
    INSTRUCTIONS_FILE,
    INSTRUCTIONS_HEADING,
    INSTRUCTIONS_PRECEDENCE,
)


@pytest.fixture
def tree(canvas_root, sample_markdown):
    canvas = storage.create_canvas(sample_markdown)
    left = storage.add_answer(canvas, parent_id=canvas.root_id, question="Why attention?")
    storage.write_body(canvas.id, left.id, "Attention lets every token see every other token.")
    left.status = "done"
    right = storage.add_answer(canvas, parent_id=canvas.root_id, question="Why not recurrence?")
    storage.write_body(canvas.id, right.id, "SECRET SIBLING TEXT")
    right.status = "done"
    deep = storage.add_answer(canvas, parent_id=left.id, question="What is a head?")
    storage.save(canvas)
    return canvas, left, right, deep


def test_should_include_the_root_document(tree, sample_markdown):
    canvas, _left, _right, deep = tree
    assert "Attention Is All You Need" in context.build_prompt(canvas, deep)


def test_should_include_the_ancestor_answer(tree):
    canvas, _left, _right, deep = tree
    assert "every token see every other token" in context.build_prompt(canvas, deep)


def test_should_never_include_a_sibling_branch(tree):
    canvas, _left, _right, deep = tree
    assert "SECRET SIBLING TEXT" not in context.build_prompt(canvas, deep)


def test_should_include_the_question(tree):
    canvas, _left, _right, deep = tree
    assert "What is a head?" in context.build_prompt(canvas, deep)


def test_should_include_the_highlighted_passage(tree):
    canvas, left, _right, deep = tree
    canvas.anchors.append(
        storage.Anchor(id="a1", box=left.id, target=deep.id, start=0, end=9, quote="Attention")
    )
    assert "Attention" in context.build_prompt(canvas, deep)


def test_should_not_ask_for_a_box_with_no_question(tree):
    canvas, _left, _right, _deep = tree
    with pytest.raises(ValueError):
        context.build_prompt(canvas, canvas.box(canvas.root_id))


def test_should_ask_the_run_for_inline_math_in_single_dollars(tree):
    canvas, _left, _right, deep = tree
    # A lone $, not one half of a $$ pair: the two delimiters mean different things.
    assert re.search(r"(?<!\$)\$(?!\$)", context.build_prompt(canvas, deep))


def test_should_ask_the_run_for_display_math_in_double_dollars(tree):
    canvas, _left, _right, deep = tree
    assert "$$" in context.build_prompt(canvas, deep)


# --- standing instructions ----------------------------------------------------
# Global, one file for every canvas, injected into every generated prompt.


def test_should_not_change_the_prompt_when_there_are_no_instructions(tree, canvas_root):
    canvas, _left, _right, deep = tree
    before = context.build_prompt(canvas, deep)
    assert not (canvas_root / INSTRUCTIONS_FILE).exists()
    assert INSTRUCTIONS_HEADING not in before


def test_should_ignore_a_whitespace_only_instructions_file(tree, canvas_root):
    canvas, _left, _right, deep = tree
    expected = context.build_prompt(canvas, deep)
    (canvas_root / INSTRUCTIONS_FILE).write_text("   \n\n\t\n", encoding="utf-8")
    assert context.build_prompt(canvas, deep) == expected


def test_should_include_the_standing_instructions(tree, canvas_root):
    canvas, _left, _right, deep = tree
    (canvas_root / INSTRUCTIONS_FILE).write_text("Answer in British English.", encoding="utf-8")
    assert "Answer in British English." in context.build_prompt(canvas, deep)


def test_should_put_the_instructions_before_the_document(tree, canvas_root):
    canvas, _left, _right, deep = tree
    (canvas_root / INSTRUCTIONS_FILE).write_text("Answer in British English.", encoding="utf-8")
    prompt = context.build_prompt(canvas, deep)
    assert prompt.index(INSTRUCTIONS_HEADING) < prompt.index("## The document being read")


def test_should_say_the_built_in_rules_win_on_a_conflict(tree, canvas_root):
    canvas, _left, _right, deep = tree
    (canvas_root / INSTRUCTIONS_FILE).write_text("Always greet me warmly.", encoding="utf-8")
    assert INSTRUCTIONS_PRECEDENCE in context.build_prompt(canvas, deep)


def test_should_offer_the_instructions_block_to_any_generator(canvas_root):
    assert context.instructions_block() == []
    (canvas_root / INSTRUCTIONS_FILE).write_text("Be brief.", encoding="utf-8")
    assert any("Be brief." in part for part in context.instructions_block())
