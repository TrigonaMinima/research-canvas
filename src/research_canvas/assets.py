"""Pictures in answers: fetched once, checked, and kept beside the canvas (US-7).

A run links pictures it found on the web. The app downloads each one after the run, so
the canvas shows it offline and no third party learns when it is reopened. The fetch
is the only request the server makes on a model's say-so, so it is guarded: http(s)
only, public addresses only on every hop, a size cap, and raster bytes only.
"""

from __future__ import annotations

import asyncio
import hashlib
import ipaddress
import re
import socket
import ssl
from collections.abc import Awaitable, Callable

import httpx

from . import config, md, storage
from .config import (
    ASSET_DIR,
    IMAGE_FETCH_TIMEOUT,
    IMAGE_USER_AGENT,
    MAX_IMAGE_REDIRECTS,
    MAX_IMAGES_PER_ANSWER,
)


class FetchError(Exception):
    """A picture could not be fetched, or what came back was not one."""


class UnsupportedImage(ValueError):
    """The bytes are not a PNG, JPEG, GIF, or WebP."""


class ImageTooLarge(ValueError):
    """The bytes are over the size cap."""


# --- what the bytes are -------------------------------------------------------


def sniff(data: bytes) -> str | None:
    """The kind of raster image by its magic bytes, never by a name or a header."""
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if data.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return "gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    return None


def save(canvas_id: str, data: bytes) -> str:
    """Store the bytes under their hash and return the path relative to the canvas."""
    # Read through the module so the cap can be lowered in tests.
    if len(data) > config.MAX_IMAGE_BYTES:
        raise ImageTooLarge(f"over {config.MAX_IMAGE_BYTES} bytes")
    kind = sniff(data)
    if kind is None:
        raise UnsupportedImage("not a PNG, JPEG, GIF, or WebP image")
    name = f"{hashlib.sha256(data).hexdigest()}.{kind}"
    storage.write_asset(canvas_id, name, data)
    return f"{ASSET_DIR}/{name}"


# --- the fetch guard ----------------------------------------------------------


def is_public(address: str) -> bool:
    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        return False
    # ::ffff:127.0.0.1 is loopback in disguise.
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    # is_global alone lets multicast through.
    return ip.is_global and not (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


async def _resolve(host: str) -> list[str]:
    loop = asyncio.get_running_loop()
    infos = await loop.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    return [str(info[4][0]) for info in infos]


# Built once: loading the CA bundle is blocking CPU work, too slow to repeat per picture
# on the event loop every answer stream shares.
_TLS = ssl.create_default_context()


def _client() -> httpx.AsyncClient:
    # Redirects are followed by hand, so every hop passes the guard.
    return httpx.AsyncClient(
        verify=_TLS,
        follow_redirects=False,
        timeout=IMAGE_FETCH_TIMEOUT,
        headers={"user-agent": IMAGE_USER_AGENT},
    )


async def _check(url: httpx.URL) -> None:
    if url.scheme not in ("http", "https") or not url.host:
        raise FetchError(f"refused: {url}")
    # Read at call time: the end-to-end tests serve pictures from loopback.
    if config.ALLOW_PRIVATE_FETCH:
        return
    # httpx resolves the host again when it connects, so a rebinding DNS server could
    # still swap the address in between. Accepted for a tool bound to localhost.
    try:
        addresses = await _resolve(url.host)
    except OSError as exc:
        raise FetchError(f"cannot resolve {url.host}") from exc
    if not addresses or not all(is_public(a) for a in addresses):
        raise FetchError(f"refused a non-public host: {url.host}")


async def _read_capped(response: httpx.Response) -> bytes:
    cap = config.MAX_IMAGE_BYTES
    declared = response.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > cap:
        raise FetchError("picture is over the size cap")
    chunks: list[bytes] = []
    size = 0
    async for chunk in response.aiter_bytes():
        size += len(chunk)
        if size > cap:
            raise FetchError("picture is over the size cap")
        chunks.append(chunk)
    return b"".join(chunks)


async def _fetch(url: str) -> bytes:
    try:
        current = httpx.URL(url)
    except httpx.InvalidURL as exc:
        raise FetchError(f"not a URL: {url}") from exc
    async with _client() as client:
        for _ in range(MAX_IMAGE_REDIRECTS + 1):
            await _check(current)
            async with client.stream("GET", current) as response:
                if response.is_redirect:
                    location = response.headers.get("location")
                    if not location:
                        raise FetchError("redirect without a location")
                    current = current.join(location)
                    continue
                if not response.is_success:
                    raise FetchError(f"status {response.status_code}")
                data = await _read_capped(response)
            if sniff(data) is None:
                raise FetchError("not a raster image")
            return data
    raise FetchError("too many redirects")


async def fetch_image(url: str) -> bytes:
    """The bytes of a public raster image, or FetchError. Nothing else escapes."""
    try:
        # One deadline for the whole fetch: httpx's timeout is per read, so a slow
        # drip could otherwise hold the answer open for minutes.
        async with asyncio.timeout(IMAGE_FETCH_TIMEOUT):
            return await _fetch(url)
    except FetchError:
        raise
    # InvalidURL is not an HTTPError; a bad redirect location raises it. An IDN host
    # that will not encode raises UnicodeError from the resolver.
    except (httpx.HTTPError, httpx.InvalidURL, UnicodeError, TimeoutError) as exc:
        raise FetchError(f"could not fetch {url}") from exc


# --- rewriting an answer ------------------------------------------------------

# ![alt](url "title"). The URL may hold one level of parentheses, as Wikimedia's do.
_IMAGE = re.compile(
    r"!\[(?P<alt>[^\]]*)\]\(\s*(?P<url>https?://(?:[^\s()]|\([^\s()]*\))+)"
    r"(?:\s+(?:\"[^\"]*\"|'[^']*'))?\s*\)"
)


def remote_images(text: str) -> list[re.Match[str]]:
    """Every remote image in the answer that markdown-it renders as one.

    The pattern finds the source spans to rewrite; the parse decides which count, so a
    URL that only appears inside a code block is left alone.
    """
    if "](http" not in text:
        return []  # most answers: no parse at all
    rendered = {
        str(child.attrGet("src"))
        for token in md.parse(text)
        if token.type == "inline"
        for child in token.children or []
        if child.type == "image"
    }
    return [m for m in _IMAGE.finditer(text) if md.normalize_link(m["url"]) in rendered]


def as_links(text: str, matches: list[re.Match[str]], local: dict[str, str] | None = None) -> str:
    """Point each picture at its local copy, or turn it into a plain link to its URL."""
    local = local or {}
    out: list[str] = []
    cursor = 0
    for match in matches:
        out.append(text[cursor : match.start()])
        path = local.get(match["url"])
        out.append(f"![{match['alt']}]({path})" if path else f"[{match['alt']}]({match['url']})")
        cursor = match.end()
    out.append(text[cursor:])
    return "".join(out)


async def localize(
    canvas_id: str,
    text: str,
    *,
    matches: list[re.Match[str]] | None = None,
    fetch: Callable[[str], Awaitable[bytes]] | None = None,
) -> str:
    """Download the answer's remote pictures and point it at the local copies.

    A picture that cannot be had becomes a plain link, so the reader still has the URL.
    """
    # The caller may have found them already, to say pictures are coming.
    if matches is None:
        matches = remote_images(text)
    if not matches:
        return text
    # Looked up at call time so a test can swap the fetcher on the module.
    fetch = fetch or fetch_image

    urls = list(dict.fromkeys(m["url"] for m in matches))[:MAX_IMAGES_PER_ANSWER]

    async def keep(url: str) -> str:
        # Hashing and writing up to 8 MB is blocking work; off the loop, beside the fetches.
        return await asyncio.to_thread(save, canvas_id, await fetch(url))

    results = await asyncio.gather(*(keep(u) for u in urls), return_exceptions=True)
    local = {url: path for url, path in zip(urls, results, strict=True) if isinstance(path, str)}
    return as_links(text, matches, local)
