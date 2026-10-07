"""Pictures in answers: sniffing, the fetch guard, storing, and rewriting links (US-7)."""

from __future__ import annotations

import httpx
import pytest
from tests.fixtures.images import GIF, HTML, JPG, PNG, SVG, WEBP

from research_canvas import assets, config, storage

# --- sniff --------------------------------------------------------------------


@pytest.mark.parametrize(
    ("data", "kind"), [(PNG, "png"), (JPG, "jpg"), (GIF, "gif"), (WEBP, "webp")]
)
def test_should_name_an_image_by_its_magic_bytes(data, kind):
    assert assets.sniff(data) == kind


@pytest.mark.parametrize("data", [SVG, HTML, b""])
def test_should_refuse_to_name_anything_that_is_not_a_raster_image(data):
    assert assets.sniff(data) is None


# --- is_public ----------------------------------------------------------------


@pytest.mark.parametrize(
    "ip",
    [
        "127.0.0.1",
        "::1",
        "10.0.0.5",
        "192.168.1.9",
        "172.16.0.1",
        "169.254.169.254",
        "fe80::1",
        "0.0.0.0",
        "240.0.0.1",
        "224.0.0.1",
    ],
)
def test_should_call_a_non_public_address_not_public(ip):
    assert assets.is_public(ip) is False


def test_should_call_a_routable_address_public():
    assert assets.is_public("93.184.216.34") is True


# --- save ---------------------------------------------------------------------


def test_should_save_an_image_under_its_hash_and_return_the_relative_path(canvas_root):
    canvas = storage.create_canvas("# Doc\n\nA paragraph long enough to pass the import minimum.\n")
    path = assets.save(canvas.id, PNG)
    assert (
        path.startswith("assets/")
        and path.endswith(".png")
        and len(path) == len("assets/") + 64 + 4
    )


def test_should_write_the_file_into_the_canvas_asset_folder(canvas_root):
    canvas = storage.create_canvas("# Doc\n\nA paragraph long enough to pass the import minimum.\n")
    path = assets.save(canvas.id, PNG)
    assert (canvas_root / canvas.id / path).read_bytes() == PNG


def test_should_return_the_same_path_for_the_same_bytes(canvas_root):
    canvas = storage.create_canvas("# Doc\n\nA paragraph long enough to pass the import minimum.\n")
    assert assets.save(canvas.id, PNG) == assets.save(canvas.id, PNG)


def test_should_keep_one_file_for_the_same_bytes_saved_twice(canvas_root):
    canvas = storage.create_canvas("# Doc\n\nA paragraph long enough to pass the import minimum.\n")
    assets.save(canvas.id, PNG)
    assets.save(canvas.id, PNG)
    assert len(list((canvas_root / canvas.id / config.ASSET_DIR).iterdir())) == 1


def test_should_refuse_to_save_an_svg(canvas_root):
    canvas = storage.create_canvas("# Doc\n\nA paragraph long enough to pass the import minimum.\n")
    with pytest.raises(assets.UnsupportedImage):
        assets.save(canvas.id, SVG)


def test_should_refuse_to_save_an_image_over_the_size_cap(canvas_root, monkeypatch):
    canvas = storage.create_canvas("# Doc\n\nA paragraph long enough to pass the import minimum.\n")
    monkeypatch.setattr(config, "MAX_IMAGE_BYTES", 10)
    monkeypatch.setattr(assets, "MAX_IMAGE_BYTES", 10, raising=False)
    with pytest.raises(assets.ImageTooLarge):
        assets.save(canvas.id, PNG)


def test_should_define_the_documented_limits():
    assert (config.ASSET_DIR, config.MAX_IMAGES_PER_ANSWER) == ("assets", 6)
    assert config.MAX_IMAGE_BYTES == 8 * 1024 * 1024
    assert config.IMAGE_FETCH_TIMEOUT == 10.0


# --- fetch_image: the guard ---------------------------------------------------


def _resolving(monkeypatch, *ips: str) -> None:
    async def resolve(host):
        return list(ips)

    monkeypatch.setattr(assets, "_resolve", resolve)


def _serving(monkeypatch, handler) -> list[str]:
    """Route every request through `handler`; return the URLs it was asked for."""
    seen: list[str] = []

    def wrapped(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return handler(request)

    monkeypatch.setattr(
        assets, "_client", lambda: httpx.AsyncClient(transport=httpx.MockTransport(wrapped))
    )
    return seen


@pytest.fixture(autouse=True)
def _no_private_override(monkeypatch):
    monkeypatch.setattr(config, "ALLOW_PRIVATE_FETCH", False)
    monkeypatch.setattr(assets, "ALLOW_PRIVATE_FETCH", False, raising=False)


@pytest.mark.parametrize("url", ["file:///etc/passwd", "ftp://example.com/a.png"])
async def test_should_refuse_a_scheme_other_than_http(url, monkeypatch):
    _resolving(monkeypatch, "93.184.216.34")
    with pytest.raises(assets.FetchError):
        await assets.fetch_image(url)


@pytest.mark.parametrize("ip", ["127.0.0.1", "10.0.0.5", "169.254.169.254", "::1"])
async def test_should_refuse_a_host_that_resolves_to_a_non_public_address(ip, monkeypatch):
    _resolving(monkeypatch, ip)
    _serving(monkeypatch, lambda r: httpx.Response(200, content=PNG))
    with pytest.raises(assets.FetchError):
        await assets.fetch_image("https://evil.example/a.png")


async def test_should_refuse_a_host_when_any_resolved_address_is_non_public(monkeypatch):
    _resolving(monkeypatch, "93.184.216.34", "10.0.0.5")
    _serving(monkeypatch, lambda r: httpx.Response(200, content=PNG))
    with pytest.raises(assets.FetchError):
        await assets.fetch_image("https://mixed.example/a.png")


async def test_should_not_send_a_request_to_a_refused_host(monkeypatch):
    _resolving(monkeypatch, "127.0.0.1")
    seen = _serving(monkeypatch, lambda r: httpx.Response(200, content=PNG))
    with pytest.raises(assets.FetchError):
        await assets.fetch_image("https://evil.example/a.png")
    assert seen == []


async def test_should_return_the_bytes_of_a_public_image(monkeypatch):
    _resolving(monkeypatch, "93.184.216.34")
    _serving(monkeypatch, lambda r: httpx.Response(200, content=PNG))
    assert await assets.fetch_image("https://example.com/a.png") == PNG


async def test_should_allow_a_loopback_host_when_the_test_override_is_on(monkeypatch):
    _resolving(monkeypatch, "127.0.0.1")
    _serving(monkeypatch, lambda r: httpx.Response(200, content=PNG))
    monkeypatch.setattr(config, "ALLOW_PRIVATE_FETCH", True)
    monkeypatch.setattr(assets, "ALLOW_PRIVATE_FETCH", True, raising=False)
    assert await assets.fetch_image("http://127.0.0.1:9/a.png") == PNG


# --- fetch_image: redirects, size, content ------------------------------------


async def test_should_refuse_a_redirect_to_a_private_host(monkeypatch):
    async def resolve(host):
        return ["10.0.0.5"] if host == "internal.example" else ["93.184.216.34"]

    monkeypatch.setattr(assets, "_resolve", resolve)

    def handler(request):
        if request.url.host == "public.example":
            return httpx.Response(302, headers={"location": "http://internal.example/a.png"})
        return httpx.Response(200, content=PNG)

    seen = _serving(monkeypatch, handler)
    with pytest.raises(assets.FetchError):
        await assets.fetch_image("https://public.example/a.png")
    assert not any("internal.example" in url for url in seen)


async def test_should_follow_a_redirect_to_another_public_host(monkeypatch):
    _resolving(monkeypatch, "93.184.216.34")

    def handler(request):
        if request.url.path == "/a.png":
            return httpx.Response(302, headers={"location": "https://cdn.example/b.png"})
        return httpx.Response(200, content=PNG)

    _serving(monkeypatch, handler)
    assert await assets.fetch_image("https://example.com/a.png") == PNG


async def test_should_refuse_more_than_three_redirects(monkeypatch):
    _resolving(monkeypatch, "93.184.216.34")

    def handler(request):
        n = int(request.url.path.strip("/") or 0)
        return httpx.Response(302, headers={"location": f"https://example.com/{n + 1}"})

    _serving(monkeypatch, handler)
    with pytest.raises(assets.FetchError):
        await assets.fetch_image("https://example.com/0")


async def test_should_refuse_a_body_over_the_size_cap(monkeypatch):
    _resolving(monkeypatch, "93.184.216.34")
    _serving(monkeypatch, lambda r: httpx.Response(200, content=PNG + b"\x00" * 100))
    monkeypatch.setattr(config, "MAX_IMAGE_BYTES", 50)
    monkeypatch.setattr(assets, "MAX_IMAGE_BYTES", 50, raising=False)
    with pytest.raises(assets.FetchError):
        await assets.fetch_image("https://example.com/big.png")


async def test_should_refuse_a_body_that_is_not_an_image(monkeypatch):
    _resolving(monkeypatch, "93.184.216.34")
    _serving(monkeypatch, lambda r: httpx.Response(200, content=HTML))
    with pytest.raises(assets.FetchError):
        await assets.fetch_image("https://example.com/page")


async def test_should_refuse_an_error_status(monkeypatch):
    _resolving(monkeypatch, "93.184.216.34")
    _serving(monkeypatch, lambda r: httpx.Response(404))
    with pytest.raises(assets.FetchError):
        await assets.fetch_image("https://example.com/missing.png")


# --- localize -----------------------------------------------------------------


@pytest.fixture
def cid(canvas_root):
    return storage.create_canvas(
        "# Doc\n\nA paragraph long enough to pass the import minimum.\n"
    ).id


def _fake_fetch(body: bytes = PNG, calls: list | None = None):
    async def fetch(url):
        if calls is not None:
            calls.append(url)
        if isinstance(body, Exception):
            raise body
        return body

    return fetch


async def test_should_rewrite_a_remote_image_to_a_local_asset(cid):
    out = await assets.localize(cid, "![A cat](https://example.com/cat.png)", fetch=_fake_fetch())
    assert out.startswith("![A cat](assets/") and out.endswith(".png)")


async def test_should_save_the_fetched_bytes_into_the_canvas(cid, canvas_root):
    await assets.localize(cid, "![A cat](https://example.com/cat.png)", fetch=_fake_fetch())
    assert len(list((canvas_root / cid / "assets").iterdir())) == 1


async def test_should_turn_a_failed_fetch_into_a_plain_link(cid):
    fetch = _fake_fetch(assets.FetchError("nope"))
    out = await assets.localize(cid, "![A cat](https://example.com/cat.png)", fetch=fetch)
    assert out == "[A cat](https://example.com/cat.png)"


async def test_should_turn_non_image_bytes_into_a_plain_link(cid):
    out = await assets.localize(
        cid, "![A cat](https://example.com/cat.png)", fetch=_fake_fetch(HTML)
    )
    assert out == "[A cat](https://example.com/cat.png)"


async def test_should_fetch_at_most_the_per_answer_limit(cid):
    calls: list[str] = []
    text = "\n".join(f"![i{n}](https://example.com/{n}.png)" for n in range(8))
    await assets.localize(cid, text, fetch=_fake_fetch(calls=calls))
    assert len(calls) == config.MAX_IMAGES_PER_ANSWER


async def test_should_turn_the_images_past_the_limit_into_links(cid):
    text = "\n".join(f"![i{n}](https://example.com/{n}.png)" for n in range(8))
    out = await assets.localize(cid, text, fetch=_fake_fetch())
    assert out.count("](https://example.com/") == 2 and "[i7](https://example.com/7.png)" in out


async def test_should_leave_an_image_in_a_fenced_code_block_alone(cid):
    text = "```\n![x](https://example.com/a.png)\n```\n"
    calls: list[str] = []
    out = await assets.localize(cid, text, fetch=_fake_fetch(calls=calls))
    assert (out, calls) == (text, [])


async def test_should_return_text_without_images_unchanged(cid):
    text = "Plain *prose* with a [link](https://example.com)."
    assert await assets.localize(cid, text, fetch=_fake_fetch()) == text


async def test_should_leave_an_already_local_image_alone(cid):
    text = "![x](assets/" + "a" * 64 + ".png)"
    calls: list[str] = []
    assert await assets.localize(cid, text, fetch=_fake_fetch(calls=calls)) == text
    assert calls == []


async def test_should_fetch_the_same_url_once(cid):
    calls: list[str] = []
    text = "![a](https://example.com/a.png)\n\n![b](https://example.com/a.png)"
    await assets.localize(cid, text, fetch=_fake_fetch(calls=calls))
    assert calls == ["https://example.com/a.png"]


async def test_should_keep_the_surrounding_text(cid):
    out = await assets.localize(
        cid, "Before.\n\n![A](https://example.com/a.png)\n\nAfter.", fetch=_fake_fetch()
    )
    assert out.startswith("Before.\n\n![A](assets/") and out.endswith("\n\nAfter.")


def test_should_name_a_contact_url_in_the_user_agent():
    # Wikimedia's robot policy refuses a client that gives no way to reach its owner.
    assert "(https://" in config.IMAGE_USER_AGENT


# --- as_links: web search off, so nothing is downloaded ----------------------


def _links(text):
    return assets.as_links(text, assets.remote_images(text))


def test_should_turn_a_remote_image_into_a_plain_link():
    assert _links("![A cat](https://example.com/cat.png)") == "[A cat](https://example.com/cat.png)"


def test_should_turn_every_remote_image_into_a_link():
    text = "![a](https://example.com/a.png) and ![b](http://example.com/b.png)"
    assert _links(text) == "[a](https://example.com/a.png) and [b](http://example.com/b.png)"


def test_should_link_every_image_past_the_limit_when_making_links():
    text = "\n".join(
        f"![p{i}](https://example.com/{i}.png)" for i in range(config.MAX_IMAGES_PER_ANSWER + 2)
    )
    assert "![" not in _links(text)


def test_should_save_no_file_when_making_links(cid, canvas_root):
    _links("![A cat](https://example.com/cat.png)")
    assert not list((canvas_root / cid / "assets").glob("*"))


def test_should_leave_a_local_image_alone_when_making_links():
    text = f"![shot](assets/{'a' * 64}.png)"
    assert _links(text) == text
