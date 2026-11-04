"""Layer 7 in a real browser: the Host and Origin checks never refuse the app's own page."""

from __future__ import annotations

import pytest

from tests.fixtures.e2e_app import SAMPLE_DOC, canvas_from

pytestmark = pytest.mark.e2e


def _save_through_the_page(page) -> int:
    """A write the browser sends with its own Origin, which is what the check reads."""
    return page.evaluate(
        """async () => {
            const id = new URLSearchParams(location.search).get('c');
            const res = await fetch(`/api/canvases/${id}`, {
                method: 'PATCH',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({theme: 'dark'}),
            });
            return res.status;
        }"""
    )


def test_should_save_from_the_page_on_127_0_0_1(app):
    canvas_from(app, SAMPLE_DOC)
    assert _save_through_the_page(app) == 200


def test_should_save_from_the_page_on_localhost(app, server):
    app.goto(server.replace("127.0.0.1", "localhost") + "/")
    app.wait_for_selector("[data-empty]")
    canvas_from(app, SAMPLE_DOC)
    assert _save_through_the_page(app) == 200
