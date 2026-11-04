"""Breaking the network under a real page: failed replies, dropped requests, dead streams.

Every route here is installed on one page, so the session server stays healthy for
every other test. A route matches one method on one path, because a canvas URL is the
prefix of every box URL under it.
"""

from __future__ import annotations

import re

TOAST = "[data-toast]"
# What a failed reply says, so a toast can be traced to the route that sent it.
DETAIL = "the server fell over"

CANVAS = re.compile(r"/api/canvases/[^/?]+$")
CANVAS_LIST = re.compile(r"/api/canvases$")
BODY = re.compile(r"/api/canvases/[^/]+/boxes/[^/]+/body$")
ASK = re.compile(r"/api/canvases/[^/]+/ask$")
BOX = re.compile(r"/api/canvases/[^/]+/boxes/[^/]+$")
RETRY = re.compile(r"/api/canvases/[^/]+/boxes/[^/]+/retry$")
STREAM = re.compile(r"/api/canvases/[^/]+/boxes/[^/]+/stream$")
EXPAND = re.compile(r"/api/research/expand")
CONFIG = re.compile(r"/api/config$")
INSTRUCTIONS = re.compile(r"/api/instructions$")


def fail(page, pattern, method: str, *, status: int = 500, times: int | None = None) -> list:
    """Answer `method` on `pattern` with an error. Returns the list of requests it caught."""
    caught: list = []

    def handler(route):
        if route.request.method != method or (times is not None and len(caught) >= times):
            route.fallback()
            return
        caught.append(route.request)
        route.fulfill(status=status, json={"detail": DETAIL})

    page.route(pattern, handler)
    return caught


def drop(page, pattern, method: str = "GET") -> list:
    """Drop `method` on `pattern` before it reaches the server, the way a dead link does."""
    caught: list = []

    def handler(route):
        if route.request.method != method:
            route.fallback()
            return
        caught.append(route.request)
        route.abort()

    page.route(pattern, handler)
    return caught


def watch_errors(page) -> list[str]:
    """Uncaught errors and console errors, minus the browser's own note on a failed load."""
    problems: list[str] = []
    page.on("pageerror", lambda e: problems.append(str(e)))
    page.on(
        "console",
        lambda m: (
            problems.append(m.text)
            if m.type == "error" and "Failed to load resource" not in m.text
            else None
        ),
    )
    return problems
