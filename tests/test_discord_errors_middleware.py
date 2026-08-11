"""Tests for the discord_errors() middleware."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from easycord.middleware import discord_errors


def _ctx(command_name: str = "cmd") -> MagicMock:
    ctx = MagicMock()
    ctx.command_name = command_name
    ctx.respond = AsyncMock()
    ctx.t = lambda key, default="", **kw: default.format(**kw) if kw else default
    return ctx


async def test_forbidden_gets_permission_message() -> None:
    ctx = _ctx()

    async def proceed() -> None:
        raise discord.Forbidden(MagicMock(), "no perms")

    await discord_errors()(ctx, proceed)

    ctx.respond.assert_awaited_once()
    args, kwargs = ctx.respond.call_args
    assert "permission" in args[0].lower()
    assert kwargs.get("ephemeral") is True


async def test_not_found_gets_specific_message() -> None:
    ctx = _ctx()

    async def proceed() -> None:
        raise discord.NotFound(MagicMock(status=404), "gone")

    await discord_errors()(ctx, proceed)
    assert "no longer exists" in ctx.respond.call_args[0][0].lower()


async def test_http_exception_gets_http_message() -> None:
    ctx = _ctx()

    async def proceed() -> None:
        raise discord.HTTPException(MagicMock(), "boom")

    await discord_errors()(ctx, proceed)
    assert "discord returned an error" in ctx.respond.call_args[0][0].lower()


async def test_custom_message_overrides_default() -> None:
    ctx = _ctx()

    async def proceed() -> None:
        raise discord.Forbidden(MagicMock(), "x")

    await discord_errors(forbidden="Nope!")(ctx, proceed)
    assert ctx.respond.call_args[0][0] == "Nope!"


async def test_non_discord_error_propagates_to_fallback() -> None:
    # discord_errors must not swallow non-Discord errors, so catch_errors (or
    # another outer handler) remains the fallback.
    ctx = _ctx()

    async def proceed() -> None:
        raise ValueError("boom")

    with pytest.raises(ValueError):
        await discord_errors()(ctx, proceed)
    ctx.respond.assert_not_awaited()


async def test_success_path_does_not_respond() -> None:
    ctx = _ctx()
    ran = []

    async def proceed() -> None:
        ran.append(True)

    await discord_errors()(ctx, proceed)
    assert ran == [True]
    ctx.respond.assert_not_awaited()
