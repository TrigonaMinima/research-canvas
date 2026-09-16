"""Seed a canvas at the release-criteria size, straight onto disk.

The PRD asks for a 20,000-word root document and 100 answer boxes. Building that
through the API would mean 100 real runs; writing it with the storage layer costs a
fraction of a second and produces exactly the same files the app reads.
"""

from __future__ import annotations

from pathlib import Path

WORDS = 20_000
ANSWERS = 100

LOREM = [
    "the",
    "transformer",
    "encoder",
    "stacks",
    "identical",
    "layers",
    "each",
    "with",
    "multi",
    "head",
    "self",
    "attention",
    "and",
    "a",
    "position",
    "wise",
    "feed",
    "forward",
    "network",
    "followed",
    "by",
    "a",
    "residual",
    "connection",
    "and",
    "layer",
    "normalisation",
    "which",
    "keeps",
    "gradients",
    "flowing",
]


def big_markdown(words: int = WORDS, answers: int = ANSWERS) -> str:
    """A long document with one unique, findable token per planned anchor."""
    body: list[str] = []
    marks = [f"marker{i:03d}" for i in range(answers)]
    per_paragraph = 120
    written = 0
    while written < words:
        chunk = [LOREM[(written + i) % len(LOREM)] for i in range(per_paragraph)]
        if marks:
            chunk[per_paragraph // 2] = marks.pop(0)
        body.append(" ".join(chunk) + ".")
        written += per_paragraph
    return "# A Very Long Paper\n\n" + "\n\n".join(body) + "\n"


def seed(canvas_home: Path, *, words: int = WORDS, answers: int = ANSWERS) -> str:
    """Write the canvas under ``canvas_home`` and return its id."""
    from research_canvas import storage

    original = storage.CANVAS_ROOT
    storage.CANVAS_ROOT = canvas_home
    try:
        canvas = storage.create_canvas(big_markdown(words, answers), web_search=False)
        source = storage.read_body(canvas.id, canvas.root_id)
        for i in range(answers):
            box = storage.add_answer(
                canvas,
                parent_id=canvas.root_id,
                question=f"What does marker{i:03d} mean?",
                # Two columns to the right of the document, so the fit test has real extent.
                x=900.0 + (i % 2) * 520.0,
                y=float(i * 240),
                web_search=False,
            )
            box.status = "done"
            storage.write_body(canvas.id, box.id, f"Answer {i}: it marks a passage.\n")
            quote = f"marker{i:03d}"
            start = source.index(quote)
            canvas.anchors.append(
                storage.Anchor(
                    id=storage.next_anchor_id(canvas),
                    box=canvas.root_id,
                    target=box.id,
                    start=start,
                    end=start + len(quote),
                    quote=quote,
                )
            )
        storage.save(canvas)
        return canvas.id
    finally:
        storage.CANVAS_ROOT = original
