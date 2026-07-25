"""Tests for ServerStatsPlugin: pure functions, store layer, and command flow."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock

import discord

from easycord.plugins.server_stats import (
    ServerStatsPlugin,
    _online_count,
    _stat_name,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_channel(name: str, channel_id: int | None = None) -> MagicMock:
    ch = MagicMock()
    ch.id = channel_id if channel_id is not None else id(name)
    ch.name = name
    ch.delete = AsyncMock()
    ch.edit = AsyncMock()
    return ch


def _ctx(guild_id: int = 100, is_admin: bool = True) -> MagicMock:
    ctx = MagicMock()
    ctx.guild = MagicMock()
    ctx.guild.id = guild_id
    ctx.guild.member_count = 10
    ctx.guild.premium_subscription_count = 0
    ctx.guild.members = []
    ctx.guild.create_voice_channel = AsyncMock(
        side_effect=lambda name, **kw: _mock_channel(name)
    )
    ctx.guild.get_channel = MagicMock(return_value=None)
    ctx.respond = AsyncMock()
    ctx.is_admin = is_admin
    return ctx


def _plugin(tmp_path) -> ServerStatsPlugin:
    p = ServerStatsPlugin.__new__(ServerStatsPlugin)
    ServerStatsPlugin.__init__(p, store_path=str(tmp_path / "server_stats"))
    return p


def _member(status: discord.Status, is_bot: bool = False) -> MagicMock:
    m = MagicMock(spec=discord.Member)
    m.status = status
    m.bot = is_bot
    return m


# ---------------------------------------------------------------------------
# Layer 1: pure functions
# ---------------------------------------------------------------------------

class TestStatName:
    def test_stat_name_format(self) -> None:
        assert _stat_name("📊 Members", 42) == "📊 Members: 42"

    def test_stat_name_zero(self) -> None:
        assert _stat_name("📊 Members", 0) == "📊 Members: 0"

    def test_stat_name_large_number(self) -> None:
        assert _stat_name("🟢 Online", 9999) == "🟢 Online: 9999"

    def test_stat_name_boosts(self) -> None:
        assert _stat_name("💎 Boosts", 3) == "💎 Boosts: 3"


class TestOnlineCount:
    def test_online_count_excludes_offline(self) -> None:
        guild = MagicMock(spec=discord.Guild)
        guild.members = [
            _member(discord.Status.online),
            _member(discord.Status.offline),
            _member(discord.Status.idle),
            _member(discord.Status.dnd),
        ]
        assert _online_count(guild) == 3

    def test_online_count_excludes_bots(self) -> None:
        guild = MagicMock(spec=discord.Guild)
        guild.members = [
            _member(discord.Status.online),
            _member(discord.Status.online, is_bot=True),
            _member(discord.Status.idle, is_bot=True),
        ]
        assert _online_count(guild) == 1

    def test_online_count_all_offline(self) -> None:
        guild = MagicMock(spec=discord.Guild)
        guild.members = [
            _member(discord.Status.offline),
            _member(discord.Status.offline),
        ]
        assert _online_count(guild) == 0

    def test_online_count_empty_guild(self) -> None:
        guild = MagicMock(spec=discord.Guild)
        guild.members = []
        assert _online_count(guild) == 0

    def test_online_count_bots_excluded_even_if_online(self) -> None:
        guild = MagicMock(spec=discord.Guild)
        guild.members = [
            _member(discord.Status.online, is_bot=True),
            _member(discord.Status.dnd, is_bot=True),
        ]
        assert _online_count(guild) == 0


# ---------------------------------------------------------------------------
# Layer 2: store / tmp_path
# ---------------------------------------------------------------------------

class TestServerStatsStore:
    @pytest.mark.asyncio
    async def test_stores_channel_ids(self, tmp_path) -> None:
        plugin = _plugin(tmp_path)
        guild_id = 200

        async with plugin._locks.lock(guild_id):
            cfg = await plugin._store.load(guild_id)
            cfg.set_other(
                "server_stats",
                {"member_channel_id": 1, "online_channel_id": 2, "boost_channel_id": 3},
            )
            await plugin._store.save(cfg)

        reloaded = await plugin._store.load(guild_id)
        data = reloaded.get_other("server_stats", {})
        assert data["member_channel_id"] == 1
        assert data["online_channel_id"] == 2
        assert data["boost_channel_id"] == 3

    @pytest.mark.asyncio
    async def test_teardown_removes_config(self, tmp_path) -> None:
        plugin = _plugin(tmp_path)
        guild_id = 201

        async with plugin._locks.lock(guild_id):
            cfg = await plugin._store.load(guild_id)
            cfg.set_other(
                "server_stats",
                {"member_channel_id": 10, "online_channel_id": 20, "boost_channel_id": 30},
            )
            await plugin._store.save(cfg)

        # Remove config
        async with plugin._locks.lock(guild_id):
            cfg = await plugin._store.load(guild_id)
            cfg.remove_other("server_stats")
            await plugin._store.save(cfg)

        reloaded = await plugin._store.load(guild_id)
        assert reloaded.get_other("server_stats", {}) == {}

    @pytest.mark.asyncio
    async def test_guild_isolation(self, tmp_path) -> None:
        plugin = _plugin(tmp_path)

        async with plugin._locks.lock(1):
            cfg1 = await plugin._store.load(1)
            cfg1.set_other("server_stats", {"member_channel_id": 99})
            await plugin._store.save(cfg1)

        cfg2 = await plugin._store.load(2)
        assert cfg2.get_other("server_stats", {}) == {}


# ---------------------------------------------------------------------------
# Layer 3: command flow
# ---------------------------------------------------------------------------

class TestStatsSetupCommand:
    @pytest.mark.asyncio
    async def test_setup_requires_admin(self, tmp_path) -> None:
        plugin = _plugin(tmp_path)
        ctx = _ctx(is_admin=False)

        await plugin.stats_setup(ctx)

        ctx.respond.assert_called_once()
        call_args = ctx.respond.call_args
        assert call_args.kwargs.get("ephemeral", False)
        text = call_args.args[0] if call_args.args else ""
        assert "Administrator" in text or "permission" in text.lower()

    @pytest.mark.asyncio
    async def test_setup_requires_guild(self, tmp_path) -> None:
        plugin = _plugin(tmp_path)
        ctx = _ctx()
        ctx.guild = None

        await plugin.stats_setup(ctx)

        ctx.respond.assert_called_once()
        call_args = ctx.respond.call_args
        assert call_args.kwargs.get("ephemeral", False)

    @pytest.mark.asyncio
    async def test_teardown_no_config_responds_error(self, tmp_path) -> None:
        plugin = _plugin(tmp_path)
        ctx = _ctx(guild_id=100)

        await plugin.stats_teardown(ctx)

        ctx.respond.assert_called_once()
        call_args = ctx.respond.call_args
        assert call_args.kwargs.get("ephemeral", False)
        text = call_args.args[0] if call_args.args else ""
        assert "not configured" in text.lower() or "setup" in text.lower()

    @pytest.mark.asyncio
    async def test_setup_creates_channels(self, tmp_path) -> None:
        import asyncio
        plugin = _plugin(tmp_path)
        guild_id = 100
        ctx = _ctx(guild_id=guild_id)

        # Track channels created by name so we can return stable IDs
        _id_counter = iter(range(1001, 1010))
        created_channels: list[MagicMock] = []

        async def _create(name: str, **kw) -> MagicMock:
            ch = _mock_channel(name, next(_id_counter))
            created_channels.append(ch)
            return ch

        ctx.guild.create_voice_channel = AsyncMock(side_effect=_create)

        # Inject a bot mock so _start_loop works; mock get_guild to return the ctx guild
        plugin._bot = MagicMock()
        plugin._bot.get_guild = MagicMock(return_value=None)  # return None so refresh is a no-op

        await plugin.stats_setup(ctx)

        # Cancel the background loop so it doesn't interfere with test teardown
        task = plugin._loops.get(guild_id)
        if task:
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass  # task is being torn down for test cleanup; outcome is irrelevant

        # Three channels should have been created
        assert ctx.guild.create_voice_channel.call_count == 3
        names = [ch.name for ch in created_channels]
        assert any("Members" in n for n in names)
        assert any("Online" in n for n in names)
        assert any("Boosts" in n for n in names)

        # IDs should be persisted
        cfg = await plugin._store.load(guild_id)
        data = cfg.get_other("server_stats", {})
        assert data["member_channel_id"] == created_channels[0].id
        assert data["online_channel_id"] == created_channels[1].id
        assert data["boost_channel_id"] == created_channels[2].id

    @pytest.mark.asyncio
    async def test_teardown_cancels_task_and_clears_config(self, tmp_path) -> None:
        plugin = _plugin(tmp_path)
        guild_id = 100
        ctx = _ctx(guild_id=guild_id)

        # Pre-configure stats
        async with plugin._locks.lock(guild_id):
            cfg = await plugin._store.load(guild_id)
            cfg.set_other(
                "server_stats",
                {"member_channel_id": 10, "online_channel_id": 20, "boost_channel_id": 30},
            )
            await plugin._store.save(cfg)

        # Pre-seed a mock task in _loops
        mock_task = MagicMock()
        mock_task.cancel = MagicMock()
        plugin._loops[guild_id] = mock_task

        # guild.get_channel returns None (channels already deleted externally)
        ctx.guild.get_channel = MagicMock(return_value=None)

        await plugin.stats_teardown(ctx)

        mock_task.cancel.assert_called_once()
        assert guild_id not in plugin._loops

        reloaded = await plugin._store.load(guild_id)
        assert reloaded.get_other("server_stats", {}) == {}

    @pytest.mark.asyncio
    async def test_teardown_deletes_channels(self, tmp_path) -> None:
        plugin = _plugin(tmp_path)
        guild_id = 100
        ctx = _ctx(guild_id=guild_id)

        ch1 = _mock_channel("📊 Members: 5", 10)
        ch2 = _mock_channel("🟢 Online: 3", 20)
        ch3 = _mock_channel("💎 Boosts: 0", 30)

        async with plugin._locks.lock(guild_id):
            cfg = await plugin._store.load(guild_id)
            cfg.set_other(
                "server_stats",
                {"member_channel_id": 10, "online_channel_id": 20, "boost_channel_id": 30},
            )
            await plugin._store.save(cfg)

        channel_map = {10: ch1, 20: ch2, 30: ch3}
        ctx.guild.get_channel = MagicMock(side_effect=lambda cid: channel_map.get(cid))

        await plugin.stats_teardown(ctx)

        ch1.delete.assert_called_once()
        ch2.delete.assert_called_once()
        ch3.delete.assert_called_once()
