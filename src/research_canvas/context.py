"""Assemble what a run is allowed to see.

US-3 fixes this: the root document, the ancestors of the box being asked from, the
highlighted passage, and the question. A sibling branch is never sent, so one line of
questioning cannot leak into another.
"""

from __future__ import annotations

from . import storage
from .storage import Box, Canvas

SYSTEM_PREAMBLE = (
    "You are answering a reader's question about a passage they highlighted while "
    "reading. Answer the question directly and concretely. Use plain markdown. Do not "
    "restate the question, do not greet, and do not offer to help further."
)


def build_prompt(canvas: Canvas, box: Box) -> str:
    if not box.question.strip():
        raise ValueError(f"box {box.id} has no question to ask")

    parts: list[str] = [SYSTEM_PREAMBLE, ""]
    chain = canvas.path_to(box.id)

    for step in chain[:-1]:
        body = storage.read_body(canvas.id, step.id).strip()
        if step.kind == "root":
            parts += ["## The document being read", "", body, ""]
        else:
            parts += [
                f"## An earlier question at depth {step.depth}",
                "",
                f"Q: {step.question}",
                "",
                f"A: {body}" if body else "A: (no answer yet)",
                "",
            ]

    passage = _highlight(canvas, box)
    if passage:
        parts += ["## The highlighted passage", "", f"> {passage}", ""]

    parts += ["## The question", "", box.question.strip(), ""]
    return "\n".join(parts)


def _highlight(canvas: Canvas, box: Box) -> str:
    for anchor in canvas.anchors:
        if anchor.target == box.id:
            return anchor.quote.strip()
    return ""
