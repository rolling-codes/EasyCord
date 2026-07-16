"""Tests for LevelsPlugin."""
from __future__ import annotations

import time
from collections import defaultdict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from easycord.plugins._levels_data import LevelsStore
from easycord.plugins.levels import LevelsPlugin


def _make_plugin(tmp_path) -> LevelsPlugin:
    p = LevelsPlugin.__new__(LevelsPlugin)
    p._store = LevelsStore(str(tmp_path / "levels"))
    p._xp_per_message = 10
    p._cooldown = 60.0
    p._announce = True
    p._cooldowns = defaultdict(dict)
    p._lb_cache = {}
    p._cfg_cache = {}
    return p


def _make_message(guild_id: int = 100, user_id: int = 1, content: str = "hello"):
    msg = MagicMock()
    msg.guild = MagicMock()
    msg.guild.id = guild_id
    msg.guild.name = "Test Guild"
    msg.author = MagicMock()
    msg.author.id = user_id
    msg.author.bot = False
    msg.author.mention = f"<@{user_id}>"
    msg.content = content
    msg.channel = MagicMock()
    msg.channel.send = AsyncMock()
    return msg


def _make_ctx(guild_id: int = 100, user_id: int = 1):
    ctx = MagicMock()
    ctx.guild = MagicMock()
    ctx.guild.id = guild_id
    ctx.guild.name = "Test Guild"
    ctx.guild.get_member = MagicMock(return_value=None)
    ctx.user = MagicMock()
    ctx.user.id = user_id
    ctx.respond = AsyncMock()
    ctx.t = lambda key, default="", **kwargs: default.format(**kwargs)
    return ctx


# ---------------------------------------------------------------------------
# XP award + cooldown
# ---------------------------------------------------------------------------

class TestXPAward:
    @pytest.fixture
    def plugin(self, tmp_path):
        return _make_plugin(tmp_path)

    @pytest.mark.asyncio
    async def test_cooldown_prevents_double_award(self, plugin) -> None:
        msg = _make_message()
        await plugin._award_xp(msg)
        xp_after_first = plugin._store.get_entry(100, 1)["xp"]

        await plugin._award_xp(msg)  # within cooldown window
        xp_after_second = plugin._store.get_entry(100, 1)["xp"]

        assert xp_after_first == 10
        assert xp_after_second == 10  # unchanged

    @pytest.mark.asyncio
    async def test_xp_awarded_after_cooldown_expires(self, plugin) -> None:
        plugin._cooldown = 0.0
        msg = _make_message()
        await plugin._award_xp(msg)
        await plugin._award_xp(msg)
        assert plugin._store.get_entry(100, 1)["xp"] == 20

    @pytest.mark.asyncio
    async def test_bot_messages_ignored(self, plugin) -> None:
        msg = _make_message()
        msg.author.bot = True
        await plugin._award_xp(msg)
        assert plugin._store.get_entry(100, 1)["xp"] == 0


# ---------------------------------------------------------------------------
# XP multiplier
# ---------------------------------------------------------------------------

class TestXPMultiplier:
    @pytest.fixture
    def plugin(self, tmp_path):
        p = _make_plugin(tmp_path)
        p._cooldown = 0.0
        return p

    @pytest.mark.asyncio
    async def test_active_multiplier_scales_xp(self, plugin) -> None:
        plugin._cfg_cache[100] = (
            {"xp_multiplier": 2.0, "xp_multiplier_expires": time.time() + 3600},
            time.monotonic(),
        )
        msg = _make_message()
        await plugin._award_xp(msg)
        assert plugin._store.get_entry(100, 1)["xp"] == 20  # 10 × 2

    @pytest.mark.asyncio
    async def test_expired_multiplier_is_ignored(self, plugin) -> None:
        plugin._cfg_cache[100] = (
            {"xp_multiplier": 5.0, "xp_multiplier_expires": time.time() - 1},
            time.monotonic(),
        )
        msg = _make_message()
        await plugin._award_xp(msg)
        assert plugin._store.get_entry(100, 1)["xp"] == 10  # 10 × 1 (expired)

    @pytest.mark.asyncio
    async def test_set_xp_multiplier_command_persists(self, plugin) -> None:
        ctx = _make_ctx()
        await plugin.set_xp_multiplier(ctx, 3.0, 30)
        ctx.respond.assert_called_once()
        config = plugin._store.read_config(100)
        assert config["xp_multiplier"] == 3.0
        assert config["xp_multiplier_expires"] > time.time()


# ---------------------------------------------------------------------------
# Leaderboard cache
# ---------------------------------------------------------------------------

class TestLeaderboardCache:
    @pytest.fixture
    def plugin(self, tmp_path):
        return _make_plugin(tmp_path)

    @pytest.mark.asyncio
    async def test_first_call_hits_store(self, plugin) -> None:
        await plugin._store.add_xp(100, 1, 50)
        ctx = _make_ctx()
        with patch.object(plugin._store, "read_xp", wraps=plugin._store.read_xp) as spy:
            await plugin.leaderboard(ctx)
            spy.assert_called_once_with(100)

    @pytest.mark.asyncio
    async def test_second_call_within_ttl_uses_cache(self, plugin) -> None:
        await plugin._store.add_xp(100, 1, 50)
        ctx = _make_ctx()
        await plugin.leaderboard(ctx)  # populates cache
        with patch.object(plugin._store, "read_xp", wraps=plugin._store.read_xp) as spy:
            await plugin.leaderboard(ctx)  # should hit cache
            spy.assert_not_called()

    @pytest.mark.asyncio
    async def test_cache_expires_after_ttl(self, plugin) -> None:
        await plugin._store.add_xp(100, 1, 50)
        ctx = _make_ctx()
        # Plant a cache entry that is already expired.
        plugin._lb_cache[100] = ({"1": {"xp": 50, "level": 1}}, time.monotonic() - 9999)
        with patch.object(plugin._store, "read_xp", wraps=plugin._store.read_xp) as spy:
            await plugin.leaderboard(ctx)
            spy.assert_called_once()  # expired → re-fetched


# ---------------------------------------------------------------------------
# Bulk XP reset
# ---------------------------------------------------------------------------

class TestBulkReset:
    @pytest.fixture
    def plugin(self, tmp_path):
        return _make_plugin(tmp_path)

    @pytest.mark.asyncio
    async def test_reset_zeroes_xp(self, plugin) -> None:
        await plugin._store.add_xp(100, 1, 500)
        assert plugin._store.get_entry(100, 1)["xp"] == 500

        ctx = _make_ctx()
        member = MagicMock()
        member.id = 1
        member.mention = "<@1>"
        await plugin.reset_xp(ctx, member)

        assert plugin._store.get_entry(100, 1)["xp"] == 0

    @pytest.mark.asyncio
    async def test_reset_invalidates_lb_cache(self, plugin) -> None:
        plugin._lb_cache[100] = ({"1": {"xp": 500, "level": 5}}, time.monotonic())
        ctx = _make_ctx()
        member = MagicMock()
        member.id = 1
        member.mention = "<@1>"
        await plugin.reset_xp(ctx, member)

        assert 100 not in plugin._lb_cache

    @pytest.mark.asyncio
    async def test_reset_noop_for_user_with_no_xp(self, plugin) -> None:
        ctx = _make_ctx()
        member = MagicMock()
        member.id = 999
        member.mention = "<@999>"
        await plugin.reset_xp(ctx, member)  # should not raise
        ctx.respond.assert_called_once()


# ---------------------------------------------------------------------------
# Level-up DM
# ---------------------------------------------------------------------------

class TestLevelUpDM:
    @pytest.fixture
    def plugin(self, tmp_path):
        p = _make_plugin(tmp_path)
        p._cooldown = 0.0
        p._xp_per_message = 100  # xp_for_level(1) == 100, so one message = level up
        return p

    @pytest.mark.asyncio
    async def test_dm_sent_when_enabled(self, plugin) -> None:
        plugin._cfg_cache[100] = ({"level_dm_enabled": True}, time.monotonic())
        msg = _make_message()
        msg.author.send = AsyncMock()

        await plugin._award_xp(msg)

        msg.author.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_dm_not_sent_when_disabled(self, plugin) -> None:
        plugin._cfg_cache[100] = ({"level_dm_enabled": False}, time.monotonic())
        msg = _make_message()
        msg.author.send = AsyncMock()

        await plugin._award_xp(msg)

        msg.author.send.assert_not_called()

    @pytest.mark.asyncio
    async def test_dm_not_sent_by_default(self, plugin) -> None:
        msg = _make_message()
        msg.author.send = AsyncMock()

        await plugin._award_xp(msg)

        msg.author.send.assert_not_called()

    @pytest.mark.asyncio
    async def test_dm_failure_does_not_crash(self, plugin) -> None:
        plugin._cfg_cache[100] = ({"level_dm_enabled": True}, time.monotonic())
        msg = _make_message()
        import discord
        msg.author.send = AsyncMock(side_effect=discord.Forbidden(MagicMock(), "DMs blocked"))

        # Should log a warning but not raise
        await plugin._award_xp(msg)
        msg.channel.send.assert_called_once()  # channel announcement still sent
