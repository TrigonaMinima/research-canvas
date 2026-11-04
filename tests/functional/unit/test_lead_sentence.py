"""anchors.lead_sentence: the quote an anchor keeps once a merge rewrites its passage."""

from __future__ import annotations

from research_canvas.anchors import lead_sentence
from research_canvas.config import MERGE_QUOTE_CHARS


def test_should_keep_only_the_first_sentence():
    assert lead_sentence("Attention is all you need. The rest follows.") == (
        "Attention is all you need."
    )


def test_should_end_a_sentence_at_a_question_or_exclamation_mark():
    assert lead_sentence("Why attention? Because it is fast!") == "Why attention?"


def test_should_flatten_line_breaks_and_runs_of_space():
    assert lead_sentence("Attention   is\nall you\n\tneed. Next.") == "Attention is all you need."


def test_should_skip_a_full_stop_inside_the_first_few_characters():
    # Starts the search at MIN_SELECTION_CHARS, so an initial is not a whole sentence.
    assert lead_sentence("A. Vaswani wrote it. Others followed.") == "A. Vaswani wrote it."


def test_should_not_end_a_sentence_at_a_decimal_point():
    assert lead_sentence("It scored 28.4 BLEU. That was new.") == "It scored 28.4 BLEU."


def test_should_keep_a_passage_with_no_sentence_end_whole():
    assert lead_sentence("A heading with no full stop") == "A heading with no full stop"


def test_should_cap_a_passage_with_no_sentence_end():
    assert len(lead_sentence("word " * 100)) <= MERGE_QUOTE_CHARS


def test_should_cap_a_first_sentence_longer_than_the_cap():
    long = "a" * (MERGE_QUOTE_CHARS + 50) + ". Short."
    assert lead_sentence(long) == "a" * MERGE_QUOTE_CHARS


def test_should_keep_a_first_sentence_that_ends_exactly_at_the_cap():
    sentence = "a" * (MERGE_QUOTE_CHARS - 1) + "."
    assert lead_sentence(sentence + " Next.") == sentence


def test_should_answer_empty_for_blank_text():
    assert lead_sentence("  \n ") == ""
