"""Which model wrote what: the answer header, the drafted brief, the research report."""

from __future__ import annotations

import json

import pytest
from playwright.sync_api import expect
from tests.fixtures.contract import make_box, make_view
from tests.fixtures.fake_claude import MODEL
from tests.fixtures.selection import answer_from_root

from .test_research_topic import draft, finished

pytestmark = pytest.mark.e2e

ROOT = '[data-box="b1"]'
ANSWER = '[data-box="b2"]'
TAG = ".box__head [data-model]"


# --- an answer box --------------------------------------------------------------


def test_an_answered_box_names_its_model_in_the_header(canvas):
    answer_from_root(canvas)
    expect(canvas.locator(f"{ANSWER} {TAG}")).to_contain_text(MODEL)


def test_the_model_tag_says_what_it_is_to_a_screen_reader(canvas):
    answer_from_root(canvas)
    expect(canvas.locator(f"{ANSWER} {TAG}")).to_have_text(f"Answered by {MODEL}")


def test_the_model_tag_is_shown_as_written_not_in_capitals(canvas):
    answer_from_root(canvas)
    tag = canvas.locator(f"{ANSWER} {TAG}")
    assert tag.evaluate("el => getComputedStyle(el).textTransform") == "none"


def test_the_model_tag_survives_a_reload(canvas):
    answer_from_root(canvas)
    canvas.reload()
    expect(canvas.locator(f"{ANSWER} {TAG}")).to_contain_text(MODEL)


def test_a_pasted_document_names_no_model(canvas):
    expect(canvas.locator(f"{ROOT} {TAG}")).to_be_hidden()


# --- the brief ------------------------------------------------------------------


def test_no_model_is_named_before_a_brief_is_drafted(app):
    app.click('[data-tab="research"]')
    expect(app.locator("[data-research-model]")).to_be_hidden()


def test_the_drafted_brief_names_its_model(app):
    draft(app)
    expect(app.locator("[data-research-model]")).to_contain_text(MODEL)


def test_the_brief_label_keeps_its_own_name(app):
    draft(app)
    expect(app.get_by_label("Research brief", exact=True)).to_be_visible()


# --- the research report ----------------------------------------------------------


def test_a_researched_root_names_the_model_that_wrote_it(app):
    root = finished(app)
    expect(root.locator(TAG)).to_contain_text(MODEL)


def test_the_research_model_tag_says_what_it_is(app):
    root = finished(app)
    expect(root.locator(TAG)).to_have_text(f"Researched by {MODEL}")


# --- a canvas saved before boxes kept their model ----------------------------------


@pytest.fixture
def older(page, server: str):
    """A researched canvas whose root box predates the model field."""
    root = make_box()
    root.pop("model")
    view = make_view(
        boxes=[root],
        anchors=[],
        bodies={"b1": "<h1>A Mocked Paper</h1>"},
        research={
            "topic": "t",
            "prompt": "p",
            "model": "opus",
            "activity": [],
            "seen": [],
            "cited": [],
            "unverified": [],
            "finishedAt": None,
        },
    )
    page.route("**/api/canvases", lambda r: r.fulfill(json=[]))
    page.route("**/api/canvases/demo", lambda r: r.fulfill(body=json.dumps(view)))
    page.goto(f"{server}/?c=demo")
    page.wait_for_selector(ROOT)
    return page


def test_an_older_researched_root_falls_back_to_the_research_model(older):
    expect(older.locator(f"{ROOT} {TAG}")).to_contain_text("opus")
