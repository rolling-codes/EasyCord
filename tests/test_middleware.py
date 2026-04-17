import pytest
import logging
from unittest.mock import AsyncMock, MagicMock

from easycord.context import Context
from easycord.middleware import (
    log_middleware,
    guild_only,
    rate_limit,
    catch_errors,
)


@pytest.fixture
def interaction():
    m = MagicMock()
    m.response.send_message = AsyncMock()
    m.followup.send = AsyncMock()
    m.command.name = "test"
    m.user.id = 1
    return m


@pytest.fixture
def ctx(interaction):
    return Context(interaction)


# --- log_middleware ---

async def test_log_middleware_calls_next(ctx):
    next_fn = AsyncMock()
    mw = log_middleware()
    await mw(ctx, next_fn)
    next_fn.assert_called_once()


async def test_log_middleware_logs(ctx, caplog):
    with caplog.at_level(logging.INFO, logger="easycord"):
        mw = log_middleware()
        await mw(ctx, AsyncMock())
    assert "test" in caplog.text


async def test_log_middleware_custom_level(ctx, caplog):
    with caplog.at_level(logging.DEBUG, logger="easycord"):
        mw = log_middleware(level=logging.DEBUG)
        await mw(ctx, AsyncMock())
    assert caplog.records[0].levelno == logging.DEBUG


# --- guild_only ---

async def test_guild_only_allows_guild_command(ctx, interaction):
    interaction.guild = MagicMock()
    next_fn = AsyncMock()
    mw = guild_only()
    await mw(ctx, next_fn)
    next_fn.assert_called_once()


async def test_guild_only_blocks_dm(ctx, interaction):
    interaction.guild = None
    next_fn = AsyncMock()
    mw = guild_only()
    await mw(ctx, next_fn)
    next_fn.assert_not_called()
    interaction.response.send_message.assert_called_once()
    args = interaction.response.send_message.call_args
    assert args.kwargs.get("ephemeral") is True


# --- rate_limit ---

async def test_rate_limit_allows_within_limit(interaction):
    mw = rate_limit(limit=3, window=10.0)
    next_fn = AsyncMock()
    for _ in range(3):
        c = Context(interaction)
        await mw(c, next_fn)
    assert next_fn.call_count == 3


async def test_rate_limit_blocks_when_exceeded(interaction):
    mw = rate_limit(limit=2, window=10.0)
    next_fn = AsyncMock()
    for _ in range(2):
        await mw(Context(interaction), next_fn)

    blocked = Context(interaction)
    await mw(blocked, next_fn)

    assert next_fn.call_count == 2
    interaction.response.send_message.assert_called_once()
    msg = interaction.response.send_message.call_args[0][0]
    assert "rate limit" in msg.lower()


async def test_rate_limit_independent_per_user(interaction):
    mw = rate_limit(limit=1, window=10.0)

    user_a = MagicMock()
    user_a.id = 10
    user_b = MagicMock()
    user_b.id = 20

    next_fn = AsyncMock()
    interaction.user = user_a
    await mw(Context(interaction), next_fn)

    interaction.user = user_b
    await mw(Context(interaction), next_fn)

    assert next_fn.call_count == 2


# --- catch_errors ---

async def test_catch_errors_passes_through_on_success(ctx):
    next_fn = AsyncMock()
    mw = catch_errors()
    await mw(ctx, next_fn)
    next_fn.assert_called_once()


async def test_catch_errors_catches_exception(ctx, interaction):
    async def boom():
        raise ValueError("kaboom")

    mw = catch_errors()
    await mw(ctx, boom)
    interaction.response.send_message.assert_called_once()
    msg = interaction.response.send_message.call_args[0][0]
    assert "wrong" in msg.lower() or "error" in msg.lower()


async def test_catch_errors_logs_exception(ctx, caplog):
    async def boom():
        raise RuntimeError("oops")

    with caplog.at_level(logging.ERROR, logger="easycord"):
        mw = catch_errors()
        await mw(ctx, boom)
    assert "oops" in caplog.text


async def test_catch_errors_custom_message(ctx, interaction):
    async def boom():
        raise ValueError("x")

    mw = catch_errors(message="Custom error.")
    await mw(ctx, boom)
    msg = interaction.response.send_message.call_args[0][0]
    assert msg == "Custom error."


async def test_catch_errors_survives_failed_response(ctx, interaction):
    async def boom():
        raise ValueError("x")

    interaction.response.send_message.side_effect = RuntimeError("send failed")
    mw = catch_errors()
    await mw(ctx, boom)


# ── dm_only / allowed_roles / admin_only / channel_only ──────────────────────

from easycord.middleware import admin_only, allowed_roles, channel_only, dm_only


def _mw_make_ctx(*, guild=True, role_ids=None):
    ctx = MagicMock()
    ctx.respond = AsyncMock()
    ctx.user = MagicMock()
    ctx.user.id = 1
    if guild:
        ctx.guild = MagicMock()
        member = MagicMock()
        member.roles = [type("R", (), {"id": rid})() for rid in (role_ids or [])]
        ctx.guild.get_member = MagicMock(return_value=member)
    else:
        ctx.guild = None
    return ctx


async def test_dm_only_passes_in_dm():
    ctx = _mw_make_ctx(guild=False)
    proceed = AsyncMock()
    await dm_only()(ctx, proceed)
    proceed.assert_called_once()


async def test_dm_only_blocks_in_guild():
    ctx = _mw_make_ctx(guild=True)
    proceed = AsyncMock()
    await dm_only()(ctx, proceed)
    proceed.assert_not_called()
    assert ctx.respond.call_args.kwargs.get("ephemeral") is True


async def test_allowed_roles_passes_when_member_has_role():
    ctx = _mw_make_ctx(guild=True, role_ids=[100, 200])
    proceed = AsyncMock()
    await allowed_roles(200)(ctx, proceed)
    proceed.assert_called_once()


async def test_allowed_roles_blocks_when_member_lacks_role():
    ctx = _mw_make_ctx(guild=True, role_ids=[100])
    proceed = AsyncMock()
    await allowed_roles(999)(ctx, proceed)
    proceed.assert_not_called()
    assert ctx.respond.call_args.kwargs.get("ephemeral") is True


async def test_allowed_roles_passes_with_any_matching_role():
    ctx = _mw_make_ctx(guild=True, role_ids=[50, 99])
    proceed = AsyncMock()
    await allowed_roles(1, 2, 99)(ctx, proceed)
    proceed.assert_called_once()


async def test_allowed_roles_passes_in_dm():
    ctx = _mw_make_ctx(guild=False)
    proceed = AsyncMock()
    await allowed_roles(999)(ctx, proceed)
    proceed.assert_called_once()


async def test_allowed_roles_blocks_when_member_not_in_cache():
    ctx = _mw_make_ctx(guild=True)
    ctx.guild.get_member = MagicMock(return_value=None)
    proceed = AsyncMock()
    await allowed_roles(100)(ctx, proceed)
    proceed.assert_not_called()


async def test_allowed_roles_custom_message():
    ctx = _mw_make_ctx(guild=True, role_ids=[])
    proceed = AsyncMock()
    await allowed_roles(999, message="Staff only!")(ctx, proceed)
    assert "Staff only!" in ctx.respond.call_args[0][0]


def _mw_make_ctx_admin(*, guild=True, is_admin=False):
    ctx = _mw_make_ctx(guild=guild)
    if guild:
        member = MagicMock()
        member.guild_permissions = MagicMock()
        member.guild_permissions.administrator = is_admin
        ctx.guild.get_member = MagicMock(return_value=member)
    return ctx


async def test_admin_only_passes_for_admin():
    ctx = _mw_make_ctx_admin(guild=True, is_admin=True)
    proceed = AsyncMock()
    await admin_only()(ctx, proceed)
    proceed.assert_called_once()


async def test_admin_only_blocks_non_admin():
    ctx = _mw_make_ctx_admin(guild=True, is_admin=False)
    proceed = AsyncMock()
    await admin_only()(ctx, proceed)
    proceed.assert_not_called()
    assert ctx.respond.call_args.kwargs.get("ephemeral") is True


async def test_admin_only_blocks_when_member_not_cached():
    ctx = _mw_make_ctx(guild=True)
    ctx.guild.get_member = MagicMock(return_value=None)
    proceed = AsyncMock()
    await admin_only()(ctx, proceed)
    proceed.assert_not_called()


async def test_admin_only_passes_in_dm():
    ctx = _mw_make_ctx_admin(guild=False)
    proceed = AsyncMock()
    await admin_only()(ctx, proceed)
    proceed.assert_called_once()


async def test_admin_only_custom_message():
    ctx = _mw_make_ctx_admin(guild=True, is_admin=False)
    proceed = AsyncMock()
    await admin_only(message="Admins only!")(ctx, proceed)
    assert "Admins only!" in ctx.respond.call_args[0][0]


def _mw_make_ctx_channel(channel_id, *, guild=True):
    ctx = _mw_make_ctx(guild=guild)
    if channel_id is not None:
        ctx.channel = MagicMock()
        ctx.channel.id = channel_id
    else:
        ctx.channel = None
    return ctx


async def test_channel_only_passes_in_allowed_channel():
    ctx = _mw_make_ctx_channel(42)
    proceed = AsyncMock()
    await channel_only(42)(ctx, proceed)
    proceed.assert_called_once()


async def test_channel_only_blocks_other_channel():
    ctx = _mw_make_ctx_channel(99)
    proceed = AsyncMock()
    await channel_only(42)(ctx, proceed)
    proceed.assert_not_called()
    assert ctx.respond.call_args.kwargs.get("ephemeral") is True


async def test_channel_only_passes_any_of_multiple():
    ctx = _mw_make_ctx_channel(5)
    proceed = AsyncMock()
    await channel_only(1, 2, 5)(ctx, proceed)
    proceed.assert_called_once()


async def test_channel_only_passes_in_dm():
    ctx = _mw_make_ctx_channel(99, guild=False)
    proceed = AsyncMock()
    await channel_only(42)(ctx, proceed)
    proceed.assert_called_once()


async def test_channel_only_blocks_when_channel_is_none():
    ctx = _mw_make_ctx_channel(None)
    proceed = AsyncMock()
    await channel_only(42)(ctx, proceed)
    proceed.assert_not_called()


async def test_channel_only_custom_message():
    ctx = _mw_make_ctx_channel(99)
    proceed = AsyncMock()
    await channel_only(42, message="Wrong channel!")(ctx, proceed)
    assert "Wrong channel!" in ctx.respond.call_args[0][0]


# ── boost_only / has_permission ───────────────────────────────────────────────

from easycord.middleware import boost_only, has_permission
import datetime


def _mw_make_ctx_boost(*, guild=True, is_booster=True):
    ctx = MagicMock()
    ctx.respond = AsyncMock()
    ctx.guild = MagicMock() if guild else None
    if guild:
        member = MagicMock()
        member.premium_since = datetime.datetime.now() if is_booster else None
        ctx.guild.get_member = MagicMock(return_value=member)
        ctx.user = MagicMock()
        ctx.user.id = 1
    return ctx


async def test_boost_only_passes_for_booster():
    ctx = _mw_make_ctx_boost(is_booster=True)
    proceed = AsyncMock()
    await boost_only()(ctx, proceed)
    proceed.assert_called_once()


async def test_boost_only_blocks_non_booster():
    ctx = _mw_make_ctx_boost(is_booster=False)
    proceed = AsyncMock()
    await boost_only()(ctx, proceed)
    proceed.assert_not_called()
    assert ctx.respond.call_args.kwargs.get("ephemeral") is True


async def test_boost_only_blocks_when_member_not_cached():
    ctx = _mw_make_ctx_boost(guild=True)
    ctx.guild.get_member = MagicMock(return_value=None)
    proceed = AsyncMock()
    await boost_only()(ctx, proceed)
    proceed.assert_not_called()


async def test_boost_only_passes_in_dm():
    ctx = _mw_make_ctx_boost(guild=False)
    proceed = AsyncMock()
    await boost_only()(ctx, proceed)
    proceed.assert_called_once()


async def test_boost_only_custom_message():
    ctx = _mw_make_ctx_boost(is_booster=False)
    proceed = AsyncMock()
    await boost_only(message="Boosters only!")(ctx, proceed)
    assert "Boosters only!" in ctx.respond.call_args[0][0]


def _mw_make_ctx_perms(*, guild=True, perms=None):
    ctx = MagicMock()
    ctx.respond = AsyncMock()
    ctx.guild = MagicMock() if guild else None
    if guild:
        member = MagicMock()
        gp = MagicMock()
        for perm in (perms or []):
            setattr(gp, perm, True)
        member.guild_permissions = gp
        ctx.guild.get_member = MagicMock(return_value=member)
        ctx.user = MagicMock()
        ctx.user.id = 1
    return ctx


async def test_has_permission_passes_when_member_has_all():
    ctx = _mw_make_ctx_perms(perms=["kick_members", "ban_members"])
    proceed = AsyncMock()
    await has_permission("kick_members", "ban_members")(ctx, proceed)
    proceed.assert_called_once()


async def test_has_permission_blocks_when_missing_one():
    ctx = _mw_make_ctx_perms(perms=["kick_members"])
    ctx.guild.get_member.return_value.guild_permissions.ban_members = False
    proceed = AsyncMock()
    await has_permission("kick_members", "ban_members")(ctx, proceed)
    proceed.assert_not_called()
    assert ctx.respond.call_args.kwargs.get("ephemeral") is True
    assert "ban_members" in ctx.respond.call_args[0][0]


async def test_has_permission_blocks_when_member_not_cached():
    ctx = _mw_make_ctx_perms(guild=True)
    ctx.guild.get_member = MagicMock(return_value=None)
    proceed = AsyncMock()
    await has_permission("kick_members")(ctx, proceed)
    proceed.assert_not_called()


async def test_has_permission_passes_in_dm():
    ctx = _mw_make_ctx_perms(guild=False)
    proceed = AsyncMock()
    await has_permission("kick_members")(ctx, proceed)
    proceed.assert_called_once()
