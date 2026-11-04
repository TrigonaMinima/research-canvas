"""Layer 7: the boundary is this machine. Host, Origin, traversal, and upload limits."""

from __future__ import annotations

import pytest

from research_canvas import assets, config, storage
from research_canvas.api import app
from research_canvas.config import FOREIGN_HOST_MESSAGE, FOREIGN_ORIGIN_MESSAGE
from tests.fixtures.images import PNG

REMOTE_PICTURE = "https://example.com/a.png"
WITH_PICTURE = (
    "# A Picture\n\nA paragraph long enough to pass the import minimum, with a picture.\n\n"
    f"![chart]({REMOTE_PICTURE})\n"
)

# --- Host ---------------------------------------------------------------------


@pytest.mark.parametrize("host", ["evil.example", "evil.example:8000", "127.0.0.1.evil.example"])
def test_should_refuse_a_foreign_host(client, host):
    assert client.get("/api/canvases", headers={"host": host}).status_code == 400


def test_should_say_why_a_foreign_host_is_refused(client):
    response = client.get("/api/canvases", headers={"host": "evil.example"})
    assert response.json() == {"detail": FOREIGN_HOST_MESSAGE}


def test_should_refuse_a_foreign_host_on_the_app_shell(client):
    assert client.get("/", headers={"host": "evil.example"}).status_code == 400


@pytest.mark.parametrize("host", ["127.0.0.1", "127.0.0.1:49213", "localhost", "LOCALHOST:5"])
def test_should_serve_this_machine_by_name_or_address(client, host):
    assert client.get("/api/canvases", headers={"host": host}).status_code == 200


# --- Origin -------------------------------------------------------------------


def _create(client, origin, sample_markdown):
    return client.post(
        "/api/canvases",
        json={"markdown": sample_markdown},
        headers={"host": "127.0.0.1:49213", "origin": origin},
    )


@pytest.mark.parametrize(
    "origin",
    [
        "https://evil.example",
        "http://127.0.0.1:1234",  # another local port is another site
        "https://127.0.0.1:49213",
        "null",
    ],
)
def test_should_refuse_a_write_from_a_foreign_origin(client, sample_markdown, origin):
    assert _create(client, origin, sample_markdown).status_code == 403


def test_should_say_why_a_foreign_origin_is_refused(client, sample_markdown):
    response = _create(client, "https://evil.example", sample_markdown)
    assert response.json() == {"detail": FOREIGN_ORIGIN_MESSAGE}


def test_should_write_nothing_for_a_foreign_origin(client, sample_markdown, canvas_root):
    _create(client, "https://evil.example", sample_markdown)
    assert list(canvas_root.iterdir()) == []


def test_should_accept_a_write_from_the_same_origin(client, sample_markdown):
    assert _create(client, "http://127.0.0.1:49213", sample_markdown).status_code == 201


def test_should_accept_a_write_with_no_origin(client, sample_markdown):
    assert client.post("/api/canvases", json={"markdown": sample_markdown}).status_code == 201


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("PATCH", "", {"theme": "dark"}),
        ("PUT", "/boxes/b1/body", {"markdown": "# Changed\n\nText."}),
        ("DELETE", "/boxes/b1", None),
        ("POST", "/ask", {"boxId": "b1", "question": "Why?"}),
        ("POST", "/boxes/b1/retry", None),
    ],
)
def test_should_refuse_every_kind_of_write_from_a_foreign_origin(
    client, canvas, method, path, body
):
    response = client.request(
        method,
        f"/api/canvases/{canvas['id']}{path}",
        json=body,
        headers={"origin": "https://evil.example"},
    )
    assert response.status_code == 403


def test_should_refuse_an_upload_from_a_foreign_origin(client, canvas):
    response = client.post(
        f"/api/canvases/{canvas['id']}/assets",
        content=PNG,
        headers={"origin": "https://evil.example"},
    )
    assert response.status_code == 403


def test_should_refuse_a_run_started_from_a_foreign_origin(client, canvas, fake_answer):
    # A stream is a GET that spends usage, so it is guarded like a write.
    fake_answer([fake_answer.Event(kind="done")])
    response = client.get(
        f"/api/canvases/{canvas['id']}/boxes/b1/stream", headers={"origin": "https://evil.example"}
    )
    assert response.status_code == 403


# --- traversal through the routes ---------------------------------------------


@pytest.mark.parametrize(
    "canvas_id", ["..", "%2e%2e", "..%2F..%2Fetc", "%2e%2e%2f%2e%2e", ".hidden", "a%00b"]
)
def test_should_answer_404_to_an_encoded_canvas_id(client, canvas_id):
    assert client.get(f"/api/canvases/{canvas_id}").status_code == 404


@pytest.mark.parametrize("box_id", ["..", "%2e%2e", "..%2F..%2Fescape", ".b2", "b1%2F..%2F.."])
def test_should_answer_404_to_an_encoded_box_id(client, canvas, box_id):
    response = client.put(
        f"/api/canvases/{canvas['id']}/boxes/{box_id}/body", json={"markdown": "# Escaped\n"}
    )
    assert response.status_code == 404


def test_should_write_no_file_outside_the_canvas_for_an_encoded_box_id(client, canvas, canvas_root):
    client.put(
        f"/api/canvases/{canvas['id']}/boxes/..%2F..%2Fescape/body", json={"markdown": "# Out\n"}
    )
    assert sorted(p.name for p in canvas_root.parent.rglob("escape*")) == []


@pytest.mark.parametrize(
    "name", ["%2e%2e%2fcanvas.json", "..%2F..%2Froot.md", f"..%2F{'a' * 64}.png"]
)
def test_should_answer_404_to_an_encoded_asset_name(client, canvas, name):
    assert client.get(f"/api/canvases/{canvas['id']}/assets/{name}").status_code == 404


# --- upload with no Content-Length --------------------------------------------


async def _post_chunks(canvas_id: str, chunks: list[bytes]) -> tuple[int, list[bytes]]:
    """Drive the app by hand: TestClient reads a streamed body in full before the app does."""
    pulled: list[bytes] = []
    status: list[int] = []

    async def receive():
        if len(pulled) == len(chunks):
            return {"type": "http.disconnect"}
        pulled.append(chunks[len(pulled)])
        return {"type": "http.request", "body": pulled[-1], "more_body": len(pulled) < len(chunks)}

    async def send(message):
        if message["type"] == "http.response.start":
            status.append(message["status"])

    path = f"/api/canvases/{canvas_id}/assets"
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "root_path": "",
        "query_string": b"",
        "headers": [(b"host", b"127.0.0.1"), (b"transfer-encoding", b"chunked")],
        "client": ("127.0.0.1", 50000),
        "server": ("127.0.0.1", 80),
    }
    await app(scope, receive, send)
    return status[0], pulled


@pytest.fixture
def small_cap(monkeypatch):
    monkeypatch.setattr(config, "MAX_IMAGE_BYTES", 100)


async def test_should_answer_413_to_a_chunked_upload_over_the_cap(canvas_root, small_cap):
    canvas = storage.create_canvas("# Doc\n\nA paragraph long enough to pass the import minimum.\n")
    status, _ = await _post_chunks(canvas.id, [PNG[:8] + b"\x00" * 56] + [b"\x00" * 64] * 9)
    assert status == 413


async def test_should_stop_reading_a_chunked_upload_once_it_passes_the_cap(canvas_root, small_cap):
    canvas = storage.create_canvas("# Doc\n\nA paragraph long enough to pass the import minimum.\n")
    _, pulled = await _post_chunks(canvas.id, [PNG[:8] + b"\x00" * 56] + [b"\x00" * 64] * 9)
    assert len(pulled) == 2  # 128 bytes is the first count past 100


async def test_should_keep_a_chunked_upload_under_the_cap(canvas_root):
    canvas = storage.create_canvas("# Doc\n\nA paragraph long enough to pass the import minimum.\n")
    status, _ = await _post_chunks(canvas.id, [PNG[:10], PNG[10:]])
    assert status == 201


# --- remote pictures in the reader's own text ---------------------------------
# Rule: a pasted or edited body is the reader's text and is kept as written. The server
# fetches nothing for it; only an answer's pictures are localised.


@pytest.fixture
def fetches(monkeypatch):
    calls: list[str] = []

    async def fetch(url):
        calls.append(url)
        return PNG

    monkeypatch.setattr(assets, "fetch_image", fetch)
    return calls


def test_should_fetch_nothing_for_a_pasted_remote_picture(client, fetches):
    client.post("/api/canvases", json={"markdown": WITH_PICTURE})
    assert fetches == []


def test_should_keep_a_pasted_remote_picture_as_written(client, fetches):
    created = client.post("/api/canvases", json={"markdown": WITH_PICTURE}).json()
    assert storage.read_body(created["id"], "b1") == WITH_PICTURE


def test_should_render_a_pasted_remote_picture_from_its_url(client, fetches):
    created = client.post("/api/canvases", json={"markdown": WITH_PICTURE}).json()
    assert f'src="{REMOTE_PICTURE}"' in created["bodies"]["b1"]


def test_should_fetch_nothing_for_an_edited_remote_picture(client, canvas, fetches):
    client.put(f"/api/canvases/{canvas['id']}/boxes/b1/body", json={"markdown": WITH_PICTURE})
    assert fetches == []


def test_should_keep_an_edited_remote_picture_as_written(client, canvas, fetches):
    client.put(f"/api/canvases/{canvas['id']}/boxes/b1/body", json={"markdown": WITH_PICTURE})
    assert storage.read_body(canvas["id"], "b1") == WITH_PICTURE
