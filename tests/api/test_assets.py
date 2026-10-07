"""Pictures over HTTP: serving, uploading, and answers whose pictures are fetched once (US-7)."""

from __future__ import annotations

import re

import pytest
from tests.fixtures.images import GIF, HTML, PNG, SVG

from research_canvas import assets, config

REMOTE = "![x](https://example.com/a.png)"


@pytest.fixture
def uploaded(client, canvas):
    """The path of a PNG saved through the upload endpoint."""
    response = client.post(f"/api/canvases/{canvas['id']}/assets", content=PNG)
    return response.json()["path"]


def _stream(client, canvas, fake_answer, text, monkeypatch, fetch=None):
    event = fake_answer.Event
    fake_answer([event(kind="text", text=text), event(kind="done")])

    async def default_fetch(url):
        return PNG

    monkeypatch.setattr(assets, "fetch_image", fetch or default_fetch)
    asked = client.post(
        f"/api/canvases/{canvas['id']}/ask",
        json={"boxId": "b1", "question": "Show me", "x": 900, "y": 80},
    ).json()["box"]
    body = client.get(f"/api/canvases/{canvas['id']}/boxes/{asked['id']}/stream").text
    return asked["id"], body


# --- upload -------------------------------------------------------------------


def test_should_answer_201_to_an_uploaded_image(client, canvas):
    assert client.post(f"/api/canvases/{canvas['id']}/assets", content=PNG).status_code == 201


def test_should_return_the_relative_path_of_an_uploaded_image(uploaded):
    assert re.fullmatch(r"assets/[0-9a-f]{64}\.png", uploaded)


def test_should_return_the_same_path_for_the_same_upload_twice(client, canvas, uploaded):
    again = client.post(f"/api/canvases/{canvas['id']}/assets", content=PNG).json()["path"]
    assert again == uploaded


def test_should_accept_a_gif_upload(client, canvas):
    path = client.post(f"/api/canvases/{canvas['id']}/assets", content=GIF).json()["path"]
    assert path.endswith(".gif")


@pytest.mark.parametrize("body", [SVG, HTML, b""])
def test_should_answer_415_to_an_upload_that_is_not_a_raster_image(client, canvas, body):
    assert client.post(f"/api/canvases/{canvas['id']}/assets", content=body).status_code == 415


def test_should_answer_413_to_an_upload_over_the_size_cap(client, canvas, monkeypatch):
    monkeypatch.setattr(config, "MAX_IMAGE_BYTES", 10)
    monkeypatch.setattr(assets, "MAX_IMAGE_BYTES", 10, raising=False)
    assert client.post(f"/api/canvases/{canvas['id']}/assets", content=PNG).status_code == 413


def test_should_answer_404_to_an_upload_for_an_unknown_canvas(client):
    assert client.post("/api/canvases/nope/assets", content=PNG).status_code == 404


# --- serving ------------------------------------------------------------------


def _url(canvas, path):
    return f"/api/canvases/{canvas['id']}/{path}"


def test_should_serve_an_uploaded_image_with_its_bytes(client, canvas, uploaded):
    assert client.get(_url(canvas, uploaded)).content == PNG


def test_should_serve_an_image_with_an_image_content_type(client, canvas, uploaded):
    assert client.get(_url(canvas, uploaded)).headers["content-type"] == "image/png"


def test_should_serve_a_gif_as_image_gif(client, canvas):
    path = client.post(f"/api/canvases/{canvas['id']}/assets", content=GIF).json()["path"]
    assert client.get(_url(canvas, path)).headers["content-type"] == "image/gif"


def test_should_forbid_content_sniffing_on_an_image(client, canvas, uploaded):
    assert client.get(_url(canvas, uploaded)).headers["x-content-type-options"] == "nosniff"


def test_should_mark_an_image_immutable_for_caching(client, canvas, uploaded):
    assert "immutable" in client.get(_url(canvas, uploaded)).headers["cache-control"]


def test_should_answer_404_to_an_asset_that_does_not_exist(client, canvas):
    assert client.get(_url(canvas, f"assets/{'b' * 64}.png")).status_code == 404


@pytest.mark.parametrize("name", ["..%2Fcanvas.json", "canvas.json", f"{'a' * 64}.svg"])
def test_should_answer_404_to_an_invalid_asset_name(client, canvas, name):
    assert client.get(_url(canvas, f"assets/{name}")).status_code == 404


def test_should_answer_404_to_an_asset_of_an_unknown_canvas(client, uploaded):
    assert client.get(f"/api/canvases/nope/{uploaded}").status_code == 404


# --- rendered HTML resolves assets --------------------------------------------


def test_should_resolve_assets_in_the_canvas_view(client, canvas, uploaded):
    client.put(_url(canvas, "boxes/b1/body"), json={"markdown": f"# Doc\n\n![pic]({uploaded})\n"})
    html = client.get(f"/api/canvases/{canvas['id']}").json()["bodies"]["b1"]
    assert f'src="/api/canvases/{canvas["id"]}/{uploaded}"' in html


def test_should_resolve_assets_in_the_html_of_a_saved_body(client, canvas, uploaded):
    saved = client.put(
        _url(canvas, "boxes/b1/body"), json={"markdown": f"# Doc\n\n![pic]({uploaded})\n"}
    ).json()
    assert f'src="/api/canvases/{canvas["id"]}/{uploaded}"' in saved["html"]


def test_should_resolve_assets_in_the_stream_done_event(client, canvas, fake_answer, monkeypatch):
    _, body = _stream(client, canvas, fake_answer, REMOTE, monkeypatch)
    assert f'src=\\"/api/canvases/{canvas["id"]}/assets/' in body


# --- localizing an answer -----------------------------------------------------


def test_should_save_the_answer_with_a_local_picture(client, canvas, fake_answer, monkeypatch):
    box, _ = _stream(client, canvas, fake_answer, REMOTE, monkeypatch)
    saved = client.get(_url(canvas, f"boxes/{box}/body")).json()["markdown"]
    assert "assets/" in saved


def test_should_not_keep_the_remote_url_in_the_saved_answer(
    client, canvas, fake_answer, monkeypatch
):
    box, _ = _stream(client, canvas, fake_answer, REMOTE, monkeypatch)
    saved = client.get(_url(canvas, f"boxes/{box}/body")).json()["markdown"]
    assert "example.com/a.png" not in saved


def test_should_fall_back_to_a_link_when_the_picture_cannot_be_fetched(
    client, canvas, fake_answer, monkeypatch
):
    async def failing(url):
        raise assets.FetchError("down")

    box, _ = _stream(client, canvas, fake_answer, REMOTE, monkeypatch, fetch=failing)
    saved = client.get(_url(canvas, f"boxes/{box}/body")).json()["markdown"]
    assert saved == "[x](https://example.com/a.png)"


def test_should_send_a_picture_status_when_the_answer_has_a_remote_image(
    client, canvas, fake_answer, monkeypatch
):
    _, body = _stream(client, canvas, fake_answer, REMOTE, monkeypatch)
    statuses = re.findall(r"event: status\ndata: (.*)", body)
    assert any("picture" in data.lower() for data in statuses)


def test_should_send_no_picture_status_when_the_answer_has_no_image(
    client, canvas, fake_answer, monkeypatch
):
    _, body = _stream(client, canvas, fake_answer, "Just words.", monkeypatch)
    statuses = re.findall(r"event: status\ndata: (.*)", body)
    assert not any("picture" in data.lower() for data in statuses)
