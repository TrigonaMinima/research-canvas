"""Every branch of the picture fetch guard: resolving, parsing, redirects, time, and size."""

from __future__ import annotations

import asyncio
import socket
import time

import httpx
import pytest

from research_canvas import assets, config
from tests.fixtures.images import PNG

PUBLIC = "93.184.216.34"


@pytest.fixture(autouse=True)
def _no_private_override(monkeypatch):
    monkeypatch.setattr(config, "ALLOW_PRIVATE_FETCH", False)


def _resolving(monkeypatch, resolve) -> None:
    monkeypatch.setattr(assets, "_resolve", resolve)


async def _public(host):
    return [PUBLIC]


def _serving(monkeypatch, handler) -> list[str]:
    """Route every request through `handler`; return the URLs it was asked for."""
    seen: list[str] = []

    async def wrapped(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return handler(request)

    monkeypatch.setattr(
        assets, "_client", lambda: httpx.AsyncClient(transport=httpx.MockTransport(wrapped))
    )
    return seen


class _Drip(httpx.AsyncByteStream):
    """A body that arrives in pieces, with no declared length."""

    def __init__(self, chunks: list[bytes], delay: float = 0.0) -> None:
        self.chunks, self.delay, self.sent = chunks, delay, 0

    async def __aiter__(self):
        for chunk in self.chunks:
            if self.delay:
                await asyncio.sleep(self.delay)
            self.sent += 1
            yield chunk


# --- resolving the host -------------------------------------------------------


async def test_should_refuse_a_host_that_does_not_resolve(monkeypatch):
    async def fail(host):
        raise socket.gaierror(socket.EAI_NONAME, "nodename nor servname provided")

    _resolving(monkeypatch, fail)
    _serving(monkeypatch, lambda r: httpx.Response(200, content=PNG))
    with pytest.raises(assets.FetchError, match="cannot resolve"):
        await assets.fetch_image("https://nowhere.example/a.png")


async def test_should_send_no_request_when_the_host_does_not_resolve(monkeypatch):
    async def fail(host):
        raise socket.gaierror(socket.EAI_NONAME, "no such host")

    _resolving(monkeypatch, fail)
    seen = _serving(monkeypatch, lambda r: httpx.Response(200, content=PNG))
    with pytest.raises(assets.FetchError):
        await assets.fetch_image("https://nowhere.example/a.png")
    assert seen == []


async def test_should_refuse_a_host_that_resolves_to_no_address(monkeypatch):
    async def empty(host):
        return []

    _resolving(monkeypatch, empty)
    seen = _serving(monkeypatch, lambda r: httpx.Response(200, content=PNG))
    with pytest.raises(assets.FetchError, match="non-public"):
        await assets.fetch_image("https://empty.example/a.png")
    assert seen == []


# --- IPv4 addresses written as IPv6 -------------------------------------------


@pytest.mark.parametrize("ip", ["::ffff:127.0.0.1", "::ffff:10.0.0.5", "::ffff:169.254.169.254"])
def test_should_call_an_ipv4_mapped_private_address_not_public(ip):
    assert assets.is_public(ip) is False


def test_should_call_an_ipv4_mapped_routable_address_public():
    # Without this, the cases above pass even with the unwrap gone.
    assert assets.is_public(f"::ffff:{PUBLIC}") is True


def test_should_call_something_that_is_not_an_address_not_public():
    assert assets.is_public("not-an-ip") is False


# --- URLs that will not parse -------------------------------------------------


@pytest.mark.parametrize("url", ["http://a.example:port/a.png", "http://a\x00b.example/a.png"])
async def test_should_refuse_a_url_that_will_not_parse(monkeypatch, url):
    _resolving(monkeypatch, _public)
    seen = _serving(monkeypatch, lambda r: httpx.Response(200, content=PNG))
    with pytest.raises(assets.FetchError, match="not a URL"):
        await assets.fetch_image(url)
    assert seen == []


async def test_should_refuse_a_redirect_to_a_location_that_will_not_parse(monkeypatch):
    _resolving(monkeypatch, _public)
    seen = _serving(monkeypatch, lambda r: httpx.Response(302, headers={"location": "http://[::1"}))
    with pytest.raises(assets.FetchError):
        await assets.fetch_image("https://example.com/a.png")
    assert len(seen) == 1


async def test_should_refuse_a_redirect_with_no_location(monkeypatch):
    _resolving(monkeypatch, _public)
    seen = _serving(monkeypatch, lambda r: httpx.Response(302))
    with pytest.raises(assets.FetchError, match="without a location"):
        await assets.fetch_image("https://example.com/a.png")
    assert len(seen) == 1


# --- the deadline over the whole fetch ----------------------------------------


@pytest.fixture
def short_deadline(monkeypatch):
    # assets imports the timeout by value, so the module binding is the one to change.
    monkeypatch.setattr(assets, "IMAGE_FETCH_TIMEOUT", 0.3)


async def test_should_give_up_on_a_slow_drip_at_the_deadline(monkeypatch, short_deadline):
    _resolving(monkeypatch, _public)
    # Each piece is quick, so a per-read timeout never fires; only the whole-fetch one can.
    drip = _Drip([PNG] + [b"\x00"] * 100, delay=0.05)
    _serving(monkeypatch, lambda r: httpx.Response(200, stream=drip))
    with pytest.raises(assets.FetchError, match="could not fetch"):
        await assets.fetch_image("https://slow.example/a.png")


async def test_should_stop_a_slow_drip_well_before_it_ends(monkeypatch, short_deadline):
    _resolving(monkeypatch, _public)
    drip = _Drip([PNG] + [b"\x00"] * 100, delay=0.05)
    _serving(monkeypatch, lambda r: httpx.Response(200, stream=drip))
    started = time.monotonic()
    with pytest.raises(assets.FetchError):
        await assets.fetch_image("https://slow.example/a.png")
    assert time.monotonic() - started < 2.0  # the whole drip would take five seconds


# --- the size cap on a body with no declared length ---------------------------


@pytest.fixture
def small_cap(monkeypatch):
    monkeypatch.setattr(config, "MAX_IMAGE_BYTES", 100)


def _undeclared(drip: _Drip) -> httpx.Response:
    response = httpx.Response(200, stream=drip)
    assert "content-length" not in response.headers  # the declared-length cap cannot fire
    return response


async def test_should_refuse_a_streamed_body_over_the_size_cap(monkeypatch, small_cap):
    _resolving(monkeypatch, _public)
    drip = _Drip([PNG[:8] + b"\x00" * 56] + [b"\x00" * 64] * 9)
    _serving(monkeypatch, lambda r: _undeclared(drip))
    with pytest.raises(assets.FetchError, match="size cap"):
        await assets.fetch_image("https://example.com/big.png")


async def test_should_stop_reading_a_streamed_body_once_it_passes_the_cap(monkeypatch, small_cap):
    _resolving(monkeypatch, _public)
    drip = _Drip([PNG[:8] + b"\x00" * 56] + [b"\x00" * 64] * 9)
    _serving(monkeypatch, lambda r: _undeclared(drip))
    with pytest.raises(assets.FetchError):
        await assets.fetch_image("https://example.com/big.png")
    assert drip.sent == 2  # 128 bytes is the first count past 100


async def test_should_keep_a_streamed_body_under_the_cap(monkeypatch):
    _resolving(monkeypatch, _public)
    drip = _Drip([PNG[:10], PNG[10:]])
    _serving(monkeypatch, lambda r: _undeclared(drip))
    assert await assets.fetch_image("https://example.com/a.png") == PNG


async def test_should_resolve_a_literal_address_to_itself():
    assert await assets._resolve("127.0.0.1") == ["127.0.0.1"]
