"""Tests for Plugin Power Pack: dependency declarations and per-guild feature flags."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from easycord import Bot, Plugin, PluginDependencyError, slash
from easycord._bot_plugins import _PluginsMixin
from easycord.testing import invoke


# ---------------------------------------------------------------------------
# Minimal bot stub used throughout
# ---------------------------------------------------------------------------

def _make_bot() -> MagicMock:
    bot = MagicMock()
    bot._plugins = []
    bot._guild_disabled_plugins = {}
    bot.is_ready.return_value = False

    # Bind real mixin methods to the mock
    bot.add_plugin = lambda p: _PluginsMixin.add_plugin(bot, p)
    bot.disable_plugin = lambda name, guild_id: _PluginsMixin.disable_plugin(bot, name, guild_id)
    bot.enable_plugin = lambda name, guild_id: _PluginsMixin.enable_plugin(bot, name, guild_id)
    bot.is_plugin_enabled = lambda name, guild_id: _PluginsMixin.is_plugin_enabled(bot, name, guild_id)

    # Stub out side-effectful methods that fire during add_plugin
    bot._scan_methods = MagicMock()
    return bot


# ---------------------------------------------------------------------------
# Feature 1 — Plugin dependency declarations
# ---------------------------------------------------------------------------


class TestPluginDependencyDeclarations:
    def test_no_requires_loads_fine(self) -> None:
        class SimplePlugin(Plugin):
            pass

        bot = _make_bot()
        p = SimplePlugin()
        bot.add_plugin(p)
        assert p in bot._plugins

    def test_satisfied_dep_loads_fine(self) -> None:
        class CorePlugin(Plugin):
            pass

        class ExtPlugin(Plugin):
            requires = ("coreplugin",)

        bot = _make_bot()
        core = CorePlugin()
        bot.add_plugin(core)
        ext = ExtPlugin()
        bot.add_plugin(ext)
        assert ext in bot._plugins

    def test_missing_dep_raises_plugin_dependency_error(self) -> None:
        class InventoryPlugin(Plugin):
            requires = ("economy",)

        bot = _make_bot()
        with pytest.raises(PluginDependencyError) as exc_info:
            bot.add_plugin(InventoryPlugin())
        assert "economy" in str(exc_info.value)
        assert "economy" in exc_info.value.missing

    def test_error_names_the_plugin_class(self) -> None:
        class MyPlugin(Plugin):
            requires = ("missing_dep",)

        bot = _make_bot()
        with pytest.raises(PluginDependencyError) as exc_info:
            bot.add_plugin(MyPlugin())
        assert "MyPlugin" in exc_info.value.plugin_class

    def test_multiple_missing_deps_all_reported(self) -> None:
        class BigPlugin(Plugin):
            requires = ("alpha", "beta", "gamma")

        bot = _make_bot()
        with pytest.raises(PluginDependencyError) as exc_info:
            bot.add_plugin(BigPlugin())
        for dep in ("alpha", "beta", "gamma"):
            assert dep in exc_info.value.missing

    def test_partial_deps_reports_only_missing(self) -> None:
        class DepA(Plugin):
            pass

        class DepB(Plugin):
            pass

        class Composite(Plugin):
            requires = ("depa", "depb")

        bot = _make_bot()
        bot.add_plugin(DepA())
        with pytest.raises(PluginDependencyError) as exc_info:
            bot.add_plugin(Composite())
        assert "depb" in exc_info.value.missing
        assert "depa" not in exc_info.value.missing

    def test_wrong_load_order_raises(self) -> None:
        class EconomyPlugin(Plugin):
            pass

        class ShopPlugin(Plugin):
            requires = ("economyplugin",)

        bot = _make_bot()
        # Loading in wrong order should raise
        with pytest.raises(PluginDependencyError):
            bot.add_plugin(ShopPlugin())

        # Correct order succeeds
        bot2 = _make_bot()
        bot2.add_plugin(EconomyPlugin())
        bot2.add_plugin(ShopPlugin())
        assert len(bot2._plugins) == 2

    def test_empty_requires_tuple_loads_fine(self) -> None:
        class EmptyDepsPlugin(Plugin):
            requires = ()

        bot = _make_bot()
        bot.add_plugin(EmptyDepsPlugin())
        assert len(bot._plugins) == 1


# ---------------------------------------------------------------------------
# Feature 3 — Per-guild plugin feature flags
# ---------------------------------------------------------------------------


class TestPerGuildPluginFlags:
    def test_plugin_enabled_by_default(self) -> None:
        bot = _make_bot()
        assert bot.is_plugin_enabled("economy", 100) is True

    def test_disable_plugin_for_guild(self) -> None:
        bot = _make_bot()
        bot.disable_plugin("economy", 100)
        assert bot.is_plugin_enabled("economy", 100) is False

    def test_disable_does_not_affect_other_guilds(self) -> None:
        bot = _make_bot()
        bot.disable_plugin("economy", 100)
        assert bot.is_plugin_enabled("economy", 200) is True

    def test_enable_restores_plugin(self) -> None:
        bot = _make_bot()
        bot.disable_plugin("tags", 50)
        assert bot.is_plugin_enabled("tags", 50) is False
        bot.enable_plugin("tags", 50)
        assert bot.is_plugin_enabled("tags", 50) is True

    def test_enable_no_op_when_not_disabled(self) -> None:
        bot = _make_bot()
        bot.enable_plugin("polls", 999)
        assert bot.is_plugin_enabled("polls", 999) is True

    def test_disable_multiple_plugins_in_same_guild(self) -> None:
        bot = _make_bot()
        bot.disable_plugin("economy", 1)
        bot.disable_plugin("tags", 1)
        assert bot.is_plugin_enabled("economy", 1) is False
        assert bot.is_plugin_enabled("tags", 1) is False
        assert bot.is_plugin_enabled("polls", 1) is True

    def test_disable_same_plugin_in_multiple_guilds(self) -> None:
        bot = _make_bot()
        bot.disable_plugin("economy", 1)
        bot.disable_plugin("economy", 2)
        assert bot.is_plugin_enabled("economy", 1) is False
        assert bot.is_plugin_enabled("economy", 2) is False
        assert bot.is_plugin_enabled("economy", 3) is True

    def test_enable_only_affects_target_guild(self) -> None:
        bot = _make_bot()
        bot.disable_plugin("economy", 1)
        bot.disable_plugin("economy", 2)
        bot.enable_plugin("economy", 1)
        assert bot.is_plugin_enabled("economy", 1) is True
        assert bot.is_plugin_enabled("economy", 2) is False


# ---------------------------------------------------------------------------
# PluginDependencyError attributes
# ---------------------------------------------------------------------------


class TestPluginDependencyErrorAttributes:
    def test_is_runtime_error_subclass(self) -> None:
        err = PluginDependencyError("Foo", ["bar"])
        assert isinstance(err, RuntimeError)

    def test_missing_attribute_set_correctly(self) -> None:
        err = PluginDependencyError("MyPlugin", ["dep1", "dep2"])
        assert err.missing == ["dep1", "dep2"]

    def test_plugin_class_attribute_set_correctly(self) -> None:
        err = PluginDependencyError("TestPlugin", ["x"])
        assert err.plugin_class == "TestPlugin"

    def test_message_includes_class_and_deps(self) -> None:
        err = PluginDependencyError("ShopPlugin", ["economy"])
        msg = str(err)
        assert "ShopPlugin" in msg
        assert "economy" in msg


# ---------------------------------------------------------------------------
# Integration: per-guild flag guard in actual command dispatch
# ---------------------------------------------------------------------------


class TestPerGuildFlagDispatchGuard:
    @pytest.mark.asyncio
    async def test_disabled_plugin_returns_ephemeral_block(self) -> None:
        bot = Bot(auto_sync=False, db_backend="memory")
        try:
            class PingPlugin(Plugin):
                @slash(description="Ping")
                async def ping(self, ctx):
                    await ctx.respond("pong")

            bot.add_plugin(PingPlugin())

            # Confirm it works normally
            ctx = await invoke(bot, "ping", guild_id=100)
            assert ctx.last_response == "pong"

            # Disable for guild 100; plugin.name == "pingplugin"
            bot.disable_plugin("pingplugin", 100)

            ctx = await invoke(bot, "ping", guild_id=100)
            assert "disabled" in (ctx.last_response or "").lower()
        finally:
            await bot.close()

    @pytest.mark.asyncio
    async def test_disabled_plugin_does_not_block_other_guilds(self) -> None:
        bot = Bot(auto_sync=False, db_backend="memory")
        try:
            class BanPlugin(Plugin):
                @slash(description="Ban")
                async def ban(self, ctx):
                    await ctx.respond("banned")

            bot.add_plugin(BanPlugin())
            bot.disable_plugin("banplugin", 100)

            # Guild 100 is blocked
            ctx100 = await invoke(bot, "ban", guild_id=100)
            assert "disabled" in (ctx100.last_response or "").lower()

            # Guild 200 is not affected
            ctx200 = await invoke(bot, "ban", guild_id=200)
            assert ctx200.last_response == "banned"
        finally:
            await bot.close()

    @pytest.mark.asyncio
    async def test_enable_restores_dispatch(self) -> None:
        bot = Bot(auto_sync=False, db_backend="memory")
        try:
            class TagPlugin(Plugin):
                @slash(description="Tag")
                async def tag(self, ctx):
                    await ctx.respond("tagged")

            bot.add_plugin(TagPlugin())
            bot.disable_plugin("tagplugin", 100)

            ctx = await invoke(bot, "tag", guild_id=100)
            assert "disabled" in (ctx.last_response or "").lower()

            bot.enable_plugin("tagplugin", 100)

            ctx = await invoke(bot, "tag", guild_id=100)
            assert ctx.last_response == "tagged"
        finally:
            await bot.close()

    @pytest.mark.asyncio
    async def test_dm_invocations_not_blocked(self) -> None:
        bot = Bot(auto_sync=False, db_backend="memory")
        try:
            class HelpPlugin(Plugin):
                @slash(description="Help")
                async def help(self, ctx):
                    await ctx.respond("here to help")

            bot.add_plugin(HelpPlugin())
            bot.disable_plugin("helpplugin", 100)

            # DM invocation (guild_id=None) must not be blocked
            ctx = await invoke(bot, "help", guild_id=None)
            assert ctx.last_response == "here to help"
        finally:
            await bot.close()
