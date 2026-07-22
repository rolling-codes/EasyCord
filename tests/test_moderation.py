"""Tests for ModerationPlugin — covers all commands and guard paths.

Tests run fully offline (no Discord connection). All Discord I/O is
mocked via MagicMock / AsyncMock.
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import discord

from easycord.plugin import Plugin
from easycord.plugins._config_manager import PluginConfigManager
from easycord.plugins.moderation import ModerationPlugin
from easycord import RateLimit, ToolLimiter
from plugin_test_helpers import make_target_user, make_target_member

pytestmark = pytest.mark.asyncio

GUILD_ID = 100
MOD_USER_ID = 1
TARGET_USER_ID = 2


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_plugin(tmp_path) -> ModerationPlugin:
    """Construct a ModerationPlugin with an in-memory config store."""
    p: ModerationPlugin = ModerationPlugin.__new__(ModerationPlugin)
    Plugin.__init__(p)
    p.config = PluginConfigManager(str(tmp_path / "moderation"))
    p.warn_limiter = ToolLimiter()
    p.ban_limiter = ToolLimiter()
    return p


def _make_ctx(
    *,
    guild_id: int | None = GUILD_ID,
    user_id: int = MOD_USER_ID,
    **permissions: bool,
) -> MagicMock:
    """Build a ctx with per-flag guild_permissions (moderation needs independent flags)."""
    ctx = MagicMock()
    ctx.respond = AsyncMock()

    perms = MagicMock(spec=discord.Permissions)
    for attr in ("kick_members", "ban_members", "manage_roles", "moderate_members", "administrator"):
        setattr(perms, attr, permissions.get(attr, False))

    member = MagicMock(spec=discord.Member)
    member.id = user_id
    member.mention = f"<@{user_id}>"
    member.guild_permissions = perms
    ctx.member = member
    ctx.user = member

    if guild_id is not None:
        guild = MagicMock(spec=discord.Guild)
        guild.id = guild_id
        guild.roles = []
        guild.get_channel = MagicMock(return_value=None)
        guild.get_member = MagicMock(return_value=None)
        ctx.guild = guild
    else:
        ctx.guild = None

    return ctx


def _make_target(user_id: int = TARGET_USER_ID) -> MagicMock:
    return make_target_user(user_id)


def _make_member_target(user_id: int = TARGET_USER_ID) -> MagicMock:
    return make_target_member(user_id)


# ---------------------------------------------------------------------------
# /kick
# ---------------------------------------------------------------------------

class TestKick:
    async def test_kick_success(self, tmp_path) -> None:
        plugin = _make_plugin(tmp_path)
        ctx = _make_ctx(kick_members=True)
        target_user = _make_target()
        target_member = _make_member_target()
        ctx.guild.get_member = MagicMock(return_value=target_member)

        await plugin.kick(ctx, user=target_user, reason="spam")

        target_member.kick.assert_awaited_once()
        ctx.respond.assert_awaited_once()
        assert "✅" in ctx.respond.call_args.args[0]

    async def test_kick_no_permission(self, tmp_path) -> None:
        plugin = _make_plugin(tmp_path)
        ctx = _make_ctx(kick_members=False)
        target_user = _make_target()

        await plugin.kick(ctx, user=target_user)

        ctx.respond.assert_awaited_once()
        assert "kick_members" in ctx.respond.call_args.args[0]

    async def test_kick_user_not_in_guild(self, tmp_path) -> None:
        plugin = _make_plugin(tmp_path)
        ctx = _make_ctx(kick_members=True)
        ctx.guild.get_member = MagicMock(return_value=None)
        target_user = _make_target()

        await plugin.kick(ctx, user=target_user)

        ctx.respond.assert_awaited_once()
        assert "not in this server" in ctx.respond.call_args.args[0]

    async def test_kick_forbidden_is_caught(self, tmp_path) -> None:
        plugin = _make_plugin(tmp_path)
        ctx = _make_ctx(kick_members=True)
        target_user = _make_target()
        target_member = _make_member_target()
        target_member.kick = AsyncMock(side_effect=discord.Forbidden(MagicMock(), "no perms"))
        ctx.guild.get_member = MagicMock(return_value=target_member)

        await plugin.kick(ctx, user=target_user)  # must not raise

        ctx.respond.assert_awaited_once()
        assert "lack permission" in ctx.respond.call_args.args[0]

    async def test_kick_http_exception_is_caught(self, tmp_path) -> None:
        plugin = _make_plugin(tmp_path)
        ctx = _make_ctx(kick_members=True)
        target_user = _make_target()
        target_member = _make_member_target()
        target_member.kick = AsyncMock(
            side_effect=discord.HTTPException(MagicMock(), "server error")
        )
        ctx.guild.get_member = MagicMock(return_value=target_member)

        await plugin.kick(ctx, user=target_user)

        ctx.respond.assert_awaited_once()
        assert "Failed to kick" in ctx.respond.call_args.args[0]

    async def test_kick_in_dm_context_rejected(self, tmp_path) -> None:
        plugin = _make_plugin(tmp_path)
        ctx = _make_ctx(guild_id=None, kick_members=True)
        ctx.member = None

        await plugin.kick(ctx, user=_make_target())

        ctx.respond.assert_awaited_once()
        assert "only be used inside a server" in ctx.respond.call_args.args[0]


# ---------------------------------------------------------------------------
# /ban
# ---------------------------------------------------------------------------

class TestBan:
    async def test_ban_success(self, tmp_path) -> None:
        plugin = _make_plugin(tmp_path)
        ctx = _make_ctx(ban_members=True)
        target_user = _make_target()
        ctx.guild.ban = AsyncMock()

        await plugin.ban(ctx, user=target_user, reason="toxic")

        ctx.guild.ban.assert_awaited_once()
        assert "✅" in ctx.respond.call_args.args[0]

    async def test_ban_no_permission(self, tmp_path) -> None:
        plugin = _make_plugin(tmp_path)
        ctx = _make_ctx(ban_members=False)
        target_user = _make_target()

        await plugin.ban(ctx, user=target_user)

        assert "ban_members" in ctx.respond.call_args.args[0]

    async def test_ban_forbidden_is_caught(self, tmp_path) -> None:
        plugin = _make_plugin(tmp_path)
        ctx = _make_ctx(ban_members=True)
        target_user = _make_target()
        ctx.guild.ban = AsyncMock(side_effect=discord.Forbidden(MagicMock(), "no perms"))

        await plugin.ban(ctx, user=target_user)

        assert "lack permission" in ctx.respond.call_args.args[0]

    async def test_ban_http_exception_is_caught(self, tmp_path) -> None:
        plugin = _make_plugin(tmp_path)
        ctx = _make_ctx(ban_members=True)
        target_user = _make_target()
        ctx.guild.ban = AsyncMock(
            side_effect=discord.HTTPException(MagicMock(), "server error")
        )

        await plugin.ban(ctx, user=target_user)

        assert "Failed to ban" in ctx.respond.call_args.args[0]

    async def test_ban_rate_limited(self, tmp_path) -> None:
        plugin = _make_plugin(tmp_path)
        ctx = _make_ctx(ban_members=True)
        ctx.guild.ban = AsyncMock()
        target_user = _make_target()

        # Exhaust the ban budget (5 per hour)
        limit = RateLimit(max_calls=5, window_minutes=60)
        for _ in range(5):
            await plugin.ban_limiter.check_limit(MOD_USER_ID, "ban", limit)

        await plugin.ban(ctx, user=target_user)

        # The rate-limit response is the only call; ban should NOT have been called
        ctx.guild.ban.assert_not_awaited()
        assert "⏳" in ctx.respond.call_args.args[0]

    async def test_ban_in_dm_context_rejected(self, tmp_path) -> None:
        plugin = _make_plugin(tmp_path)
        ctx = _make_ctx(guild_id=None, ban_members=True)
        ctx.member = None

        await plugin.ban(ctx, user=_make_target())

        assert "only be used inside a server" in ctx.respond.call_args.args[0]


# ---------------------------------------------------------------------------
# /unban
# ---------------------------------------------------------------------------

class TestUnban:
    async def test_unban_success(self, tmp_path) -> None:
        plugin = _make_plugin(tmp_path)
        ctx = _make_ctx(ban_members=True)
        target_user = _make_target()
        ctx.guild.unban = AsyncMock()

        await plugin.unban(ctx, user=target_user)

        ctx.guild.unban.assert_awaited_once()
        assert "✅" in ctx.respond.call_args.args[0]

    async def test_unban_no_permission(self, tmp_path) -> None:
        plugin = _make_plugin(tmp_path)
        ctx = _make_ctx(ban_members=False)

        await plugin.unban(ctx, user=_make_target())

        assert "ban_members" in ctx.respond.call_args.args[0]

    async def test_unban_not_found_is_caught(self, tmp_path) -> None:
        plugin = _make_plugin(tmp_path)
        ctx = _make_ctx(ban_members=True)
        ctx.guild.unban = AsyncMock(
            side_effect=discord.NotFound(MagicMock(), "not banned")
        )

        await plugin.unban(ctx, user=_make_target())

        assert "not banned" in ctx.respond.call_args.args[0]

    async def test_unban_forbidden_is_caught(self, tmp_path) -> None:
        plugin = _make_plugin(tmp_path)
        ctx = _make_ctx(ban_members=True)
        ctx.guild.unban = AsyncMock(side_effect=discord.Forbidden(MagicMock(), "no perms"))

        await plugin.unban(ctx, user=_make_target())

        assert "lack permission" in ctx.respond.call_args.args[0]

    async def test_unban_http_exception_is_caught(self, tmp_path) -> None:
        plugin = _make_plugin(tmp_path)
        ctx = _make_ctx(ban_members=True)
        ctx.guild.unban = AsyncMock(
            side_effect=discord.HTTPException(MagicMock(), "error")
        )

        await plugin.unban(ctx, user=_make_target())

        assert "Failed to unban" in ctx.respond.call_args.args[0]


# ---------------------------------------------------------------------------
# /timeout
# ---------------------------------------------------------------------------

class TestTimeout:
    async def test_timeout_success(self, tmp_path) -> None:
        plugin = _make_plugin(tmp_path)
        ctx = _make_ctx(moderate_members=True)
        target_user = _make_target()
        target_member = _make_member_target()
        ctx.guild.get_member = MagicMock(return_value=target_member)

        await plugin.timeout(ctx, user=target_user, minutes=30)

        target_member.timeout.assert_awaited_once()
        assert "✅" in ctx.respond.call_args.args[0]
        assert "30 minutes" in ctx.respond.call_args.args[0]

    async def test_timeout_no_permission(self, tmp_path) -> None:
        plugin = _make_plugin(tmp_path)
        ctx = _make_ctx(moderate_members=False)

        await plugin.timeout(ctx, user=_make_target(), minutes=10)

        assert "moderate_members" in ctx.respond.call_args.args[0]

    async def test_timeout_user_not_in_guild(self, tmp_path) -> None:
        plugin = _make_plugin(tmp_path)
        ctx = _make_ctx(moderate_members=True)
        ctx.guild.get_member = MagicMock(return_value=None)

        await plugin.timeout(ctx, user=_make_target(), minutes=10)

        assert "not in this server" in ctx.respond.call_args.args[0]

    async def test_timeout_forbidden_is_caught(self, tmp_path) -> None:
        plugin = _make_plugin(tmp_path)
        ctx = _make_ctx(moderate_members=True)
        target_user = _make_target()
        target_member = _make_member_target()
        target_member.timeout = AsyncMock(
            side_effect=discord.Forbidden(MagicMock(), "no perms")
        )
        ctx.guild.get_member = MagicMock(return_value=target_member)

        await plugin.timeout(ctx, user=target_user, minutes=5)

        assert "lack permission" in ctx.respond.call_args.args[0]

    async def test_timeout_http_exception_is_caught(self, tmp_path) -> None:
        plugin = _make_plugin(tmp_path)
        ctx = _make_ctx(moderate_members=True)
        target_user = _make_target()
        target_member = _make_member_target()
        target_member.timeout = AsyncMock(
            side_effect=discord.HTTPException(MagicMock(), "error")
        )
        ctx.guild.get_member = MagicMock(return_value=target_member)

        await plugin.timeout(ctx, user=target_user, minutes=5)

        assert "Failed to timeout" in ctx.respond.call_args.args[0]

    async def test_timeout_minutes_clamped_to_minimum(self, tmp_path) -> None:
        """Negative or zero minutes should be clamped to 1."""
        plugin = _make_plugin(tmp_path)
        ctx = _make_ctx(moderate_members=True)
        target_user = _make_target()
        target_member = _make_member_target()
        ctx.guild.get_member = MagicMock(return_value=target_member)

        await plugin.timeout(ctx, user=target_user, minutes=-5)

        target_member.timeout.assert_awaited_once()
        # Response contains the clamped 1 minute, not -5
        assert "1 minutes" in ctx.respond.call_args.args[0]

    async def test_timeout_minutes_clamped_to_maximum(self, tmp_path) -> None:
        """Minutes above 40320 (28 days) should be clamped."""
        plugin = _make_plugin(tmp_path)
        ctx = _make_ctx(moderate_members=True)
        target_user = _make_target()
        target_member = _make_member_target()
        ctx.guild.get_member = MagicMock(return_value=target_member)

        await plugin.timeout(ctx, user=target_user, minutes=99999)

        target_member.timeout.assert_awaited_once()
        assert "40320 minutes" in ctx.respond.call_args.args[0]


# ---------------------------------------------------------------------------
# /warn
# ---------------------------------------------------------------------------

class TestWarn:
    async def test_warn_success_first_warning(self, tmp_path) -> None:
        plugin = _make_plugin(tmp_path)
        ctx = _make_ctx(moderate_members=True)
        target_user = _make_target()
        # No member in guild — auto-mute skipped safely
        ctx.guild.get_member = MagicMock(return_value=None)

        await plugin.warn(ctx, user=target_user, reason="spamming")

        ctx.respond.assert_awaited()
        response = ctx.respond.call_args.args[0]
        assert "⚠️" in response
        assert "Warning #1" in response

    async def test_warn_accumulates_per_user(self, tmp_path) -> None:
        plugin = _make_plugin(tmp_path)
        ctx = _make_ctx(moderate_members=True)
        target_user = _make_target()
        ctx.guild.get_member = MagicMock(return_value=None)

        await plugin.warn(ctx, user=target_user, reason="first")
        ctx.respond.reset_mock()
        await plugin.warn(ctx, user=target_user, reason="second")

        response = ctx.respond.call_args.args[0]
        assert "Warning #2" in response

    async def test_warn_guild_isolation(self, tmp_path) -> None:
        """Warns for the same user in two different guilds are counted separately."""
        plugin = _make_plugin(tmp_path)
        target_user = _make_target()

        ctx_a = _make_ctx(guild_id=100, moderate_members=True)
        ctx_a.guild.get_member = MagicMock(return_value=None)
        ctx_b = _make_ctx(guild_id=200, moderate_members=True)
        ctx_b.guild.get_member = MagicMock(return_value=None)

        await plugin.warn(ctx_a, user=target_user, reason="in guild A")
        ctx_a.respond.reset_mock()
        await plugin.warn(ctx_a, user=target_user, reason="in guild A again")
        await plugin.warn(ctx_b, user=target_user, reason="in guild B")

        # Guild A: count 2, Guild B: count 1
        assert "Warning #2" in ctx_a.respond.call_args.args[0]
        assert "Warning #1" in ctx_b.respond.call_args.args[0]

    async def test_warn_no_permission(self, tmp_path) -> None:
        plugin = _make_plugin(tmp_path)
        ctx = _make_ctx(moderate_members=False)

        await plugin.warn(ctx, user=_make_target(), reason="test")

        assert "moderate_members" in ctx.respond.call_args.args[0]

    async def test_warn_rate_limited(self, tmp_path) -> None:
        plugin = _make_plugin(tmp_path)
        ctx = _make_ctx(moderate_members=True)
        ctx.guild.get_member = MagicMock(return_value=None)

        # Exhaust the warn budget (10 per hour)
        limit = RateLimit(max_calls=10, window_minutes=60)
        for _ in range(10):
            await plugin.warn_limiter.check_limit(MOD_USER_ID, "warn", limit)

        await plugin.warn(ctx, user=_make_target(), reason="test")

        assert "⏳" in ctx.respond.call_args.args[0]

    async def test_warn_disabled_for_guild(self, tmp_path) -> None:
        plugin = _make_plugin(tmp_path)
        await plugin._update_config(GUILD_ID, enable_warnings=False)
        ctx = _make_ctx(moderate_members=True)

        await plugin.warn(ctx, user=_make_target())

        assert "Warnings are disabled" in ctx.respond.call_args.args[0]

    async def test_warn_auto_mute_at_threshold(self, tmp_path) -> None:
        """Reaching the warn threshold triggers auto-mute via add_roles."""
        plugin = _make_plugin(tmp_path)
        # Threshold is 3 (default)
        ctx = _make_ctx(moderate_members=True)
        target_user = _make_target()
        target_member = _make_member_target()
        target_member.roles = []  # not already muted
        ctx.guild.get_member = MagicMock(return_value=target_member)

        # Set up the guild to return a mute role
        mute_role = MagicMock(spec=discord.Role)
        mute_role.name = "Muted"
        ctx.guild.roles = [mute_role]

        with patch("discord.utils.get", return_value=mute_role):
            await plugin.warn(ctx, user=target_user, reason="1")
            ctx.respond.reset_mock()
            await plugin.warn(ctx, user=target_user, reason="2")
            ctx.respond.reset_mock()
            await plugin.warn(ctx, user=target_user, reason="3")

        target_member.add_roles.assert_awaited_once()

    async def test_warn_in_dm_context_rejected(self, tmp_path) -> None:
        plugin = _make_plugin(tmp_path)
        ctx = _make_ctx(guild_id=None, moderate_members=True)
        ctx.member = None

        await plugin.warn(ctx, user=_make_target())

        assert "only be used inside a server" in ctx.respond.call_args.args[0]


# ---------------------------------------------------------------------------
# /warnings (view history)
# ---------------------------------------------------------------------------

class TestWarnings:
    async def test_warnings_no_warnings(self, tmp_path) -> None:
        plugin = _make_plugin(tmp_path)
        ctx = _make_ctx()
        target_user = _make_target()

        await plugin.warnings(ctx, user=target_user)

        assert "no warnings" in ctx.respond.call_args.args[0]

    async def test_warnings_shows_history(self, tmp_path) -> None:
        plugin = _make_plugin(tmp_path)
        # Issue a warning first
        warn_ctx = _make_ctx(moderate_members=True)
        warn_ctx.guild.get_member = MagicMock(return_value=None)
        target_user = _make_target()
        await plugin.warn(warn_ctx, user=target_user, reason="bad behaviour")

        ctx = _make_ctx()
        await plugin.warnings(ctx, user=target_user)

        # Responded with an embed
        ctx.respond.assert_awaited_once()
        call_kwargs = ctx.respond.call_args.kwargs
        assert "embed" in call_kwargs

    async def test_warnings_in_dm_context_rejected(self, tmp_path) -> None:
        plugin = _make_plugin(tmp_path)
        ctx = _make_ctx(guild_id=None)

        await plugin.warnings(ctx, user=_make_target())

        assert "only be used inside a server" in ctx.respond.call_args.args[0]


# ---------------------------------------------------------------------------
# /mute
# ---------------------------------------------------------------------------

class TestMute:
    async def test_mute_success(self, tmp_path) -> None:
        plugin = _make_plugin(tmp_path)
        ctx = _make_ctx(manage_roles=True)
        target_user = _make_target()
        target_member = _make_member_target()
        target_member.roles = []
        ctx.guild.get_member = MagicMock(return_value=target_member)

        mute_role = MagicMock(spec=discord.Role)
        mute_role.name = "Muted"
        ctx.guild.roles = [mute_role]

        with patch("discord.utils.get", return_value=mute_role):
            await plugin.mute(ctx, user=target_user)

        target_member.add_roles.assert_awaited_once()
        assert "🔇" in ctx.respond.call_args.args[0]

    async def test_mute_no_permission(self, tmp_path) -> None:
        plugin = _make_plugin(tmp_path)
        ctx = _make_ctx(manage_roles=False)

        await plugin.mute(ctx, user=_make_target())

        assert "manage_roles" in ctx.respond.call_args.args[0]

    async def test_mute_user_not_in_guild(self, tmp_path) -> None:
        plugin = _make_plugin(tmp_path)
        ctx = _make_ctx(manage_roles=True)
        ctx.guild.get_member = MagicMock(return_value=None)

        await plugin.mute(ctx, user=_make_target())

        assert "not in this server" in ctx.respond.call_args.args[0]

    async def test_mute_already_muted(self, tmp_path) -> None:
        plugin = _make_plugin(tmp_path)
        ctx = _make_ctx(manage_roles=True)
        target_user = _make_target()
        target_member = _make_member_target()
        mute_role = MagicMock(spec=discord.Role)
        mute_role.name = "Muted"
        target_member.roles = [mute_role]
        ctx.guild.get_member = MagicMock(return_value=target_member)

        with patch("discord.utils.get", return_value=mute_role):
            await plugin.mute(ctx, user=target_user)

        target_member.add_roles.assert_not_awaited()
        assert "already muted" in ctx.respond.call_args.args[0]

    async def test_mute_forbidden_is_caught(self, tmp_path) -> None:
        plugin = _make_plugin(tmp_path)
        ctx = _make_ctx(manage_roles=True)
        target_user = _make_target()
        target_member = _make_member_target()
        target_member.roles = []
        target_member.add_roles = AsyncMock(
            side_effect=discord.Forbidden(MagicMock(), "no perms")
        )
        ctx.guild.get_member = MagicMock(return_value=target_member)
        mute_role = MagicMock(spec=discord.Role)
        mute_role.name = "Muted"

        with patch("discord.utils.get", return_value=mute_role):
            await plugin.mute(ctx, user=target_user)

        assert "lack permission" in ctx.respond.call_args.args[0]


# ---------------------------------------------------------------------------
# /unmute
# ---------------------------------------------------------------------------

class TestUnmute:
    async def test_unmute_success(self, tmp_path) -> None:
        plugin = _make_plugin(tmp_path)
        ctx = _make_ctx(manage_roles=True)
        target_user = _make_target()
        target_member = _make_member_target()
        mute_role = MagicMock(spec=discord.Role)
        mute_role.name = "Muted"
        target_member.roles = [mute_role]
        ctx.guild.get_member = MagicMock(return_value=target_member)

        with patch("discord.utils.get", return_value=mute_role):
            await plugin.unmute(ctx, user=target_user)

        target_member.remove_roles.assert_awaited_once()
        assert "🔊" in ctx.respond.call_args.args[0]

    async def test_unmute_not_muted(self, tmp_path) -> None:
        plugin = _make_plugin(tmp_path)
        ctx = _make_ctx(manage_roles=True)
        target_user = _make_target()
        target_member = _make_member_target()
        target_member.roles = []
        ctx.guild.get_member = MagicMock(return_value=target_member)

        with patch("discord.utils.get", return_value=None):
            await plugin.unmute(ctx, user=target_user)

        assert "not muted" in ctx.respond.call_args.args[0]

    async def test_unmute_no_permission(self, tmp_path) -> None:
        plugin = _make_plugin(tmp_path)
        ctx = _make_ctx(manage_roles=False)

        await plugin.unmute(ctx, user=_make_target())

        assert "manage_roles" in ctx.respond.call_args.args[0]

    async def test_unmute_forbidden_is_caught(self, tmp_path) -> None:
        plugin = _make_plugin(tmp_path)
        ctx = _make_ctx(manage_roles=True)
        target_user = _make_target()
        target_member = _make_member_target()
        mute_role = MagicMock(spec=discord.Role)
        mute_role.name = "Muted"
        target_member.roles = [mute_role]
        target_member.remove_roles = AsyncMock(
            side_effect=discord.Forbidden(MagicMock(), "no perms")
        )
        ctx.guild.get_member = MagicMock(return_value=target_member)

        with patch("discord.utils.get", return_value=mute_role):
            await plugin.unmute(ctx, user=target_user)

        assert "lack permission" in ctx.respond.call_args.args[0]


# ---------------------------------------------------------------------------
# /mod_config
# ---------------------------------------------------------------------------

class TestModConfig:
    async def test_mod_config_responds_with_embed(self, tmp_path) -> None:
        plugin = _make_plugin(tmp_path)
        ctx = _make_ctx()

        await plugin.mod_config(ctx)

        ctx.respond.assert_awaited_once()
        call_kwargs = ctx.respond.call_args.kwargs
        assert "embed" in call_kwargs
        assert call_kwargs["embed"].title == "Moderation Config"

    async def test_mod_config_in_dm_context_rejected(self, tmp_path) -> None:
        plugin = _make_plugin(tmp_path)
        ctx = _make_ctx(guild_id=None)

        await plugin.mod_config(ctx)

        assert "only be used inside a server" in ctx.respond.call_args.args[0]


# ---------------------------------------------------------------------------
# Audit log — silent on Forbidden, no-op without channel
# ---------------------------------------------------------------------------

class TestAuditLog:
    async def test_log_moderation_skipped_without_channel(self, tmp_path) -> None:
        """_log_moderation is a no-op when audit_channel is not configured."""
        plugin = _make_plugin(tmp_path)
        ctx = _make_ctx()
        ctx.guild.get_channel = MagicMock(return_value=None)
        target_user = _make_target()

        # Should complete without error
        await plugin._log_moderation(ctx, "kick", target_user, "test")

    async def test_log_moderation_forbidden_is_swallowed(self, tmp_path) -> None:
        """A Forbidden error on the audit channel send must not propagate."""
        plugin = _make_plugin(tmp_path)
        await plugin._update_config(GUILD_ID, audit_channel=999)
        ctx = _make_ctx()
        audit_ch = MagicMock()
        audit_ch.send = AsyncMock(side_effect=discord.Forbidden(MagicMock(), "no perms"))
        ctx.guild.get_channel = MagicMock(return_value=audit_ch)
        target_user = _make_target()

        # Must not raise
        await plugin._log_moderation(ctx, "ban", target_user, "reason")


# ---------------------------------------------------------------------------
# on_load
# ---------------------------------------------------------------------------

async def test_on_load_completes(tmp_path) -> None:
    plugin = _make_plugin(tmp_path)
    await plugin.on_load()  # must not raise
