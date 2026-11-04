"""Layer 7 below HTTP: unsafe link schemes in a body, and ids that try to leave the canvas."""

from __future__ import annotations

import pytest

from research_canvas import md, storage

# --- link and image schemes ---------------------------------------------------


@pytest.mark.parametrize(
    "source",
    [
        "[x](javascript:alert(1))",
        "[x](JAVASCRIPT:alert(1))",
        "[x]( javascript:alert(1) )",
        "[x](vbscript:msgbox(1))",
        "[x](file:///etc/passwd)",
        "[x](data:text/html,<script>alert(1)</script>)",
        "<javascript:alert(1)>",
    ],
)
def test_should_render_no_link_for_an_unsafe_scheme(source):
    assert "href" not in md.render(source)


def test_should_not_linkify_a_bare_javascript_url():
    assert "href" not in md.render("See javascript:alert(1) for details.")


@pytest.mark.parametrize(
    "source",
    [
        "![x](data:image/svg+xml;base64,PHN2Zz48L3N2Zz4=)",
        "![x](data:image/png;base64,iVBORw0KGgo=)",
        "![x](DATA:image/gif;base64,R0lGODlh)",
        "![x](javascript:alert(1))",
    ],
)
def test_should_render_no_picture_for_an_unsafe_source(source):
    assert "<img" not in md.render(source)


@pytest.mark.parametrize(
    ("source", "attr"),
    [
        ("[x](https://example.com/a)", 'href="https://example.com/a"'),
        ("[x](mailto:a@example.com)", 'href="mailto:a@example.com"'),
        ("![x](https://example.com/a.png)", 'src="https://example.com/a.png"'),
        ("![x](assets/a.png)", 'src="assets/a.png"'),
    ],
)
def test_should_keep_a_safe_link_or_picture(source, attr):
    assert attr in md.render(source)


# --- ids that name a file -----------------------------------------------------


@pytest.fixture
def cid(canvas_root):
    return storage.create_canvas(
        "# Doc\n\nA paragraph long enough to pass the import minimum.\n"
    ).id


UNSAFE_IDS = ["../escape", "..", ".hidden", "b2/../../escape", "", "-b2"]


@pytest.mark.parametrize("box_id", UNSAFE_IDS)
def test_should_refuse_to_write_a_body_under_an_unsafe_box_id(cid, box_id):
    with pytest.raises(storage.CanvasNotFound):
        storage.write_body(cid, box_id, "text")


@pytest.mark.parametrize("box_id", UNSAFE_IDS)
def test_should_refuse_to_delete_a_body_under_an_unsafe_box_id(cid, box_id):
    with pytest.raises(storage.CanvasNotFound):
        storage.delete_body(cid, box_id)


def test_should_read_nothing_through_an_unsafe_box_id(cid, canvas_root):
    (canvas_root / cid / "secret.md").write_text("private")
    with pytest.raises(storage.CanvasNotFound):
        storage.read_body(cid, "../secret")


def test_should_write_no_file_outside_the_canvas_for_an_unsafe_box_id(cid, canvas_root):
    with pytest.raises(storage.CanvasNotFound):
        storage.write_body(cid, "../../escape", "text")
    assert list(canvas_root.parent.rglob("escape*")) == []


@pytest.mark.parametrize("box_id", UNSAFE_IDS)
def test_should_refuse_a_merge_file_under_an_unsafe_box_id(cid, box_id):
    with pytest.raises(storage.CanvasNotFound):
        storage.delete_merge(cid, box_id)


@pytest.mark.parametrize("box_id", ["b2", "b10", "b2.v1", "b_2-a"])
def test_should_accept_a_plain_box_id(cid, box_id):
    storage.write_body(cid, box_id, "text")
    assert storage.read_body(cid, box_id) == "text"
