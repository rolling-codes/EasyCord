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
# EconomyPlugin concurrency — balance mutations must not lose updates
#
# ServerConfigStore.load/save are async; callers must stay correct when those
# awaits actually suspend (any async backend: aiofiles, DB, executor). Today's
# store happens to do synchronous file I/O, which masks the read-modify-write
# race in economy. The fixture wraps load/save with a single cooperative yield
# to exercise the async contract the way a real async backend would.
# ---------------------------------------------------------------------------

class TestEconomyConcurrency:
    @pytest.fixture
    def plugin(self, tmp_path):
        import asyncio
        p = EconomyPlugin.__new__(EconomyPlugin)
        from easycord.plugins._config_manager import PluginConfigManager
        p.config = PluginConfigManager(str(tmp_path / "economy"))

        # Simulate an async store backend: each load/save yields to the loop.
        orig_load, orig_save = p.config.store.load, p.config.store.save

        async def yielding_load(guild_id):
            await asyncio.sleep(0)
            return await orig_load(guild_id)

        async def yielding_save(cfg):
            await asyncio.sleep(0)
            return await orig_save(cfg)

        p.config.store.load = yielding_load
        p.config.store.save = yielding_save
        return p

    @pytest.mark.asyncio
    async def test_concurrent_add_balance_loses_no_increments(self, plugin) -> None:
        """N concurrent +1 rewards must end at exactly N (no lost updates)."""
        import asyncio
        n = 25
        await asyncio.gather(*(plugin._add_balance(100, 1, 1) for _ in range(n)))
        assert await plugin._get_balance(100, 1) == n

    @pytest.mark.asyncio
    async def test_concurrent_adds_multiple_users_same_guild(self, plugin) -> None:
        """Concurrent rewards for different users in one guild must all persist."""
        import asyncio
        n = 10
        await asyncio.gather(
            *(plugin._add_balance(100, 1, 1) for _ in range(n)),
            *(plugin._add_balance(100, 2, 1) for _ in range(n)),
        )
        assert await plugin._get_balance(100, 1) == n
        assert await plugin._get_balance(100, 2) == n

    @pytest.mark.asyncio
    async def test_concurrent_transfers_conserve_total(self, plugin) -> None:
        """Concurrent transfers must conserve the total currency supply."""
        import asyncio
        await plugin._set_balance(100, 1, 50)
        await plugin._set_balance(100, 2, 50)

        ctx1 = _make_ctx(user_id=1, guild_id=100)
        ctx2 = _make_ctx(user_id=2, guild_id=100)
        user2 = MagicMock()
        user2.id = 2
        user1 = MagicMock()
        user1.id = 1

        await asyncio.gather(
            *(plugin.transfer(ctx1, user2, 5) for _ in range(5)),
            *(plugin.transfer(ctx2, user1, 5) for _ in range(5)),
        )

        b1 = await plugin._get_balance(100, 1)
        b2 = await plugin._get_balance(100, 2)
        assert b1 + b2 == 100, f"currency not conserved: {b1} + {b2} != 100"

    @pytest.mark.asyncio
    async def test_transfer_cannot_overdraw_concurrently(self, plugin) -> None:
        """Two concurrent transfers of the full balance must not both succeed."""
        import asyncio
        await plugin._set_balance(100, 1, 10)

        ctx = _make_ctx(user_id=1, guild_id=100)
        recipient = MagicMock()
        recipient.id = 2

        await asyncio.gather(
            plugin.transfer(ctx, recipient, 10),
            plugin.transfer(ctx, recipient, 10),
        )

        b1 = await plugin._get_balance(100, 1)
        b2 = await plugin._get_balance(100, 2)
        assert b1 + b2 == 10, f"overdraw created currency: {b1} + {b2} != 10"


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
