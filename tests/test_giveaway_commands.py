"""Tests for GiveawayPlugin — pure helpers and command flows."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from easycord.plugins.giveaway import (
    GiveawayPlugin,
    _build_embed,
    _parse_duration,
    _pick_winners,
)


def _plugin(tmp_path) -> GiveawayPlugin:
    p = GiveawayPlugin.__new__(GiveawayPlugin)
    GiveawayPlugin.__init__(p, store_path=str(tmp_path / "giveaway"))
    p._bot = MagicMock()
    return p


def _ctx(guild_id: int = 100) -> MagicMock:
    ctx = MagicMock()
    ctx.guild = MagicMock()
    ctx.guild.id = guild_id
    ctx.respond = AsyncMock()
    ctx.channel = MagicMock()
    ctx.channel.id = 55
    return ctx


def _ended_giveaway(entries: list[int] | None = None) -> dict:
    return {
        "channel_id": 55,
        "prize": "Test prize",
        "end_time": "2024-01-01T00:00:00+00:00",
        "winner_count": 1,
        "entries": entries or [],
        "status": "ended",
        "winners": [],
    }


# ---------------------------------------------------------------------------
# Pure function tests
# ---------------------------------------------------------------------------

class TestParseDuration:
    def test_seconds(self):
        assert _parse_duration("30s") == 30

    def test_minutes(self):
        assert _parse_duration("5m") == 300

    def test_hours(self):
        assert _parse_duration("2h") == 7200

    def test_days(self):
        assert _parse_duration("1d") == 86400

    def test_invalid_raises(self):
        with pytest.raises(ValueError, match="Invalid duration"):
            _parse_duration("forever")


class TestPickWinners:
    def test_empty_entries_returns_empty(self):
        assert _pick_winners([], 3) == []

    def test_fewer_entries_than_count_returns_all(self):
        winners = _pick_winners([1, 2], 5)
        assert set(winners) == {1, 2}

    def test_winners_are_unique(self):
        entries = list(range(50))
        winners = _pick_winners(entries, 10)
        assert len(winners) == len(set(winners))

    def test_count_respected(self):
        entries = list(range(100))
        assert len(_pick_winners(entries, 5)) == 5


class TestBuildEmbed:
    def test_active_embed_has_footer(self):
        embed = _build_embed("Nitro", 9_999_999, 2, 5, ended=False)
        assert embed.title is not None
        assert "GIVEAWAY" in embed.title
        assert embed.description is not None
        assert "Nitro" in embed.description
        assert embed.footer is not None

    def test_ended_embed_no_footer_text(self):
        embed = _build_embed("Steam key", 9_999_999, 1, 3, ended=True)
        assert embed.description is not None
        assert "Ended" in embed.description
        assert embed.footer.text is None

    def test_entry_count_in_description(self):
        embed = _build_embed("Prize", 9_999_999, 1, 42, ended=False)
        assert embed.description is not None
        assert "42" in embed.description


# ---------------------------------------------------------------------------
# Command flow tests
# ---------------------------------------------------------------------------

class TestGiveawayCommand:
    async def test_invalid_duration_rejected(self, tmp_path):
        p = _plugin(tmp_path)
        ctx = _ctx()

        await p.giveaway(ctx, "Prize", "not-valid", 1)

        ctx.respond.assert_called_once()
        _, kwargs = ctx.respond.call_args
        assert kwargs.get("ephemeral") is True

    async def test_zero_winners_rejected(self, tmp_path):
        p = _plugin(tmp_path)
        ctx = _ctx()

        await p.giveaway(ctx, "Prize", "1h", 0)

        ctx.respond.assert_called_once()
        _, kwargs = ctx.respond.call_args
        assert kwargs.get("ephemeral") is True

    async def test_no_guild_returns_early(self, tmp_path):
        p = _plugin(tmp_path)
        ctx = _ctx()
        ctx.guild = None

        await p.giveaway(ctx, "Prize", "1h", 1)

        ctx.respond.assert_not_called()


class TestGiveawayEnd:
    async def test_invalid_message_id_rejected(self, tmp_path):
        p = _plugin(tmp_path)
        ctx = _ctx()

        await p.giveaway_end(ctx, "not-a-number")

        ctx.respond.assert_called_once()
        _, kwargs = ctx.respond.call_args
        assert kwargs.get("ephemeral") is True

    async def test_no_active_giveaway_rejected(self, tmp_path):
        p = _plugin(tmp_path)
        ctx = _ctx(guild_id=100)

        await p.giveaway_end(ctx, "12345")

        ctx.respond.assert_called_once()
        _, kwargs = ctx.respond.call_args
        assert kwargs.get("ephemeral") is True

    async def test_no_guild_returns_early(self, tmp_path):
        p = _plugin(tmp_path)
        ctx = _ctx()
        ctx.guild = None

        await p.giveaway_end(ctx, "12345")

        ctx.respond.assert_not_called()


class TestGiveawayReroll:
    async def test_invalid_message_id_rejected(self, tmp_path):
        p = _plugin(tmp_path)
        ctx = _ctx()

        await p.giveaway_reroll(ctx, "bad")

        ctx.respond.assert_called_once()
        _, kwargs = ctx.respond.call_args
        assert kwargs.get("ephemeral") is True

    async def test_no_ended_giveaway_rejected(self, tmp_path):
        p = _plugin(tmp_path)
        ctx = _ctx(guild_id=100)

        await p.giveaway_reroll(ctx, "99999")

        ctx.respond.assert_called_once()
        _, kwargs = ctx.respond.call_args
        assert kwargs.get("ephemeral") is True

    async def test_no_entries_responds_ephemeral(self, tmp_path):
        p = _plugin(tmp_path)
        ctx = _ctx(guild_id=100)

        async with p._guild_lock(100):
            cfg = await p._store.load(100)
            cfg.set_other("giveaways", {"42": _ended_giveaway(entries=[])})
            await p._store.save(cfg)

        await p.giveaway_reroll(ctx, "42")

        ctx.respond.assert_called_once()
        _, kwargs = ctx.respond.call_args
        assert kwargs.get("ephemeral") is True

    async def test_with_entries_picks_new_winners(self, tmp_path):
        p = _plugin(tmp_path)
        ctx = _ctx(guild_id=100)

        async with p._guild_lock(100):
            cfg = await p._store.load(100)
            cfg.set_other("giveaways", {"77": _ended_giveaway(entries=[1001, 1002, 1003])})
            await p._store.save(cfg)

        await p.giveaway_reroll(ctx, "77")

        ctx.respond.assert_called_once()
        args, _ = ctx.respond.call_args
        assert "🎉" in (args[0] if args else "")
