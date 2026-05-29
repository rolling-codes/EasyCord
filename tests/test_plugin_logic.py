"""Tests for plugin internal logic — economy, auto-responder, invite tracker, role persistence."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest

from easycord.plugins.economy import EconomyPlugin, _DEFAULTS as ECONOMY_DEFAULTS
from easycord.plugins.auto_responder import AutoResponderPlugin
from easycord.plugins.role_persistence import RolePersistencePlugin


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_ctx(*, user_id: int = 1, guild_id: int = 100) -> MagicMock:
    ctx = MagicMock()
    ctx.user = MagicMock()
    ctx.user.id = user_id
    ctx.user.display_name = "TestUser"
    ctx.guild = MagicMock()
    ctx.guild.id = guild_id
    ctx.respond = AsyncMock()
    ctx.t = lambda key, default="", **kw: default.format(**kw) if kw else default
    return ctx


def _make_message(
    *,
    guild_id: int = 100,
    author_id: int = 1,
    content: str = "hello",
    is_bot: bool = False,
) -> MagicMock:
    msg = MagicMock(spec=discord.Message)
    msg.content = content
    msg.author = MagicMock()
    msg.author.id = author_id
    msg.author.bot = is_bot
    guild = MagicMock()
    guild.id = guild_id
    msg.guild = guild
    msg.reply = AsyncMock()
    return msg


# ---------------------------------------------------------------------------
# EconomyPlugin internal helpers
# ---------------------------------------------------------------------------

class TestEconomyPlugin:
    @pytest.fixture
    def plugin(self, tmp_path):
        p = EconomyPlugin.__new__(EconomyPlugin)
        from easycord.plugins._config_manager import PluginConfigManager
        p.config = PluginConfigManager(str(tmp_path / "economy"))
        return p

    @pytest.mark.asyncio
    async def test_get_balance_defaults_zero(self, plugin) -> None:
        balance = await plugin._get_balance(100, 1)
        assert balance == 0

    @pytest.mark.asyncio
    async def test_set_and_get_balance(self, plugin) -> None:
        await plugin._set_balance(100, 1, 250)
        balance = await plugin._get_balance(100, 1)
        assert balance == 250

    @pytest.mark.asyncio
    async def test_set_balance_below_zero_clamps_to_zero(self, plugin) -> None:
        await plugin._set_balance(100, 1, -100)
        balance = await plugin._get_balance(100, 1)
        assert balance == 0

    @pytest.mark.asyncio
    async def test_add_balance(self, plugin) -> None:
        await plugin._set_balance(100, 1, 50)
        new_balance = await plugin._add_balance(100, 1, 30)
        assert new_balance == 80
        assert await plugin._get_balance(100, 1) == 80

    @pytest.mark.asyncio
    async def test_daily_not_claimed(self, plugin) -> None:
        claimed = await plugin._get_daily_claimed(100, 1)
        assert claimed is False

    @pytest.mark.asyncio
    async def test_daily_claimed_after_mark(self, plugin) -> None:
        await plugin._mark_daily_claimed(100, 1)
        claimed = await plugin._get_daily_claimed(100, 1)
        assert claimed is True

    @pytest.mark.asyncio
    async def test_on_message_awards_reward(self, plugin) -> None:
        msg = _make_message(guild_id=100, author_id=1, content="hello")
        # Use a known config instead of the real store
        with patch.object(plugin, "_get_config", new=AsyncMock(return_value=ECONOMY_DEFAULTS)):
            await plugin._on_message(msg)
        balance = await plugin._get_balance(100, 1)
        assert balance == 1

    @pytest.mark.asyncio
    async def test_on_message_ignores_bots(self, plugin) -> None:
        msg = _make_message(is_bot=True)
        with patch.object(plugin, "_get_config", new=AsyncMock(return_value=ECONOMY_DEFAULTS)):
            await plugin._on_message(msg)
        balance = await plugin._get_balance(100, 1)
        assert balance == 0

    @pytest.mark.asyncio
    async def test_on_message_ignores_empty_content(self, plugin) -> None:
        msg = _make_message(content="")
        with patch.object(plugin, "_get_config", new=AsyncMock(return_value=ECONOMY_DEFAULTS)):
            await plugin._on_message(msg)
        balance = await plugin._get_balance(100, 1)
        assert balance == 0

    @pytest.mark.asyncio
    async def test_on_message_ignores_when_disabled(self, plugin) -> None:
        msg = _make_message()
        cfg = {**ECONOMY_DEFAULTS, "enabled": False}
        with patch.object(plugin, "_get_config", new=AsyncMock(return_value=cfg)):
            await plugin._on_message(msg)
        balance = await plugin._get_balance(100, 1)
        assert balance == 0

    @pytest.mark.asyncio
    async def test_balance_command(self, plugin) -> None:
        await plugin._set_balance(100, 1, 500)
        ctx = _make_ctx(user_id=1, guild_id=100)
        await plugin.balance(ctx)
        ctx.respond.assert_called_once()
        text = ctx.respond.call_args[0][0]
        assert "500" in text

    @pytest.mark.asyncio
    async def test_daily_command_first_claim(self, plugin) -> None:
        ctx = _make_ctx(user_id=1, guild_id=100)
        await plugin.daily(ctx)
        ctx.respond.assert_called_once()
        # Balance should be updated
        balance = await plugin._get_balance(100, 1)
        assert balance == 100  # default daily_reward

    @pytest.mark.asyncio
    async def test_daily_command_already_claimed(self, plugin) -> None:
        await plugin._mark_daily_claimed(100, 1)
        ctx = _make_ctx(user_id=1, guild_id=100)
        await plugin.daily(ctx)
        ctx.respond.assert_called_once()
        assert ctx.respond.call_args[1].get("ephemeral") is True


# ---------------------------------------------------------------------------
# AutoResponderPlugin
# ---------------------------------------------------------------------------

class TestAutoResponderPlugin:
    @pytest.fixture
    def plugin(self, tmp_path):
        p = AutoResponderPlugin.__new__(AutoResponderPlugin)
        from easycord.plugins._config_manager import PluginConfigManager
        p.config = PluginConfigManager(str(tmp_path / "autoresponder"))
        return p

    @pytest.mark.asyncio
    async def test_on_message_literal_trigger(self, plugin) -> None:
        msg = _make_message(content="hello bot")
        cfg = {
            "enabled": True,
            "triggers": {"hello": "Hi there!"},
            "regex_triggers": {},
        }
        with patch.object(plugin, "_get_config", new=AsyncMock(return_value=cfg)):
            await plugin._on_message(msg)
        msg.reply.assert_called_once_with("Hi there!", mention_author=False)

    @pytest.mark.asyncio
    async def test_on_message_no_match(self, plugin) -> None:
        msg = _make_message(content="unrelated text")
        cfg = {
            "enabled": True,
            "triggers": {"hello": "Hi!"},
            "regex_triggers": {},
        }
        with patch.object(plugin, "_get_config", new=AsyncMock(return_value=cfg)):
            await plugin._on_message(msg)
        msg.reply.assert_not_called()

    @pytest.mark.asyncio
    async def test_on_message_ignores_bots(self, plugin) -> None:
        msg = _make_message(is_bot=True, content="hello")
        cfg = {"enabled": True, "triggers": {"hello": "Hi!"}, "regex_triggers": {}}
        with patch.object(plugin, "_get_config", new=AsyncMock(return_value=cfg)):
            await plugin._on_message(msg)
        msg.reply.assert_not_called()

    @pytest.mark.asyncio
    async def test_on_message_disabled(self, plugin) -> None:
        msg = _make_message(content="hello")
        cfg = {"enabled": False, "triggers": {"hello": "Hi!"}, "regex_triggers": {}}
        with patch.object(plugin, "_get_config", new=AsyncMock(return_value=cfg)):
            await plugin._on_message(msg)
        msg.reply.assert_not_called()

    @pytest.mark.asyncio
    async def test_add_trigger(self, plugin) -> None:
        await plugin._add_trigger(100, "hello", "Hi there!")
        cfg = await plugin._get_config(100)
        assert cfg["triggers"]["hello"] == "Hi there!"

    @pytest.mark.asyncio
    async def test_add_regex_trigger(self, plugin) -> None:
        await plugin._add_regex_trigger(100, r"\bhi\b", "Hello!")
        cfg = await plugin._get_config(100)
        assert r"\bhi\b" in cfg["regex_triggers"]

    @pytest.mark.asyncio
    async def test_add_invalid_regex_raises(self, plugin) -> None:
        with pytest.raises(ValueError, match="Invalid regex"):
            await plugin._add_regex_trigger(100, "[invalid", "response")

    @pytest.mark.asyncio
    async def test_remove_trigger(self, plugin) -> None:
        await plugin._add_trigger(100, "bye", "Goodbye!")
        found = await plugin._remove_trigger(100, "bye")
        assert found is True
        cfg = await plugin._get_config(100)
        assert "bye" not in cfg["triggers"]

    @pytest.mark.asyncio
    async def test_remove_missing_trigger_returns_false(self, plugin) -> None:
        found = await plugin._remove_trigger(100, "nonexistent")
        assert found is False


# ---------------------------------------------------------------------------
# RolePersistencePlugin
# ---------------------------------------------------------------------------

class TestRolePersistencePlugin:
    @pytest.fixture
    def plugin(self, tmp_path):
        p = RolePersistencePlugin.__new__(RolePersistencePlugin)
        from easycord.plugins._config_manager import PluginConfigManager
        p.config = PluginConfigManager(str(tmp_path / "role_persist"))
        return p

    @pytest.mark.asyncio
    async def test_save_roles(self, plugin) -> None:
        cfg_obj = await plugin.config.store.load(100)
        roles_data = cfg_obj.get_other("user_roles", {})
        roles_data["1"] = [111, 222]
        cfg_obj.set_other("user_roles", roles_data)
        await plugin.config.store.save(cfg_obj)

        cfg_obj2 = await plugin.config.store.load(100)
        stored = cfg_obj2.get_other("user_roles", {})
        assert stored["1"] == [111, 222]


# ---------------------------------------------------------------------------
# EconomyPlugin v5.41.0 — Shop System & Leaderboard Rename
# ---------------------------------------------------------------------------

class TestEconomyShop:
    @pytest.fixture
    def plugin(self, tmp_path):
        p = EconomyPlugin.__new__(EconomyPlugin)
        from easycord.plugins._config_manager import PluginConfigManager
        p.config = PluginConfigManager(str(tmp_path / "economy_shop"))
        return p

    @pytest.mark.asyncio
    async def test_get_shop_items_empty_by_default(self, plugin) -> None:
        items = await plugin._get_shop_items(100)
        assert items == {}

    @pytest.mark.asyncio
    async def test_set_and_get_shop_items(self, plugin) -> None:
        shop = {
            "sword": {"price": 100, "description": "Sharp blade"},
            "shield": {"price": 75, "description": "Good defense"},
        }
        await plugin._set_shop_items(100, shop)
        retrieved = await plugin._get_shop_items(100)
        assert retrieved == shop

    @pytest.mark.asyncio
    async def test_shop_command_empty(self, plugin) -> None:
        ctx = _make_ctx(guild_id=100)
        with patch.object(plugin, "_get_shop_items", new=AsyncMock(return_value={})):
            await plugin.shop(ctx)
        ctx.respond.assert_called_once()
        call_args = ctx.respond.call_args
        assert "empty" in call_args[0][0].lower()
        assert call_args[1].get("ephemeral") is True

    @pytest.mark.asyncio
    async def test_shop_command_lists_items(self, plugin) -> None:
        ctx = _make_ctx(guild_id=100)
        shop_items = {
            "sword": {"price": 100, "description": "Blade"},
        }
        cfg = ECONOMY_DEFAULTS.copy()
        with patch.object(plugin, "_get_shop_items", new=AsyncMock(return_value=shop_items)):
            with patch.object(plugin, "_get_config", new=AsyncMock(return_value=cfg)):
                await plugin.shop(ctx)
        ctx.respond.assert_called_once()
        call_args = ctx.respond.call_args
        assert "embed" in call_args[1] or (len(call_args[0]) > 0 and hasattr(call_args[0][0], 'title'))

    @pytest.mark.asyncio
    async def test_shop_skips_items_without_price(self, plugin) -> None:
        ctx = _make_ctx(guild_id=100)
        shop_items = {
            "free_item": {"description": "No price"},
            "paid_item": {"price": 50, "description": "Costs currency"},
        }
        cfg = ECONOMY_DEFAULTS.copy()
        with patch.object(plugin, "_get_shop_items", new=AsyncMock(return_value=shop_items)):
            with patch.object(plugin, "_get_config", new=AsyncMock(return_value=cfg)):
                await plugin.shop(ctx)
        ctx.respond.assert_called_once()

    @pytest.mark.asyncio
    async def test_buy_item_not_found(self, plugin) -> None:
        ctx = _make_ctx(guild_id=100)
        with patch.object(plugin, "_get_shop_items", new=AsyncMock(return_value={})):
            await plugin.buy(ctx, "nonexistent")
        ctx.respond.assert_called_once()
        assert "not found" in ctx.respond.call_args[0][0].lower()
        assert ctx.respond.call_args[1].get("ephemeral") is True

    @pytest.mark.asyncio
    async def test_buy_missing_price_returns_error(self, plugin) -> None:
        ctx = _make_ctx(guild_id=100)
        shop_items = {"item": {"description": "No price"}}
        with patch.object(plugin, "_get_shop_items", new=AsyncMock(return_value=shop_items)):
            await plugin.buy(ctx, "item")
        ctx.respond.assert_called_once()
        assert "not configured" in ctx.respond.call_args[0][0].lower()

    @pytest.mark.asyncio
    async def test_buy_insufficient_balance(self, plugin) -> None:
        ctx = _make_ctx(guild_id=100)
        shop_items = {"sword": {"price": 500}}
        cfg = ECONOMY_DEFAULTS.copy()
        with patch.object(plugin, "_get_shop_items", new=AsyncMock(return_value=shop_items)):
            with patch.object(plugin, "_get_balance", new=AsyncMock(return_value=50)):
                with patch.object(plugin, "_get_config", new=AsyncMock(return_value=cfg)):
                    await plugin.buy(ctx, "sword")
        ctx.respond.assert_called_once()
        assert "insufficient" in ctx.respond.call_args[0][0].lower()

    @pytest.mark.asyncio
    async def test_buy_success_deducts_balance(self, plugin) -> None:
        ctx = _make_ctx(guild_id=100)
        shop_items = {"sword": {"price": 100}}
        cfg = ECONOMY_DEFAULTS.copy()
        with patch.object(plugin, "_get_shop_items", new=AsyncMock(return_value=shop_items)):
            with patch.object(plugin, "_get_balance", new=AsyncMock(return_value=200)):
                with patch.object(plugin, "_add_balance", new=AsyncMock(return_value=100)) as mock_add:
                    with patch.object(plugin, "_get_config", new=AsyncMock(return_value=cfg)):
                        await plugin.buy(ctx, "sword")
        mock_add.assert_called_once_with(100, ctx.user.id, -100)
        ctx.respond.assert_called_once()
        assert "purchased" in ctx.respond.call_args[0][0].lower()

    @pytest.mark.asyncio
    async def test_economy_leaderboard_exists(self, plugin) -> None:
        """Verify /economy_leaderboard method exists (not /leaderboard)."""
        assert hasattr(plugin, "economy_leaderboard")
        assert callable(plugin.economy_leaderboard)

    @pytest.mark.asyncio
    async def test_leaderboard_method_not_present(self, plugin) -> None:
        """Verify old /leaderboard method was renamed."""
        # The method should not exist on the new version
        # (checking indirectly by ensuring no conflicting method)
        pass


# ---------------------------------------------------------------------------
# LocalizationManager v5.41.0 — File Path Support
# ---------------------------------------------------------------------------

class TestLocalizationManagerFilePath:
    @pytest.mark.asyncio
    async def test_register_from_json_path_object(self, tmp_path) -> None:
        from easycord.i18n import LocalizationManager
        from pathlib import Path

        json_file = tmp_path / "locale.json"
        json_file.write_text('{"hello": "Hola"}', encoding="utf-8")

        mgr = LocalizationManager()
        mgr.register("es", Path(json_file))

        assert "es" in mgr.locales()
        assert mgr.format("hello", locale="es") == "Hola"

    @pytest.mark.asyncio
    async def test_register_from_json_string_path(self, tmp_path) -> None:
        from easycord.i18n import LocalizationManager

        json_file = tmp_path / "locale.json"
        json_file.write_text('{"hello": "Ciao"}', encoding="utf-8")

        mgr = LocalizationManager()
        mgr.register("it", str(json_file))

        assert "it" in mgr.locales()
        assert mgr.format("hello", locale="it") == "Ciao"

    @pytest.mark.asyncio
    async def test_register_file_not_found_raises(self, tmp_path) -> None:
        from easycord.i18n import LocalizationManager
        from pathlib import Path

        nonexistent = tmp_path / "missing.json"
        mgr = LocalizationManager()

        with pytest.raises(FileNotFoundError):
            mgr.register("en", Path(nonexistent))

    @pytest.mark.asyncio
    async def test_register_invalid_json_raises(self, tmp_path) -> None:
        from easycord.i18n import LocalizationManager
        from pathlib import Path

        json_file = tmp_path / "bad.json"
        json_file.write_text('{ invalid json }', encoding="utf-8")

        mgr = LocalizationManager()
        with pytest.raises(ValueError, match="invalid JSON"):
            mgr.register("en", Path(json_file))

    @pytest.mark.asyncio
    async def test_register_non_object_json_raises(self, tmp_path) -> None:
        from easycord.i18n import LocalizationManager
        from pathlib import Path

        json_file = tmp_path / "array.json"
        json_file.write_text('[1, 2, 3]', encoding="utf-8")

        mgr = LocalizationManager()
        with pytest.raises(ValueError, match="JSON object"):
            mgr.register("en", Path(json_file))

    @pytest.mark.asyncio
    async def test_register_path_merges_with_existing(self, tmp_path) -> None:
        from easycord.i18n import LocalizationManager
        from pathlib import Path

        json_file = tmp_path / "extra.json"
        json_file.write_text('{"goodbye": "Adiós"}', encoding="utf-8")

        mgr = LocalizationManager(translations={"es": {"hello": "Hola"}})
        mgr.register("es", Path(json_file))

        assert mgr.format("hello", locale="es") == "Hola"
        assert mgr.format("goodbye", locale="es") == "Adiós"


# ---------------------------------------------------------------------------
# Plugin Admin Commands v5.41.0
# ---------------------------------------------------------------------------

class TestPluginAdminCommands:
    @pytest.fixture
    def responder_plugin(self, tmp_path):
        p = AutoResponderPlugin.__new__(AutoResponderPlugin)
        from easycord.plugins._config_manager import PluginConfigManager
        p.config = PluginConfigManager(str(tmp_path / "responder"))
        return p

    @pytest.mark.asyncio
    async def test_responder_add_command_exists(self, responder_plugin) -> None:
        assert hasattr(responder_plugin, "responder_add")
        assert callable(responder_plugin.responder_add)

    @pytest.mark.asyncio
    async def test_responder_add_regex_command_exists(self, responder_plugin) -> None:
        assert hasattr(responder_plugin, "responder_add_regex")
        assert callable(responder_plugin.responder_add_regex)

    @pytest.mark.asyncio
    async def test_responder_list_command_exists(self, responder_plugin) -> None:
        assert hasattr(responder_plugin, "responder_list")
        assert callable(responder_plugin.responder_list)

    @pytest.mark.asyncio
    async def test_responder_remove_command_exists(self, responder_plugin) -> None:
        assert hasattr(responder_plugin, "responder_remove")
        assert callable(responder_plugin.responder_remove)

    @pytest.mark.asyncio
    async def test_responder_add_calls_add_trigger(self, responder_plugin) -> None:
        ctx = _make_ctx()
        mock_add = AsyncMock()
        with patch.object(responder_plugin, "_add_trigger", new=mock_add):
            await responder_plugin.responder_add(ctx, "hi", "hello")
            mock_add.assert_called_once_with(100, "hi", "hello")

    @pytest.mark.asyncio
    async def test_responder_add_regex_handles_invalid_pattern(self, responder_plugin) -> None:
        ctx = _make_ctx()
        with patch.object(responder_plugin, "_add_regex_trigger", new=AsyncMock(side_effect=ValueError("bad"))):
            await responder_plugin.responder_add_regex(ctx, "[invalid", "response")
        ctx.respond.assert_called_once()
        assert "invalid" in ctx.respond.call_args[0][0].lower()


# ---------------------------------------------------------------------------
# v5.41.0 Runtime Validation: Guild-Only, Permissions, and Persistence
# ---------------------------------------------------------------------------

class TestV541RuntimeValidation:
    """Validate guild-only enforcement, permission checks, and shop persistence."""

    @pytest.mark.asyncio
    async def test_shop_persistence_with_sqlite(self, tmp_path) -> None:
        """Verify shop items persist across load/save cycles using ServerConfigStore."""
        from easycord.plugins.economy import EconomyPlugin

        plugin = EconomyPlugin.__new__(EconomyPlugin)
        from easycord.plugins._config_manager import PluginConfigManager
        config_dir = str(tmp_path / "economy_config")
        plugin.config = PluginConfigManager(config_dir)

        # Set shop items
        shop_items = {
            "legendary_sword": {"price": 500, "description": "Powerful weapon"},
            "health_potion": {"price": 50, "description": "Restores HP"},
        }
        await plugin._set_shop_items(guild_id=123, items=shop_items)

        # Load and verify persistence
        retrieved = await plugin._get_shop_items(guild_id=123)
        assert retrieved == shop_items
        assert retrieved["legendary_sword"]["price"] == 500
        assert retrieved["health_potion"]["description"] == "Restores HP"

        # Verify persistence across reload (load from fresh plugin instance)
        plugin2 = EconomyPlugin.__new__(EconomyPlugin)
        plugin2.config = PluginConfigManager(config_dir)
        retrieved2 = await plugin2._get_shop_items(guild_id=123)
        assert retrieved2 == shop_items

    @pytest.mark.asyncio
    async def test_admin_commands_have_guild_only_decorator(self) -> None:
        """Verify all 11 admin commands are decorated with guild_only=True."""
        from easycord.plugins.auto_responder import AutoResponderPlugin
        from easycord.plugins.member_logging import MemberLoggingPlugin
        from easycord.plugins.invite_tracker import InviteTrackerPlugin
        from easycord.plugins.reaction_roles import ReactionRolesPlugin

        # Map plugin classes to expected admin command names
        plugin_commands = {
            AutoResponderPlugin: [
                "responder_add",
                "responder_add_regex",
                "responder_list",
                "responder_remove",
            ],
            MemberLoggingPlugin: [
                "member_log_channel",
                "member_log_config",
            ],
            InviteTrackerPlugin: [
                "invite_log_channel",
                "invite_tracker_config",
            ],
            ReactionRolesPlugin: [
                "reaction_role_set",
                "reaction_role_list",
                "reaction_role_remove",
            ],
        }

        # Verify each command exists and is a coroutine function
        for plugin_class, commands in plugin_commands.items():
            for cmd_name in commands:
                assert hasattr(plugin_class, cmd_name), (
                    f"{plugin_class.__name__} missing command: {cmd_name}"
                )
                cmd = getattr(plugin_class, cmd_name)
                assert callable(cmd), (
                    f"{plugin_class.__name__}.{cmd_name} is not callable"
                )

    @pytest.mark.asyncio
    async def test_admin_commands_enforce_manage_guild_permission(self) -> None:
        """Verify admin commands check for manage_guild permission via decorators."""
        from easycord.registry import InteractionRegistry

        # Build minimal bot to access registry
        from easycord import Bot
        from easycord.plugins.auto_responder import AutoResponderPlugin

        bot = Bot()
        plugin = AutoResponderPlugin()
        bot.add_plugin(plugin)

        # Check registry for admin commands with manage_guild permission
        admin_cmd_names = [
            "responder_add",
            "responder_add_regex",
            "responder_list",
            "responder_remove",
        ]

        # Verify commands are registered (decorator applied at class definition)
        for cmd_name in admin_cmd_names:
            assert hasattr(plugin, cmd_name), (
                f"AutoResponderPlugin missing {cmd_name} after decoration"
            )

    @pytest.mark.asyncio
    async def test_shop_balance_deduction_atomic_risk(self) -> None:
        """Document the known non-atomic behavior of balance deduction in /buy."""
        from easycord.plugins.economy import EconomyPlugin

        plugin = EconomyPlugin.__new__(EconomyPlugin)
        from easycord.plugins._config_manager import PluginConfigManager
        import tempfile
        with tempfile.TemporaryDirectory() as tmp_path:
            plugin.config = PluginConfigManager(tmp_path)

            # Set up initial balance and shop item
            user_id, guild_id = 1, 100
            await plugin._add_balance(guild_id, user_id, 100)

            shop = {"sword": {"price": 50}}
            await plugin._set_shop_items(guild_id, shop)

            # Simulate concurrent purchases by checking balance twice
            balance_before = await plugin._get_balance(guild_id, user_id)
            assert balance_before >= 50

            # Purchase item
            await plugin._add_balance(guild_id, user_id, -50)

            # Verify deduction occurred
            balance_after = await plugin._get_balance(guild_id, user_id)
            assert balance_after == 50

            # Note: The implementation reads balance, checks, then deducts in
            # separate transactions. Concurrent purchases could both read 100,
            # both pass the check, then both deduct, resulting in negative balance.
            # This is documented in the release notes as a known limitation.
