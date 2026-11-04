"""A picture in a table cell renders as an <img> inside its <td>."""

# Guards ebccccc (fix: keep pictures in table cells to a sensible height), issue #23.

from __future__ import annotations

import re

from research_canvas import md

LOCAL = "![A cat](assets/" + "a" * 64 + ".png)"
BASE = "/api/canvases/c1/"


# --- pictures in table cells (issue #23: comparing things side by side) ---------


def table_with(picture: str) -> str:
    return f"| Model | Picture |\n| --- | --- |\n| A | {picture} |\n"


TABLE_WITH_LOCAL = table_with(LOCAL)
TABLE_WITH_REMOTE = table_with("![x](https://example.com/a.png)")
IMG_IN_CELL = re.compile(r"<td[^>]*>[^<]*<img [^>]*>[^<]*</td>")


def test_should_render_a_local_picture_inside_a_table_cell():
    assert IMG_IN_CELL.search(md.render(TABLE_WITH_LOCAL, base=BASE))


def test_should_resolve_a_local_picture_in_a_table_cell_against_the_base():
    html = md.render(TABLE_WITH_LOCAL, base=BASE)
    assert f'src="{BASE}assets/' + "a" * 64 + '.png"' in html


def test_should_render_a_remote_picture_inside_a_table_cell():
    html = md.render(TABLE_WITH_REMOTE, base=BASE)
    assert 'src="https://example.com/a.png"' in IMG_IN_CELL.search(html).group(0)
