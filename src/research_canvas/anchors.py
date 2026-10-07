"""An anchor points at a passage by text offset and the text itself.

Never by pixel rect: rects die on reload, on resize, and when a web font lands.
Storing the quote as well is what lets an anchor follow its text when the box
around it changes.

Offsets are measured against the *rendered* plain text of a box body: the
concatenation of the text nodes under ``[data-body]``, which is what the browser
walks when the reader drags a selection. They are never measured against the
markdown source, and the two disagree the moment a document contains any markup.
The browser owns this measurement end to end; the server stores what it is sent.
Any server-side caller of `resolve` must pass that same rendered projection.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .config import MERGE_QUOTE_CHARS, MIN_SELECTION_CHARS


@dataclass
class Anchor:
    id: str
    box: str  # the box the passage lives in
    target: str  # the answer box it opened
    start: int
    end: int
    quote: str

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "box": self.box,
            "target": self.target,
            "start": self.start,
            "end": self.end,
            "quote": self.quote,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Anchor:
        return cls(
            id=data["id"],
            box=data["box"],
            target=data["target"],
            start=int(data["start"]),
            end=int(data["end"]),
            quote=data["quote"],
        )


def resolve(text: str, anchor: Anchor) -> Anchor | None:
    """Locate the anchor in `text`, tolerating drift. None means the passage is gone."""
    quote = anchor.quote
    if len(quote) < MIN_SELECTION_CHARS:
        return None

    if text[anchor.start : anchor.end] == quote:
        return anchor

    hits = occurrences(text, quote)
    if not hits:
        return None

    # The text moved. Take the occurrence closest to where it used to be.
    start = min(hits, key=lambda i: abs(i - anchor.start))
    return Anchor(
        id=anchor.id,
        box=anchor.box,
        target=anchor.target,
        start=start,
        end=start + len(quote),
        quote=quote,
    )


def occurrences(text: str, needle: str) -> list[int]:
    """Every start offset, overlaps included. Shared with the merge matcher."""
    found, at = [], text.find(needle)
    while at != -1:
        found.append(at)
        at = text.find(needle, at + 1)
    return found


_SENTENCE_END = re.compile(r"[.!?](\s|$)")


def lead_sentence(text: str) -> str:
    """The opening sentence of a passage, capped so a mark stays a mark.

    Used when a merge rewrites the text an anchor quoted: the anchor follows the
    replacement, and a whole-paragraph quote would paint a paragraph-long highlight.
    """
    flat = " ".join(text.split())
    end = _SENTENCE_END.search(flat, MIN_SELECTION_CHARS)
    if end and end.end() <= MERGE_QUOTE_CHARS:
        return flat[: end.end()].strip()
    return flat[:MERGE_QUOTE_CHARS].strip()
