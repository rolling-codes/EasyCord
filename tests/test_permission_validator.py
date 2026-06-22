"""Tests for _validate_plugin_permissions on _PluginsMixin."""
from __future__ import annotations

import logging
from unittest.mock import MagicMock

import discord
import pytest

from easycord._bot_plugins import _PluginsMixin
from easycord.decorators import slash
from easycord.plugin import Plugin


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_guild(*, guild_id: int = 123456, name: str = "My Server", **perms_kwargs) -> MagicMock:
    """Return a fake discord.Guild whose bot member has the given permissions."""
    guild = MagicMock(spec=discord.Guild)
    guild.id = guild_id
    guild.name = name

    perms = discord.Permissions.none()
    for perm, value in perms_kwargs.items():
        setattr(perms, perm, value)

    me = MagicMock(spec=discord.Member)
    me.guild_permissions = perms
    guild.me = me
    return guild


def _make_mixin(guilds: list) -> _PluginsMixin:
    """Create a bare _PluginsMixin instance with a .guilds attribute."""
    mixin = _PluginsMixin.__new__(_PluginsMixin)
    mixin.guilds = guilds
    return mixin


def _make_plugin(perms: list[str] | None = None, *, require_admin: bool = False) -> Plugin:
    """Build a Plugin subclass with one @slash command that declares *perms*."""

    class TestPlugin(Plugin):
        @slash(description="Test command", permissions=perms, require_admin=require_admin)
        async def do_thing(self, ctx):
            pass

    plugin = TestPlugin.__new__(TestPlugin)
    Plugin.__init__(plugin)
    plugin._bot = MagicMock()  # set after __init__ so it isn't overwritten to None
    return plugin


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestValidatePluginPermissions:
    def test_warns_when_bot_lacks_required_permission(self, caplog):
        """Bot is missing kick_members → warning emitted."""
        guild = _make_guild(guild_id=123456, name="My Server", kick_members=False)
        mixin = _make_mixin([guild])
        plugin = _make_plugin(perms=["kick_members"])

        with caplog.at_level(logging.WARNING, logger="easycord"):
            mixin._validate_plugin_permissions(plugin)

        assert any(
            "kick_members" in record.message and "My Server" in record.message
            for record in caplog.records
        ), f"Expected permission warning, got: {[r.message for r in caplog.records]}"

    def test_no_warning_when_bot_has_required_permission(self, caplog):
        """Bot has kick_members → no warning."""
        guild = _make_guild(guild_id=123456, name="My Server", kick_members=True)
        mixin = _make_mixin([guild])
        plugin = _make_plugin(perms=["kick_members"])

        with caplog.at_level(logging.WARNING, logger="easycord"):
            mixin._validate_plugin_permissions(plugin)

        perm_warnings = [
            r for r in caplog.records
            if "kick_members" in r.message and r.levelno == logging.WARNING
        ]
        assert perm_warnings == []

    def test_no_crash_when_bot_in_no_guilds(self, caplog):
        """Empty guild list → silently skip, no exception."""
        mixin = _make_mixin([])
        plugin = _make_plugin(perms=["kick_members"])

        # Must not raise
        mixin._validate_plugin_permissions(plugin)
        assert caplog.records == []

    def test_require_admin_triggers_administrator_check(self, caplog):
        """require_admin=True checks 'administrator' permission."""
        guild = _make_guild(guild_id=111, name="Admin Server", administrator=False)
        mixin = _make_mixin([guild])
        plugin = _make_plugin(require_admin=True)

        with caplog.at_level(logging.WARNING, logger="easycord"):
            mixin._validate_plugin_permissions(plugin)

        assert any(
            "administrator" in record.message
            for record in caplog.records
        )

    def test_no_permissions_declared_no_warning(self, caplog):
        """Command with no permissions= and no require_admin → no warning."""
        guild = _make_guild(guild_id=999, name="Server", kick_members=False)
        mixin = _make_mixin([guild])
        plugin = _make_plugin(perms=None)

        with caplog.at_level(logging.WARNING, logger="easycord"):
            mixin._validate_plugin_permissions(plugin)

        assert caplog.records == []

    def test_warning_includes_guild_id_and_name(self, caplog):
        """Warning message must contain the guild ID and name."""
        guild = _make_guild(guild_id=987654, name="Test Guild", manage_messages=False)
        mixin = _make_mixin([guild])
        plugin = _make_plugin(perms=["manage_messages"])

        with caplog.at_level(logging.WARNING, logger="easycord"):
            mixin._validate_plugin_permissions(plugin)

        msgs = [r.message for r in caplog.records if r.levelno == logging.WARNING]
        assert any("987654" in m and "Test Guild" in m for m in msgs)

    def test_guild_scoped_command_only_checked_in_matching_guild(self, caplog):
        """guild_id on a command limits the permission check to that guild only."""

        class ScopedPlugin(Plugin):
            @slash(description="Scoped", permissions=["ban_members"], guild_id=200)
            async def scoped_cmd(self, ctx):
                pass

        plugin = ScopedPlugin.__new__(ScopedPlugin)
        Plugin.__init__(plugin)
        plugin._bot = MagicMock()

        # Guild 200 has the permission; guild 300 does not but must not be checked.
        guild_200 = _make_guild(guild_id=200, name="Target Guild", ban_members=True)
        guild_300 = _make_guild(guild_id=300, name="Other Guild", ban_members=False)
        mixin = _make_mixin([guild_200, guild_300])

        with caplog.at_level(logging.WARNING, logger="easycord"):
            mixin._validate_plugin_permissions(plugin)

        # No warning because guild 200 (the only checked one) has the permission.
        perm_warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert perm_warnings == []

    def test_multiple_guilds_each_checked_independently(self, caplog):
        """Multiple guilds — warning only for the guild that's missing the perm."""
        guild_ok = _make_guild(guild_id=1, name="OK Guild", kick_members=True)
        guild_bad = _make_guild(guild_id=2, name="Bad Guild", kick_members=False)
        mixin = _make_mixin([guild_ok, guild_bad])
        plugin = _make_plugin(perms=["kick_members"])

        with caplog.at_level(logging.WARNING, logger="easycord"):
            mixin._validate_plugin_permissions(plugin)

        warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert len(warnings) == 1
        assert "Bad Guild" in warnings[0].message

    def test_me_is_none_skips_guild(self, caplog):
        """If guild.me is None the guild is skipped without error."""
        guild = _make_guild(guild_id=50, name="Ghost Guild", kick_members=False)
        guild.me = None  # override
        mixin = _make_mixin([guild])
        plugin = _make_plugin(perms=["kick_members"])

        # Must not raise
        mixin._validate_plugin_permissions(plugin)
        assert caplog.records == []
