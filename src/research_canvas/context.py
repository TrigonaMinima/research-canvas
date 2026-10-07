"""Assemble what a run is allowed to see.

US-3 fixes this: the root document, the ancestors of the box being asked from, the
highlighted passage, and the question. A sibling branch is never sent, so one line of
questioning cannot leak into another.
"""

from __future__ import annotations

from . import storage
from .config import INSTRUCTIONS_HEADING, INSTRUCTIONS_PRECEDENCE, MAX_IMAGES_PER_ANSWER
from .storage import Box, Canvas

_BASE = (
    "You are answering a reader's question about a passage they highlighted while "
    "reading. Answer the question directly and concretely. Use plain markdown. Do not "
    "restate the question, do not greet, and do not offer to help further. Write "
    "mathematics as LaTeX: $...$ inline and $$...$$ on its own line for display. "
)

SYSTEM_PREAMBLE = _BASE + (
    "Back factual claims with sources you found on the web and link them inline, unless "
    "the document and passages given here already hold the facts. When the reader asks "
    "for pictures, or the answer is about something visual, embed up to "
    f"{MAX_IMAGES_PER_ANSWER} pictures as ![short caption](direct image file URL). Use "
    "only direct image file URLs you saw in search or fetch results; Wikimedia Commons "
    "upload URLs work well. Never invent a URL. Do not say whether a picture was checked: "
    "the app downloads and checks every one itself."
)

# Without search the run can only guess picture URLs, and a guessed URL is never shown.
OFFLINE_PREAMBLE = _BASE + (
    "Web search is off for this question. Do not embed pictures, because you cannot "
    "check that a picture URL is real."
)


MERGE_PREAMBLE = (
    "You are folding an answer back into the document a reader is reading. Return the "
    "changes as edits: one JSON object per line and nothing else, no prose around them, no "
    'fence, no array. Each object has "find", the exact markdown to replace, "replace", '
    'the markdown to put in its place, and "why", one short line naming the change. Quote '
    'enough surrounding text in "find" to be unique in the document. Change whatever the '
    "answer bears on, anywhere in the document, and leave everything else alone: text you do "
    "not name is kept exactly as it is, so name every change you want made. Write mathematics "
    "as LaTeX: $...$ inline and $$...$$ on its own line for display."
)


def instructions_block() -> list[str]:
    """The reader's standing instructions, or nothing at all when they have none.

    Every generator calls this, so the answer runs and the research runs to come obey
    the same one file. It is read here, not at import, so an edit needs no restart.
    """
    text = storage.read_instructions().strip()
    if not text:
        return []
    return [f"## {INSTRUCTIONS_HEADING}", "", INSTRUCTIONS_PRECEDENCE, "", text, ""]


def build_prompt(canvas: Canvas, box: Box) -> str:
    if not box.question.strip():
        raise ValueError(f"box {box.id} has no question to ask")

    # Beside the preamble, not beside the question: these are rules, not the ask.
    preamble = SYSTEM_PREAMBLE if canvas.searches(box) else OFFLINE_PREAMBLE
    parts: list[str] = [preamble, "", *instructions_block()]
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


def build_merge_prompt(canvas: Canvas, box: Box, guidance: str) -> str:
    """What a merge run sees: the parent it may change, and the answer going into it.

    The same path-only rule as `build_prompt`, pointed the other way. The run is given the
    parent and this one answer, never a sibling branch, and the highlighted passage is told
    to it as where the question came from, not as a limit on what it may change.
    """
    if not box.parent:
        raise ValueError(f"box {box.id} has no parent to merge into")
    parent = canvas.box(box.parent)

    parts: list[str] = [MERGE_PREAMBLE, "", *instructions_block()]
    parts += [
        "## The document to change",
        "",
        storage.read_body(canvas.id, parent.id).strip(),
        "",
    ]

    passage = _highlight(canvas, box)
    if passage:
        parts += [
            "## The passage the reader highlighted",
            "",
            f"> {passage}",
            "",
            "It is where the question came from. It is not a limit on what you may change.",
            "",
        ]

    answer = storage.read_body(canvas.id, box.id).strip()
    parts += ["## The question they asked", "", box.question.strip(), ""]
    parts += ["## The answer to fold in", "", answer or "(no answer yet)", ""]

    if guidance.strip():
        parts += ["## How the reader wants it merged", "", guidance.strip(), ""]

    return "\n".join(parts)
