"""Tests for require_admin, @command_error, and describe() features."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import discord
from discord import app_commands
import pytest

from easycord.decorators import slash, command_error, describe
from easycord.decorators import (
    cooldown,
    install_type,
    message_command,
    premium_required,
    require_permissions,
    user_command,
)
from easycord.context import Context


# ---------------------------------------------------------------------------
# describe() decorator
# ---------------------------------------------------------------------------

class TestDescribe:
    def test_sets_description_attribute(self):
        @describe(member="The member to kick", reason="Why")
        async def kick(ctx, member, reason=""):
            pass

        assert kick.__discord_app_commands_param_description__["member"] == "The member to kick"
        assert kick.__discord_app_commands_param_description__["reason"] == "Why"

    def test_stacks_with_slash(self):
        @slash(description="Kick a member")
        @describe(member="The member")
        async def kick(ctx, member):
            pass

        assert kick._is_slash
        assert kick.__discord_app_commands_param_description__["member"] == "The member"

    def test_multiple_calls_merge(self):
        @describe(a="desc_a")
        @describe(b="desc_b")
        async def cmd(ctx, a, b):
            pass

        assert cmd.__discord_app_commands_param_description__["a"] == "desc_a"
        assert cmd.__discord_app_commands_param_description__["b"] == "desc_b"


# ---------------------------------------------------------------------------
# command_error() decorator
# ---------------------------------------------------------------------------

class TestCommandError:
    def test_marks_handler(self):
        @command_error("divide")
        async def divide_error(self, ctx, exc):
            pass

        assert divide_error._is_command_error is True
        assert divide_error._command_error_for == "divide"

    def test_handler_registered_on_plugin(self):
        """_scan_methods should populate _command_error_handlers."""
        from easycord import Plugin

        class MathPlugin(Plugin):
            @slash(description="Divide")
            async def divide(self, ctx, a: int, b: int):
                await ctx.respond(str(a // b))

            @command_error("divide")
            async def divide_error(self, ctx, exc):
                await ctx.respond("error", ephemeral=True)

        bot = MagicMock()
        bot._plugins = []
        bot._event_handlers = {}
        bot._command_error_handlers = {}
        bot.ai_tools = {}
        bot.tool_registry = MagicMock()
        bot.tool_registry._tools = {}
        bot.tree = MagicMock()
        bot.is_ready = MagicMock(return_value=False)

        # Patch _register_slash so we can isolate the handler scanning
        bot._register_slash = MagicMock()
        bot._register_context_menu = MagicMock()
        bot._register_component_handler = MagicMock()
        bot._register_modal_handler = MagicMock()

        from easycord._bot_plugins import _PluginsMixin
        plugin = MathPlugin()
        plugin._bot = bot
        _PluginsMixin._scan_methods(bot, plugin)

        assert "divide" in bot._command_error_handlers


# ---------------------------------------------------------------------------
# require_admin in slash decorator
# ---------------------------------------------------------------------------

class TestRequireAdmin:
    def test_slash_stores_require_admin(self):
        @slash(description="Admin cmd", require_admin=True)
        async def reset(ctx):
            pass

        assert reset._slash_require_admin is True

    def test_slash_default_require_admin_false(self):
        @slash(description="Normal cmd")
        async def ping(ctx):
            pass

        assert ping._slash_require_admin is False

    @pytest.mark.asyncio
    async def test_require_admin_blocks_non_admin(self):
        """_build_slash_callback should reject members without administrator."""
        from easycord._bot_commands import _CommandsMixin

        called = []

        async def handler(ctx):
            called.append(True)

        bot = MagicMock()
        bot._middleware = []
        bot._error_handler = None
        bot._command_error_handlers = {}

        callback = _CommandsMixin._build_slash_callback(
            bot,
            handler,
            require_admin=True,
            ephemeral=False,
            guild_only=False,
            permissions=None,
            cooldown=None,
            command_name="reset",
        )

        interaction = MagicMock(spec=discord.Interaction)
        interaction.response = AsyncMock()
        interaction.response.is_done = MagicMock(return_value=False)
        interaction.followup = AsyncMock()

        guild = MagicMock()
        member = MagicMock()
        perms = MagicMock()
        perms.administrator = False
        member.guild_permissions = perms
        guild.get_member.return_value = member
        interaction.guild = guild
        interaction.user = MagicMock()
        interaction.user.id = 42
        interaction.locale = discord.Locale.american_english

        ctx = Context(interaction)
        ctx.respond = AsyncMock()

        # Patch Context construction inside the callback
        with patch("easycord._bot_commands.Context", return_value=ctx):
            with patch("easycord._bot_commands.build_chain") as mock_chain:
                # build_chain(ctx, invoke_fn, middleware) must return a callable
                mock_chain.side_effect = lambda c, invoke_fn, mw: invoke_fn
                await callback(interaction)

        assert not called
        ctx.respond.assert_called_once()
        msg = ctx.respond.call_args[0][0]
        assert "permission" in msg.lower() or "administrator" in msg.lower()

    @pytest.mark.asyncio
    async def test_require_admin_allows_admin(self):
        from easycord._bot_commands import _CommandsMixin

        called = []

        async def handler(ctx):
            called.append(True)

        bot = MagicMock()
        bot._middleware = []
        bot._error_handler = None
        bot._command_error_handlers = {}

        callback = _CommandsMixin._build_slash_callback(
            bot,
            handler,
            require_admin=True,
            ephemeral=False,
            guild_only=False,
            permissions=None,
            cooldown=None,
            command_name="reset",
        )

        interaction = MagicMock(spec=discord.Interaction)
        interaction.response = AsyncMock()
        interaction.response.is_done = MagicMock(return_value=False)
        interaction.followup = AsyncMock()

        guild = MagicMock()
        member = MagicMock()
        perms = MagicMock()
        perms.administrator = True
        member.guild_permissions = perms
        guild.get_member.return_value = member
        interaction.guild = guild
        interaction.user = MagicMock()
        interaction.user.id = 42
        interaction.locale = discord.Locale.american_english

        ctx = Context(interaction)
        ctx.respond = AsyncMock()

        with patch("easycord._bot_commands.Context", return_value=ctx):
            with patch("easycord._bot_commands.build_chain") as mock_chain:
                mock_chain.side_effect = lambda c, invoke_fn, mw: invoke_fn
                await callback(interaction)

        assert called


# ---------------------------------------------------------------------------
# Stacked guard decorators and metadata propagation
# ---------------------------------------------------------------------------

class TestStackedCommandDecorators:
    def test_cooldown_metadata_supports_rate_and_bucket(self):
        @slash(description="Limited")
        @cooldown(rate=2, per=10.0, bucket="guild")
        async def limited(ctx):
            pass

        assert limited._slash_cooldown == 10.0
        assert limited._slash_cooldown_rate == 2
        assert limited._slash_cooldown_bucket == "guild"

    def test_require_permissions_metadata(self):
        @slash(description="Moderate")
        @require_permissions("manage_messages")
        async def moderate(ctx):
            pass

        assert moderate._slash_permissions == ["manage_messages"]

    def test_inline_empty_permissions_override_stacked_metadata(self):
        @slash(description="Public", permissions=[])
        @require_permissions("administrator")
        async def public(ctx):
            pass

        assert public._slash_permissions == []

    def test_install_type_metadata(self):
        @slash(description="Info")
        @install_type(guild=True, user=True)
        async def info(ctx):
            pass

        assert info._slash_allowed_contexts.guild is True
        assert info._slash_allowed_contexts.dm_channel is True
        assert info._slash_allowed_contexts.private_channel is True
        assert info._slash_allowed_installs.guild is True
        assert info._slash_allowed_installs.user is True

    def test_premium_required_metadata(self):
        @slash(description="Premium")
        @premium_required
        async def premium(ctx):
            pass

        assert premium._slash_premium_required is True

    def test_invalid_cooldown_rejected(self):
        with pytest.raises(ValueError, match="bucket"):
            cooldown(per=5.0, bucket="channel")


class TestBotCommandGuards:
    @pytest.mark.asyncio
    async def test_cooldown_rate_allows_multiple_uses_then_blocks(self):
        from easycord import Bot
        from easycord.testing import invoke

        bot = Bot(auto_sync=False, db_backend="memory")
        calls = []
        try:
            @bot.slash(description="Limited", cooldown=30.0, cooldown_rate=2)
            async def limited(ctx):
                calls.append(ctx.user.id)
                await ctx.respond("ok")

            first = await invoke(bot, "limited", user_id=1)
            second = await invoke(bot, "limited", user_id=1)
            third = await invoke(bot, "limited", user_id=1)

            assert first.last_response == "ok"
            assert second.last_response == "ok"
            assert "cooldown" in (third.last_response or "").lower()
            assert calls == [1, 1]
        finally:
            await bot.close()

    @pytest.mark.asyncio
    async def test_guild_cooldown_bucket_is_shared_by_members(self):
        from easycord import Bot
        from easycord.testing import invoke

        bot = Bot(auto_sync=False, db_backend="memory")
        calls = []
        try:
            @bot.slash(description="Guild limited", cooldown=30.0, cooldown_bucket="guild")
            async def guild_limited(ctx):
                calls.append(ctx.user.id)
                await ctx.respond("ok")

            first = await invoke(bot, "guild_limited", user_id=1, guild_id=100)
            second = await invoke(bot, "guild_limited", user_id=2, guild_id=100)

            assert first.last_response == "ok"
            assert "cooldown" in (second.last_response or "").lower()
            assert calls == [1]
        finally:
            await bot.close()

    @pytest.mark.asyncio
    async def test_guild_cooldown_bucket_is_per_user_in_dms(self):
        from easycord import Bot
        from easycord.testing import invoke

        bot = Bot(auto_sync=False, db_backend="memory")
        calls = []
        try:
            @bot.slash(description="DM guild limited", cooldown=30.0, cooldown_bucket="guild")
            async def dm_guild_limited(ctx):
                calls.append(ctx.user.id)
                await ctx.respond("ok")

            first = await invoke(bot, "dm_guild_limited", user_id=1, guild_id=None)
            second = await invoke(bot, "dm_guild_limited", user_id=2, guild_id=None)
            third = await invoke(bot, "dm_guild_limited", user_id=1, guild_id=None)

            assert first.last_response == "ok"
            assert second.last_response == "ok"
            assert "cooldown" in (third.last_response or "").lower()
            assert calls == [1, 2]
        finally:
            await bot.close()

    @pytest.mark.asyncio
    async def test_premium_required_blocks_without_entitlement(self):
        from easycord import Bot
        from easycord.testing import invoke

        bot = Bot(auto_sync=False, db_backend="memory")
        calls = []
        try:
            @bot.slash(description="Premium", premium_required=True)
            async def premium(ctx):
                calls.append(True)
                await ctx.respond("premium ok")

            blocked = await invoke(bot, "premium")
            allowed = await invoke(bot, "premium", entitlements=[object()])

            assert "premium" in (blocked.last_response or "").lower()
            assert allowed.last_response == "premium ok"
            assert calls == [True]
        finally:
            await bot.close()

    @pytest.mark.asyncio
    async def test_require_permissions_decorator_works_on_bot_command(self):
        from easycord import Bot
        from easycord.testing import invoke

        bot = Bot(auto_sync=False, db_backend="memory")
        calls = []
        try:
            @bot.slash(description="Admin")
            @require_permissions("administrator")
            async def admin(ctx):
                calls.append(True)
                await ctx.respond("admin ok")

            blocked = await invoke(bot, "admin", is_admin=False)
            allowed = await invoke(bot, "admin", is_admin=True)

            assert "administrator" in (blocked.last_response or "").lower()
            assert allowed.last_response == "admin ok"
            assert calls == [True]
        finally:
            await bot.close()

    @pytest.mark.asyncio
    async def test_require_permissions_decorator_works_on_plugin_command(self):
        from easycord import Bot, Plugin
        from easycord.testing import invoke

        calls = []

        class AdminPlugin(Plugin):
            @slash(description="Admin")
            @require_permissions("administrator")
            async def plugin_admin(self, ctx):
                calls.append(True)
                await ctx.respond("plugin admin ok")

        bot = Bot(auto_sync=False, db_backend="memory")
        try:
            bot.add_plugin(AdminPlugin())

            blocked = await invoke(bot, "plugin_admin", is_admin=False)
            allowed = await invoke(bot, "plugin_admin", is_admin=True)

            assert "administrator" in (blocked.last_response or "").lower()
            assert allowed.last_response == "plugin admin ok"
            assert calls == [True]
        finally:
            await bot.close()

    @pytest.mark.asyncio
    async def test_inline_empty_permissions_override_stacked_guard(self):
        from easycord import Bot
        from easycord.testing import invoke

        bot = Bot(auto_sync=False, db_backend="memory")
        calls = []
        try:
            @bot.slash(description="Public", permissions=[])
            @require_permissions("administrator")
            async def public(ctx):
                calls.append(True)
                await ctx.respond("public ok")

            allowed = await invoke(bot, "public", is_admin=False)

            assert allowed.last_response == "public ok"
            assert calls == [True]
        finally:
            await bot.close()


class TestPluginErrorHandling:
    @pytest.mark.asyncio
    async def test_plugin_on_error_runs_before_global_handler(self):
        from easycord import Bot, Plugin
        from easycord.testing import invoke

        events = []

        class ErrorPlugin(Plugin):
            @slash(description="Broken")
            async def broken(self, ctx):
                raise RuntimeError("boom")

            async def on_error(self, ctx, exc):
                events.append(("plugin", str(exc)))
                await ctx.respond("plugin handled")

        bot = Bot(auto_sync=False, db_backend="memory")

        @bot.on_error
        async def global_error(ctx, exc):
            events.append(("global", str(exc)))
            await ctx.respond("global handled")

        try:
            bot.add_plugin(ErrorPlugin())
            ctx = await invoke(bot, "broken")

            assert ctx.last_response == "plugin handled"
            assert events == [("plugin", "boom")]
        finally:
            await bot.close()

    @pytest.mark.asyncio
    async def test_command_error_runs_before_plugin_on_error(self):
        from easycord import Bot, Plugin
        from easycord.testing import invoke

        events = []

        class ErrorPlugin(Plugin):
            @slash(description="Broken")
            async def broken(self, ctx):
                raise RuntimeError("boom")

            @command_error("broken")
            async def broken_error(self, ctx, exc):
                events.append(("command", str(exc)))
                await ctx.respond("command handled")

            async def on_error(self, ctx, exc):
                events.append(("plugin", str(exc)))
                await ctx.respond("plugin handled")

        bot = Bot(auto_sync=False, db_backend="memory")
        try:
            bot.add_plugin(ErrorPlugin())
            ctx = await invoke(bot, "broken")

            assert ctx.last_response == "command handled"
            assert events == [("command", "boom")]
        finally:
            await bot.close()


class TestScannerMetadataPropagation:
    def _mock_bot_for_scan(self):
        bot = MagicMock()
        bot._plugins = []
        bot._event_handlers = {}
        bot._command_error_handlers = {}
        bot.ai_tools = {}
        bot.tool_registry = MagicMock()
        bot.tool_registry._tools = {}
        bot.is_ready = MagicMock(return_value=False)
        bot._register_slash = MagicMock()
        bot._register_context_menu = MagicMock()
        bot._register_component_handler = MagicMock()
        bot._register_modal_handler = MagicMock()
        return bot

    def test_install_type_propagates_to_register_slash(self):
        from easycord import Plugin
        from easycord._bot_plugins import _PluginsMixin

        class InstallPlugin(Plugin):
            @slash(description="Info")
            @install_type(guild=True, user=True)
            async def info(self, ctx):
                pass

        bot = self._mock_bot_for_scan()
        plugin = InstallPlugin()
        plugin._bot = bot
        _PluginsMixin._scan_methods(bot, plugin)

        kwargs = bot._register_slash.call_args.kwargs
        assert kwargs["allowed_contexts"].guild is True
        assert kwargs["allowed_contexts"].dm_channel is True
        assert kwargs["allowed_contexts"].private_channel is True
        assert kwargs["allowed_installs"].guild is True
        assert kwargs["allowed_installs"].user is True

    def test_context_menu_metadata_propagates_to_register_context_menu(self):
        from easycord import Plugin
        from easycord._bot_plugins import _PluginsMixin

        contexts = app_commands.AppCommandContext(guild=True, dm_channel=False, private_channel=False)
        installs = app_commands.AppInstallationType(guild=True, user=False)

        class MenuPlugin(Plugin):
            @user_command(
                name="Profile",
                nsfw=True,
                allowed_contexts=contexts,
                allowed_installs=installs,
            )
            async def profile(self, ctx, member):
                pass

            @message_command(
                name="Quote",
                nsfw=True,
                allowed_contexts=contexts,
                allowed_installs=installs,
            )
            async def quote(self, ctx, message):
                pass

        bot = self._mock_bot_for_scan()
        plugin = MenuPlugin()
        plugin._bot = bot
        _PluginsMixin._scan_methods(bot, plugin)

        calls = bot._register_context_menu.call_args_list
        assert len(calls) == 2
        for call in calls:
            assert call.kwargs["nsfw"] is True
            assert call.kwargs["allowed_contexts"] is contexts
            assert call.kwargs["allowed_installs"] is installs
