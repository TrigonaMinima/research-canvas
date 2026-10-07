"""Folding an answer back into the document it came from.

The run does not rewrite the document. It writes a list of edits, each naming the markdown
it replaces, so it may change anything anywhere in the parent while text no edit names
stays byte-identical. Applying them yields the document the review proposes, which is what
the reader then reads, edits, and accepts.

Edits arrive one JSON object per line rather than as one array, so a review fills in as the
run writes and a run cut short by a usage limit still yields the edits it managed.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from . import anchors

# How an edit stands against the document as it is now.
APPLIED = "applied"  # placed, and written into the proposed document
READY = "ready"  # not yet placed against a document
MISSING = "missing"  # the text it names is not there
AMBIGUOUS = "ambiguous"  # the text it names is there more than once

# A run that wraps its lines in a fence is being helpful, not wrong.
_FENCE = re.compile(r"^\s*```")


@dataclass
class Edit:
    id: str
    why: str
    find: str
    replace: str
    result: str = READY  # against the document as it stands now, never stored

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "why": self.why,
            "find": self.find,
            "replace": self.replace,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Edit:
        return cls(
            id=data["id"],
            why=data.get("why", ""),
            find=data["find"],
            replace=data["replace"],
        )


@dataclass
class EditStream:
    """Turns the run's token deltas into edits, one complete line at a time."""

    _buffer: str = ""
    _seen: int = 0

    def feed(self, delta: str) -> list[Edit]:
        self._buffer += delta
        found = []
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            edit = self._read(line)
            if edit:
                found.append(edit)
        return found

    def close(self) -> list[Edit]:
        """Whatever is left. A complete last line counts; a truncated one cannot parse."""
        line, self._buffer = self._buffer, ""
        edit = self._read(line)
        return [edit] if edit else []

    def _read(self, line: str) -> Edit | None:
        if not line.strip() or _FENCE.match(line):
            return None
        try:
            data = json.loads(line)
        except ValueError:
            return None
        if not isinstance(data, dict) or not _texts(data):
            return None
        self._seen += 1
        return Edit(
            id=f"e{self._seen}",
            why=str(data.get("why", "")).strip(),
            find=data["find"],
            replace=data["replace"],
        )


def _texts(data: dict) -> bool:
    return isinstance(data.get("find"), str) and isinstance(data.get("replace"), str)


def apply(markdown: str, edits: list[Edit]) -> tuple[str, list[Edit]]:
    """The document with every placeable edit written, and how each one fared.

    Each edit's `result` is stamped on the edit itself, so there is one list, not two
    that have to be kept in step by position.

    Each edit is located against the document as the ones before it left it, never against
    stored offsets. Two edits that overlap therefore cannot corrupt each other: the second
    simply reports that its text is no longer there.
    """
    body = markdown
    for edit in edits:
        placed = _spans(body, edit.find)
        if not placed:
            edit.result = MISSING
        elif len(placed) > 1:
            edit.result = AMBIGUOUS
        else:
            start, end = placed[0]
            body = body[:start] + edit.replace + body[end:]
            edit.result = APPLIED
    return body, edits


def where(markdown: str, edit: Edit) -> int | None:
    """The offset an edit's text sits at, or None when it is not there.

    Measured against the untouched document, so two edits can be ordered against each
    other and labelled with their section without either one having been written yet.
    """
    spans = _spans(markdown, edit.find)
    return spans[0][0] if spans else None


def _spans(text: str, find: str) -> list[tuple[int, int]]:
    """Where `find` sits, exactly if it can, else allowing whitespace to have moved.

    The run quotes the source back at us, and a soft wrap lands differently in a quote than
    in the file. Whitespace is the only thing allowed to differ; nothing else is normalised,
    because a looser match is a rewrite of text the reader never saw.
    """
    needle = find.strip()
    if not needle:
        return []
    exact = anchors.occurrences(text, needle)
    if exact:
        return [(at, at + len(needle)) for at in exact]
    loose = r"\s+".join(re.escape(word) for word in needle.split())
    return [(m.start(), m.end()) for m in re.finditer(loose, text)]
