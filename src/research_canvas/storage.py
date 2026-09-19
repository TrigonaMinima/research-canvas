"""Canvases on disk: one folder each, plain JSON and plain markdown.

Nothing leaves the machine and nothing is hidden in a database, so a canvas can be
read, grepped, backed up, or resumed with ordinary tools.
"""

from __future__ import annotations

import json
import os
import re
import threading
import unicodedata
from collections.abc import Iterable
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from itertools import count

from . import md
from .anchors import Anchor
from .config import (
    BOX_DIR,
    CANVAS_FILE,
    CANVAS_ROOT,
    FORMAT_VERSION,
    INSTRUCTIONS_FILE,
    INSTRUCTIONS_TOO_LONG_MESSAGE,
    MAX_BOX_WIDTH,
    MAX_INSTRUCTIONS_CHARS,
    MIN_BOX_WIDTH,
    MIN_PASTE_CHARS,
    ROOT_BOX_ID,
    ROOT_BOX_WIDTH,
    ROOT_DOC_FILE,
    UNFINISHED,
)

INTERRUPTED_REASON = (
    "The app closed while this answer was running. Nothing else on the canvas changed."
)
REFUSED_MESSAGE = "Import refused: paste at least a few sentences of text. No canvas was created."


class ImportRefused(ValueError):
    """The pasted text was too thin to make a canvas from."""


class CanvasNotFound(LookupError):
    """No canvas with that id, or the id was not a plain folder name."""


class InstructionsTooLong(ValueError):
    """The standing instructions were longer than every run can afford to carry."""


@dataclass
class Camera:
    tx: float = 0.0
    ty: float = 0.0
    scale: float = 1.0

    def to_dict(self) -> dict:
        return {"tx": self.tx, "ty": self.ty, "scale": self.scale}

    @classmethod
    def from_dict(cls, data: dict) -> Camera:
        return cls(tx=float(data["tx"]), ty=float(data["ty"]), scale=float(data["scale"]))


@dataclass
class Box:
    id: str
    kind: str  # "root" | "answer"
    x: float
    y: float
    w: float
    depth: int = 0
    parent: str | None = None
    status: str = "done"
    question: str = ""
    reason: str = ""
    web_search: bool = True
    collapsed: bool = False
    # Slugs of the headings folded shut inside this box's document.
    sections: list[str] = field(default_factory=list)
    # Dragged vertically by the reader, so the layout pass leaves it alone.
    pinned: bool = False
    created_at: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "kind": self.kind,
            "x": self.x,
            "y": self.y,
            "w": self.w,
            "depth": self.depth,
            "parent": self.parent,
            "status": self.status,
            "question": self.question,
            "reason": self.reason,
            "webSearch": self.web_search,
            "collapsed": self.collapsed,
            "sections": self.sections,
            "pinned": self.pinned,
            "createdAt": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Box:
        return cls(
            id=data["id"],
            kind=data["kind"],
            x=float(data["x"]),
            y=float(data["y"]),
            w=float(data["w"]),
            depth=int(data.get("depth", 0)),
            parent=data.get("parent"),
            status=data.get("status", "done"),
            question=data.get("question", ""),
            reason=data.get("reason", ""),
            web_search=bool(data.get("webSearch", True)),
            collapsed=bool(data.get("collapsed", False)),
            sections=[str(s) for s in data.get("sections", [])],
            pinned=bool(data.get("pinned", False)),
            created_at=data.get("createdAt", ""),
        )


@dataclass
class Canvas:
    id: str
    title: str
    created_at: str
    updated_at: str
    boxes: list[Box] = field(default_factory=list)
    anchors: list[Anchor] = field(default_factory=list)
    camera: Camera = field(default_factory=Camera)
    theme: str = "light"
    web_search: bool = True

    root_id: str = ROOT_BOX_ID

    def box(self, box_id: str) -> Box:
        for box in self.boxes:
            if box.id == box_id:
                return box
        raise KeyError(box_id)

    def path_to(self, box_id: str) -> list[Box]:
        """Root first, then every ancestor, then the box. Never a sibling (US-3)."""
        chain: list[Box] = []
        current: str | None = box_id
        while current is not None:
            box = self.box(current)
            chain.append(box)
            current = box.parent
        return list(reversed(chain))

    def to_dict(self) -> dict:
        return {
            "formatVersion": FORMAT_VERSION,
            "id": self.id,
            "title": self.title,
            "createdAt": self.created_at,
            "updatedAt": self.updated_at,
            "theme": self.theme,
            "webSearch": self.web_search,
            "rootId": self.root_id,
            "camera": self.camera.to_dict(),
            "boxes": [b.to_dict() for b in self.boxes],
            "anchors": [a.to_dict() for a in self.anchors],
        }

    @classmethod
    def from_dict(cls, data: dict) -> Canvas:
        return cls(
            id=data["id"],
            title=data["title"],
            created_at=data["createdAt"],
            updated_at=data["updatedAt"],
            theme=data.get("theme", "light"),
            web_search=bool(data.get("webSearch", True)),
            root_id=data.get("rootId", ROOT_BOX_ID),
            camera=Camera.from_dict(data["camera"]),
            boxes=[Box.from_dict(b) for b in data["boxes"]],
            anchors=[Anchor.from_dict(a) for a in data["anchors"]],
        )


@dataclass
class CanvasSummary:
    id: str
    title: str
    updated_at: str
    boxes: int

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "updatedAt": self.updated_at,
            "boxes": self.boxes,
        }


# --- creating -----------------------------------------------------------------


def create_canvas(markdown: str, *, web_search: bool = True) -> Canvas:
    if len(markdown.strip()) <= MIN_PASTE_CHARS:
        raise ImportRefused(REFUSED_MESSAGE)

    title = md.first_heading(markdown) or "Untitled"
    now = _now()
    canvas = Canvas(
        id=_reserve_id(title),
        title=title,
        created_at=now,
        updated_at=now,
        web_search=web_search,
        boxes=[
            Box(
                id=ROOT_BOX_ID,
                kind="root",
                x=0.0,
                y=0.0,
                w=float(ROOT_BOX_WIDTH),
                depth=0,
                status="done",
                web_search=web_search,
                created_at=now,
            )
        ],
    )
    (_dir(canvas.id) / BOX_DIR).mkdir(parents=True, exist_ok=True)
    write_body(canvas.id, ROOT_BOX_ID, markdown)
    save(canvas)
    return canvas


def add_answer(
    canvas: Canvas,
    *,
    parent_id: str,
    question: str,
    x: float = 0.0,
    y: float = 0.0,
    w: float | None = None,
    web_search: bool | None = None,
) -> Box:
    parent = canvas.box(parent_id)
    box = Box(
        id=_next_box_id(canvas),
        kind="answer",
        x=x,
        y=y,
        # An answer opens as wide as the box it came from, so a reader who widened one
        # branch keeps that column width all the way down it.
        w=_clamp_width(parent.w if w is None else w),
        depth=parent.depth + 1,
        parent=parent_id,
        status="pending",
        question=question,
        web_search=canvas.web_search if web_search is None else web_search,
        created_at=_now(),
    )
    canvas.boxes.append(box)
    return box


# --- concurrency --------------------------------------------------------------

# One writer at a time per canvas. A camera nudge and a finishing answer both
# rewrite canvas.json, and the loser of that race would drop the winner's change.
_LOCKS: dict[str, threading.RLock] = {}
_LOCKS_GUARD = threading.Lock()

# Runs this process is actually driving. Everything else that looks unfinished on
# disk was left behind by a process that is gone.
_LIVE: set[tuple[str, str]] = set()
_LIVE_GUARD = threading.Lock()


def _lock_for(canvas_id: str) -> threading.RLock:
    with _LOCKS_GUARD:
        return _LOCKS.setdefault(canvas_id, threading.RLock())


@contextmanager
def edit(canvas_id: str):
    """Load, hand over, and save again, with nobody else writing in between."""
    with _lock_for(canvas_id):
        canvas = load(canvas_id)
        yield canvas
        save(canvas)


@contextmanager
def live(canvas_id: str, box_id: str):
    """Mark a run as belonging to this process, so a reload does not bury it."""
    key = (canvas_id, box_id)
    with _LIVE_GUARD:
        _LIVE.add(key)
    try:
        yield
    finally:
        with _LIVE_GUARD:
            _LIVE.discard(key)


def is_live(canvas_id: str, box_id: str) -> bool:
    with _LIVE_GUARD:
        return (canvas_id, box_id) in _LIVE


# --- reading and writing ------------------------------------------------------


def load(canvas_id: str) -> Canvas:
    path = _dir(canvas_id) / CANVAS_FILE
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CanvasNotFound(canvas_id) from exc

    canvas = Canvas.from_dict(data)
    for box in canvas.boxes:
        # A run cannot outlive the process that started it. Runs this process is
        # still driving are the exception: they are not orphans.
        if box.status in UNFINISHED and not is_live(canvas.id, box.id):
            box.status = "interrupted"
            box.reason = INTERRUPTED_REASON
    return canvas


def save(canvas: Canvas) -> None:
    canvas.updated_at = _now()
    # Serialise before touching the file, so a failure here cannot truncate the old one.
    payload = json.dumps(canvas.to_dict(), indent=2, ensure_ascii=False) + "\n"
    _atomic_write(_dir(canvas.id) / CANVAS_FILE, payload)


def list_canvases() -> list[CanvasSummary]:
    if not CANVAS_ROOT.exists():
        return []
    found: list[CanvasSummary] = []
    for entry in CANVAS_ROOT.iterdir():
        if not entry.is_dir():
            continue
        try:
            data = json.loads((entry / CANVAS_FILE).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        found.append(
            CanvasSummary(
                id=data["id"],
                title=data["title"],
                updated_at=data["updatedAt"],
                boxes=len(data["boxes"]),
            )
        )
    found.sort(key=lambda c: (c.updated_at, c.id), reverse=True)
    return found


def read_body(canvas_id: str, box_id: str) -> str:
    try:
        return _body_path(canvas_id, box_id).read_text(encoding="utf-8")
    except OSError:
        return ""


def write_body(canvas_id: str, box_id: str, text: str) -> None:
    path = _body_path(canvas_id, box_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write(path, text)


def delete_body(canvas_id: str, box_id: str) -> None:
    _body_path(canvas_id, box_id).unlink(missing_ok=True)


# --- standing instructions ----------------------------------------------------
# One file for the whole app. Read on every prompt build rather than cached, so
# editing it in a text editor takes effect without restarting the server.


def read_instructions() -> str:
    # Only a missing file means "no instructions". An unreadable one is a fault worth
    # hearing about, not a reason to quietly drop the reader's rules from every run.
    try:
        return (CANVAS_ROOT / INSTRUCTIONS_FILE).read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def write_instructions(text: str) -> None:
    if len(text) > MAX_INSTRUCTIONS_CHARS:
        raise InstructionsTooLong(INSTRUCTIONS_TOO_LONG_MESSAGE)
    _atomic_write(CANVAS_ROOT / INSTRUCTIONS_FILE, text)


# --- internals ----------------------------------------------------------------


def _dir(canvas_id: str):
    if not _SAFE_ID.fullmatch(canvas_id or ""):
        raise CanvasNotFound(canvas_id)
    return CANVAS_ROOT / canvas_id


def _body_path(canvas_id: str, box_id: str):
    base = _dir(canvas_id)
    if box_id == ROOT_BOX_ID:
        return base / ROOT_DOC_FILE
    if not _SAFE_ID.fullmatch(box_id or ""):
        raise CanvasNotFound(box_id)
    return base / BOX_DIR / f"{box_id}.md"


_TMP_SEQ = count()


def _atomic_write(path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Unique per write: two writers sharing one temp name clobber each other.
    tmp = path.with_name(f".{path.name}.{os.getpid()}.{next(_TMP_SEQ)}.tmp")
    try:
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, path)
    except OSError:
        tmp.unlink(missing_ok=True)
        raise


def _clamp_width(w: float) -> float:
    return min(float(MAX_BOX_WIDTH), max(float(MIN_BOX_WIDTH), float(w)))


def _next_id(prefix: str, existing: Iterable) -> str:
    """One past the highest number already used, so an id is never reissued."""
    used = {int(item.id[1:]) for item in existing if item.id[1:].isdigit()}
    return f"{prefix}{max(used, default=0) + 1}"


def _next_box_id(canvas: Canvas) -> str:
    return _next_id("b", canvas.boxes)


def next_anchor_id(canvas: Canvas) -> str:
    return _next_id("a", canvas.anchors)


def _reserve_id(title: str) -> str:
    """Claim a folder name now, so two imports of the same paper cannot collide."""
    CANVAS_ROOT.mkdir(parents=True, exist_ok=True)
    stem = f"{datetime.now(UTC):%Y-%m-%d}-{_slug(title)}"
    for suffix in ("", *(f"-{n}" for n in range(2, 1000))):
        candidate = CANVAS_ROOT / f"{stem}{suffix}"
        try:
            candidate.mkdir()
        except FileExistsError:
            continue
        return candidate.name
    raise ImportRefused("Too many canvases with this title.")


_SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")


def _slug(title: str) -> str:
    ascii_title = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_title.lower()).strip("-")
    return (slug[:48].rstrip("-")) or "untitled"


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="microseconds")
