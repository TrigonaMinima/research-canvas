"""Anchors are text offsets plus the quoted text, never pixel rects (PRD 15)."""

from __future__ import annotations

from research_canvas import anchors

TEXT = "The Transformer is based solely on attention mechanisms, dispensing with recurrence."


def test_should_accept_an_anchor_whose_quote_matches_its_offsets():
    anchor = anchors.Anchor(id="a1", box="b1", target="b2", start=4, end=15, quote="Transformer")
    assert anchors.resolve(TEXT, anchor).start == 4


def test_should_reanchor_when_the_text_shifted_but_the_quote_survives():
    shifted = "Note. " + TEXT
    anchor = anchors.Anchor(id="a1", box="b1", target="b2", start=4, end=15, quote="Transformer")
    assert anchors.resolve(shifted, anchor).start == 10


def test_should_report_an_anchor_lost_when_its_quote_is_gone():
    anchor = anchors.Anchor(id="a1", box="b1", target="b2", start=4, end=15, quote="Transformer")
    assert anchors.resolve("a completely different sentence", anchor) is None


def test_should_prefer_the_occurrence_nearest_the_stored_offset():
    text = "cat ... " + ("x" * 40) + " cat"
    anchor = anchors.Anchor(id="a1", box="b1", target="b2", start=49, end=52, quote="cat")
    assert anchors.resolve(text, anchor).start == 49


def test_should_refuse_a_quote_shorter_than_the_minimum():
    anchor = anchors.Anchor(id="a1", box="b1", target="b2", start=0, end=2, quote="Th")
    assert anchors.resolve(TEXT, anchor) is None
