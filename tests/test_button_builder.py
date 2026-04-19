"""Tests for easycord.builders.button — ButtonRowBuilder."""
import discord

from easycord.builders.button import ButtonRowBuilder


def test_build_returns_view():
    view = ButtonRowBuilder().button("Click", custom_id="click").build()
    assert isinstance(view, discord.ui.View)


def test_button_added_to_view():
    view = ButtonRowBuilder().button("Click", custom_id="click").build()
    assert len(view.children) == 1


def test_button_label():
    view = ButtonRowBuilder().button("Go", custom_id="go").build()
    assert view.children[0].label == "Go"


def test_button_custom_id():
    view = ButtonRowBuilder().button("Go", custom_id="go").build()
    assert view.children[0].custom_id == "go"


def test_button_default_style_is_primary():
    view = ButtonRowBuilder().button("X", custom_id="x").build()
    assert view.children[0].style == discord.ButtonStyle.primary


def test_button_style_success():
    view = ButtonRowBuilder().button("OK", custom_id="ok", style="success").build()
    assert view.children[0].style == discord.ButtonStyle.success


def test_button_style_danger():
    view = ButtonRowBuilder().button("No", custom_id="no", style="danger").build()
    assert view.children[0].style == discord.ButtonStyle.danger


def test_button_style_secondary():
    view = ButtonRowBuilder().button("Meh", custom_id="meh", style="secondary").build()
    assert view.children[0].style == discord.ButtonStyle.secondary


def test_button_link_style_uses_url():
    view = ButtonRowBuilder().button("Visit", style="link", url="https://example.com").build()
    btn = view.children[0]
    assert btn.style == discord.ButtonStyle.link
    assert btn.url == "https://example.com"


def test_multiple_buttons():
    view = ButtonRowBuilder().button("A", custom_id="a").button("B", custom_id="b").build()
    assert len(view.children) == 2
    assert view.children[0].label == "A"
    assert view.children[1].label == "B"


def test_chaining_returns_self():
    b = ButtonRowBuilder()
    assert b.button("X", custom_id="x") is b
