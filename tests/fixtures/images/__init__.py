"""Tiny image bodies, built in code so no binary is committed."""

from __future__ import annotations

import struct
import zlib


def _chunk(kind: bytes, data: bytes) -> bytes:
    body = kind + data
    return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))


def make_png(width: int = 2, height: int = 2) -> bytes:
    """A valid solid-red PNG a browser will decode."""
    row = b"\x00" + b"\xff\x00\x00" * width
    return (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + _chunk(b"IDAT", zlib.compress(row * height))
        + _chunk(b"IEND", b"")
    )


PNG = make_png()
GIF = b"GIF89a" + b"\x01\x00\x01\x00\x00\x00\x00;"
JPG = b"\xff\xd8\xff\xe0" + b"\x00" * 16
WEBP = b"RIFF\x24\x00\x00\x00WEBPVP8 " + b"\x00" * 16
SVG = b'<svg xmlns="http://www.w3.org/2000/svg" width="1" height="1"><script>1</script></svg>'
HTML = b"<!doctype html><html><body>not a picture</body></html>"
