"""Tests for the v2.2+ middleware additions: dm_only, allowed_roles, admin_only."""
import pytest
from unittest.mock import AsyncMock, MagicMock

from easycord.middleware import admin_only, allowed_roles, channel_only, dm_only


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_ctx(*, guild=True, role_ids: list[int] | None = None):
    ctx = MagicMock()
    ctx.respond = AsyncMock()
    ctx.user = MagicMock()
    ctx.user.id = 1

    if guild:
        ctx.guild = MagicMock()
        member = MagicMock()
        roles = []
        for rid in (role_ids or []):
            r = MagicMock()
            r.id = rid
            roles.append(r)
        member.roles = roles
        ctx.guild.get_member = MagicMock(return_value=member)
    else:
        ctx.guild = None

    return ctx


# ── dm_only ───────────────────────────────────────────────────────────────────

async def test_dm_only_passes_in_dm():
    ctx = _make_ctx(guild=False)
    proceed = AsyncMock()
    await dm_only()(ctx, proceed)
    proceed.assert_called_once()


async def test_dm_only_blocks_in_guild():
    ctx = _make_ctx(guild=True)
    proceed = AsyncMock()
    await dm_only()(ctx, proceed)
    proceed.assert_not_called()
    ctx.respond.assert_called_once()
    assert ctx.respond.call_args.kwargs.get("ephemeral") is True


# ── allowed_roles ─────────────────────────────────────────────────────────────

async def test_allowed_roles_passes_when_member_has_role():
    ctx = _make_ctx(guild=True, role_ids=[100, 200])
    proceed = AsyncMock()
    await allowed_roles(200)(ctx, proceed)
    proceed.assert_called_once()


async def test_allowed_roles_blocks_when_member_lacks_role():
    ctx = _make_ctx(guild=True, role_ids=[100])
    proceed = AsyncMock()
    await allowed_roles(999)(ctx, proceed)
    proceed.assert_not_called()
    ctx.respond.assert_called_once()
    assert ctx.respond.call_args.kwargs.get("ephemeral") is True


async def test_allowed_roles_passes_with_any_matching_role():
    ctx = _make_ctx(guild=True, role_ids=[50, 99])
    proceed = AsyncMock()
    await allowed_roles(1, 2, 99)(ctx, proceed)
    proceed.assert_called_once()


async def test_allowed_roles_passes_in_dm():
    """DMs bypass the role check — combine with guild_only() if needed."""
    ctx = _make_ctx(guild=False)
    proceed = AsyncMock()
    await allowed_roles(999)(ctx, proceed)
    proceed.assert_called_once()


async def test_allowed_roles_blocks_when_member_not_in_cache():
    ctx = _make_ctx(guild=True, role_ids=[])
    ctx.guild.get_member = MagicMock(return_value=None)
    proceed = AsyncMock()
    await allowed_roles(100)(ctx, proceed)
    proceed.assert_not_called()


async def test_allowed_roles_custom_message():
    ctx = _make_ctx(guild=True, role_ids=[])
    proceed = AsyncMock()
    await allowed_roles(999, message="Staff only!")(ctx, proceed)
    assert "Staff only!" in ctx.respond.call_args[0][0]


# ── admin_only ────────────────────────────────────────────────────────────────

def _make_ctx_admin(*, guild=True, is_admin=False):
    ctx = _make_ctx(guild=guild)
    if guild:
        member = MagicMock()
        member.guild_permissions = MagicMock()
        member.guild_permissions.administrator = is_admin
        ctx.guild.get_member = MagicMock(return_value=member)
    return ctx


async def test_admin_only_passes_for_admin():
    ctx = _make_ctx_admin(guild=True, is_admin=True)
    proceed = AsyncMock()
    await admin_only()(ctx, proceed)
    proceed.assert_called_once()


async def test_admin_only_blocks_non_admin():
    ctx = _make_ctx_admin(guild=True, is_admin=False)
    proceed = AsyncMock()
    await admin_only()(ctx, proceed)
    proceed.assert_not_called()
    ctx.respond.assert_called_once()
    assert ctx.respond.call_args.kwargs.get("ephemeral") is True


async def test_admin_only_blocks_when_member_not_cached():
    ctx = _make_ctx(guild=True)
    ctx.guild.get_member = MagicMock(return_value=None)
    proceed = AsyncMock()
    await admin_only()(ctx, proceed)
    proceed.assert_not_called()


async def test_admin_only_passes_in_dm():
    """DMs bypass the admin check — combine with guild_only() if needed."""
    ctx = _make_ctx_admin(guild=False)
    proceed = AsyncMock()
    await admin_only()(ctx, proceed)
    proceed.assert_called_once()


async def test_admin_only_custom_message():
    ctx = _make_ctx_admin(guild=True, is_admin=False)
    proceed = AsyncMock()
    await admin_only(message="Admins only!")(ctx, proceed)
    assert "Admins only!" in ctx.respond.call_args[0][0]


# ── channel_only ──────────────────────────────────────────────────────────────

def _make_ctx_channel(channel_id: int | None, *, guild=True):
    ctx = _make_ctx(guild=guild)
    if channel_id is not None:
        ctx.channel = MagicMock()
        ctx.channel.id = channel_id
    else:
        ctx.channel = None
    return ctx


async def test_channel_only_passes_in_allowed_channel():
    ctx = _make_ctx_channel(42)
    proceed = AsyncMock()
    await channel_only(42)(ctx, proceed)
    proceed.assert_called_once()


async def test_channel_only_blocks_other_channel():
    ctx = _make_ctx_channel(99)
    proceed = AsyncMock()
    await channel_only(42)(ctx, proceed)
    proceed.assert_not_called()
    assert ctx.respond.call_args.kwargs.get("ephemeral") is True


async def test_channel_only_passes_any_of_multiple():
    ctx = _make_ctx_channel(5)
    proceed = AsyncMock()
    await channel_only(1, 2, 5)(ctx, proceed)
    proceed.assert_called_once()


async def test_channel_only_passes_in_dm():
    ctx = _make_ctx_channel(99, guild=False)
    proceed = AsyncMock()
    await channel_only(42)(ctx, proceed)
    proceed.assert_called_once()


async def test_channel_only_blocks_when_channel_is_none():
    ctx = _make_ctx_channel(None)
    proceed = AsyncMock()
    await channel_only(42)(ctx, proceed)
    proceed.assert_not_called()


async def test_channel_only_custom_message():
    ctx = _make_ctx_channel(99)
    proceed = AsyncMock()
    await channel_only(42, message="Wrong channel!")(ctx, proceed)
    assert "Wrong channel!" in ctx.respond.call_args[0][0]
