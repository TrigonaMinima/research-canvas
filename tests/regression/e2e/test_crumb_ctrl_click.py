"""A modified click on the home crumb opens the canvas list in a new tab."""

# Guards 1a76b08 (fix: open the canvas list in a new tab on a modified crumb click).

from __future__ import annotations

import pytest
from playwright.sync_api import expect

pytestmark = pytest.mark.e2e


def test_should_link_the_crumb_to_the_canvas_list(canvas):
    expect(canvas.locator("[data-crumb-home]")).to_have_attribute("href", "./")


def test_should_open_the_list_in_a_new_tab_on_ctrl_click(canvas):
    with canvas.context.expect_page() as opened:
        canvas.click("[data-crumb-home]", modifiers=["ControlOrMeta"])
    expect(opened.value.locator("[data-empty]")).to_be_visible()


def test_should_keep_the_canvas_open_on_ctrl_click(canvas):
    with canvas.context.expect_page():
        canvas.click("[data-crumb-home]", modifiers=["ControlOrMeta"])
    expect(canvas.locator("[data-empty]")).to_be_hidden()
