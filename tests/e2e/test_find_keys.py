"""Find is keyboard-driven: Enter steps through the matches, Shift+Enter steps back."""

from __future__ import annotations

import re

import pytest
from playwright.sync_api import expect

pytestmark = pytest.mark.e2e


def test_should_step_through_matches_with_enter_and_shift_enter(canvas):
    canvas.fill("[data-find]", "the")
    count = canvas.locator("[data-find-count]")
    expect(count).to_have_text(re.compile(r"^1/\d+$"))
    total = count.text_content().split("/")[1]
    assert int(total) > 1, "the fixture needs at least two matches to step between"

    canvas.press("[data-find]", "Enter")
    expect(count).to_have_text(f"2/{total}")

    canvas.press("[data-find]", "Shift+Enter")
    expect(count).to_have_text(f"1/{total}")
