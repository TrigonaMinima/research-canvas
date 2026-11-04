"""A merge stream that drops is closed, never reconnected: a reconnect is a second run."""

# Guards #48 (streams and retry start a second run on a box that has one).

from __future__ import annotations

import pytest

from tests.fixtures.merging import MERGE_BUTTON, PANE
from tests.fixtures.selection import QUOTE, ask

pytestmark = pytest.mark.e2e

# Long enough for a browser told to come back after 100 ms to have done so many times.
WAIT_MS = 1500


def _dropped_merge(page) -> list[str]:
    """Open a merge whose stream ends at once, and hand back every stream request."""
    hits: list[str] = []

    def drop(route):
        hits.append(route.request.url)
        # A stream that ends without a `done` is a dropped one. `retry` keeps the wait short.
        route.fulfill(status=200, content_type="text/event-stream", body="retry: 100\n\n")

    page.route("**/merge/stream", drop)
    ask(page, "b1", QUOTE, "What is a residual connection?")
    page.wait_for_selector('[data-box="b2"][data-status="done"]', timeout=20000)
    page.click(MERGE_BUTTON.format(box="b2"))
    page.wait_for_selector("[data-merge-ask]")
    page.fill("[data-merge-input]", "Fold it in.")
    page.click("[data-merge-send]")
    page.wait_for_selector(PANE.format(box="b1"))
    page.wait_for_timeout(WAIT_MS)
    return hits


def test_should_open_a_dropped_merge_stream_only_once(canvas):
    assert len(_dropped_merge(canvas)) == 1
