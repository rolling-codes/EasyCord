"""Tests for UIMixin.send_buttons."""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock
import discord

from easycord._context_ui import UIMixin


class _FakeCtx(UIMixin):
    """Minimal stand-in for Context that satisfies UIMixin dependencies."""

    def __init__(self):
        self.interaction = MagicMock()
        self._responded = False
        self._last_view = None
        self._last_kwargs = {}

    async def respond(self, *args, **kwargs):
        self._responded = True
        self._last_kwargs = kwargs
        self._last_view = kwargs.get("view")


# ── send_buttons ──────────────────────────────────────────────────────────────

async def test_send_buttons_returns_clicked_value():
    ctx = _FakeCtx()

    async def _click_first():
        await asyncio.sleep(0)
        btn = ctx._last_view.children[0]
        interaction = MagicMock()
        interaction.response.edit_message = AsyncMock()
        await btn.callback(interaction)

    task = asyncio.create_task(_click_first())
    result = await ctx.send_buttons("Pick one", ["Alpha", "Beta"])
    await task
    assert result == "Alpha"


async def test_send_buttons_returns_dict_value():
    ctx = _FakeCtx()

    async def _click():
        await asyncio.sleep(0)
        btn = ctx._last_view.children[1]
        interaction = MagicMock()
        interaction.response.edit_message = AsyncMock()
        await btn.callback(interaction)

    task = asyncio.create_task(_click())
    result = await ctx.send_buttons(
        "Pick one",
        [
            {"label": "Approve", "value": "approve", "style": "green"},
            {"label": "Deny", "value": "deny", "style": "red"},
        ],
    )
    await task
    assert result == "deny"


async def test_send_buttons_returns_none_on_timeout():
    ctx = _FakeCtx()

    async def _trigger_timeout():
        await asyncio.sleep(0)
        await ctx._last_view.on_timeout()

    task = asyncio.create_task(_trigger_timeout())
    result = await ctx.send_buttons("Pick one", ["A"], timeout=60)
    await task
    assert result is None


async def test_send_buttons_string_label_equals_value():
    ctx = _FakeCtx()

    async def _click():
        await asyncio.sleep(0)
        btn = ctx._last_view.children[0]
        interaction = MagicMock()
        interaction.response.edit_message = AsyncMock()
        await btn.callback(interaction)

    task = asyncio.create_task(_click())
    result = await ctx.send_buttons("Go", ["MyOption"])
    await task
    assert result == "MyOption"
    assert ctx._last_view.children[0].label == "MyOption"


async def test_send_buttons_passes_ephemeral():
    ctx = _FakeCtx()

    async def _click():
        await asyncio.sleep(0)
        btn = ctx._last_view.children[0]
        interaction = MagicMock()
        interaction.response.edit_message = AsyncMock()
        await btn.callback(interaction)

    task = asyncio.create_task(_click())
    await ctx.send_buttons("Go", ["X"], ephemeral=True)
    await task
    assert ctx._last_kwargs.get("ephemeral") is True


async def test_send_buttons_dict_label_fallback_as_value():
    """When a dict has no 'value' key, label is used as the return value."""
    ctx = _FakeCtx()

    async def _click():
        await asyncio.sleep(0)
        btn = ctx._last_view.children[0]
        interaction = MagicMock()
        interaction.response.edit_message = AsyncMock()
        await btn.callback(interaction)

    task = asyncio.create_task(_click())
    result = await ctx.send_buttons("Go", [{"label": "Confirm"}])
    await task
    assert result == "Confirm"
