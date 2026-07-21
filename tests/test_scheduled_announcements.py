"""Tests for ScheduledAnnouncementsPlugin: pure functions, store, and command flow."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from easycord.plugins.scheduled_announcements import (
    ScheduledAnnouncementsPlugin,
    _announcement_embed,
    _next_fire,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ctx(guild_id: int = 100, user_id: int = 1) -> MagicMock:
    ctx = MagicMock()
    ctx.guild = MagicMock()
    ctx.guild.id = guild_id
    ctx.user = MagicMock()
    ctx.user.id = user_id
    ctx.respond = AsyncMock()
    ctx.is_admin = True
    ctx.member = MagicMock()
    return ctx


def _plugin(tmp_path) -> ScheduledAnnouncementsPlugin:
    p = ScheduledAnnouncementsPlugin.__new__(ScheduledAnnouncementsPlugin)
    ScheduledAnnouncementsPlugin.__init__(
        p, store_path=str(tmp_path / "announcements")
    )
    return p


def _sample_ann(
    ann_id: int = 1,
    channel_id: int = 999,
    interval: int = 3600,
    message: str = "Hello world",
) -> dict:
    now = datetime.now(timezone.utc)
    return {
        "id": ann_id,
        "channel_id": channel_id,
        "interval_seconds": interval,
        "message": message,
        "next_fire": _next_fire(now, interval).isoformat(),
        "active": True,
    }


# ---------------------------------------------------------------------------
# Layer 1: pure functions
# ---------------------------------------------------------------------------

class TestNextFire:
    def test_next_fire_adds_interval(self) -> None:
        now = datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        result = _next_fire(now, 3600)
        assert result == datetime(2026, 6, 15, 13, 0, 0, tzinfo=timezone.utc)

    def test_next_fire_zero_interval(self) -> None:
        now = datetime(2026, 6, 15, 0, 0, 0, tzinfo=timezone.utc)
        assert _next_fire(now, 0) == now

    def test_next_fire_returns_datetime(self) -> None:
        now = datetime.now(timezone.utc)
        result = _next_fire(now, 60)
        assert isinstance(result, datetime)


class TestAnnouncementEmbed:
    def _ann(self) -> dict:
        return _sample_ann(ann_id=5, channel_id=123, interval=1800, message="Test msg")

    def test_announcement_embed_contains_message(self) -> None:
        ann = self._ann()
        embed = _announcement_embed(ann)
        assert embed.description is not None
        assert "Test msg" in embed.description

    def test_announcement_embed_shows_id(self) -> None:
        ann = self._ann()
        embed = _announcement_embed(ann)
        assert embed.title is not None
        assert "5" in embed.title

    def test_announcement_embed_is_embed(self) -> None:
        embed = _announcement_embed(self._ann())
        assert isinstance(embed, discord.Embed)

    def test_announcement_embed_has_fields(self) -> None:
        embed = _announcement_embed(self._ann())
        assert len(embed.fields) >= 1


class TestParseDurationImport:
    def test_parse_duration_import(self) -> None:
        from easycord.plugins.scheduled_announcements import _parse_duration as pd
        assert pd("1h") == 3600

    def test_parse_duration_minutes(self) -> None:
        from easycord.plugins.scheduled_announcements import _parse_duration as pd
        assert pd("30m") == 1800

    def test_parse_duration_invalid_raises(self) -> None:
        from easycord.plugins.scheduled_announcements import _parse_duration as pd
        with pytest.raises(ValueError):
            pd("bad")


# ---------------------------------------------------------------------------
# Layer 2: store persistence
# ---------------------------------------------------------------------------

class TestStorePersistence:
    async def test_add_announcement_persists(self, tmp_path) -> None:
        p = _plugin(tmp_path)
        ctx = _ctx()
        channel = MagicMock()
        channel.id = 555
        channel.mention = "<#555>"

        await p.announcement_add(ctx, channel, "1h", "Check #rules!")

        from easycord.server_config import ServerConfigStore
        store = ServerConfigStore(str(tmp_path / "announcements"))
        cfg = await store.load(100)
        data = cfg.get_other("announcements", {})
        items = data.get("items", [])
        assert len(items) == 1
        assert items[0]["message"] == "Check #rules!"
        assert items[0]["channel_id"] == 555
        assert items[0]["interval_seconds"] == 3600

    async def test_remove_announcement(self, tmp_path) -> None:
        p = _plugin(tmp_path)
        ctx = _ctx()
        channel = MagicMock()
        channel.id = 555
        channel.mention = "<#555>"

        await p.announcement_add(ctx, channel, "1h", "First")
        await p.announcement_add(ctx, channel, "2h", "Second")

        remove_ctx = _ctx()
        await p.announcement_remove(remove_ctx, 1)

        from easycord.server_config import ServerConfigStore
        store = ServerConfigStore(str(tmp_path / "announcements"))
        cfg = await store.load(100)
        data = cfg.get_other("announcements", {})
        items = data.get("items", [])
        assert len(items) == 1
        assert items[0]["message"] == "Second"

    async def test_list_announcements(self, tmp_path) -> None:
        p = _plugin(tmp_path)
        ctx = _ctx()
        channel = MagicMock()
        channel.id = 555
        channel.mention = "<#555>"

        await p.announcement_add(ctx, channel, "1h", "Alpha")
        await p.announcement_add(ctx, channel, "2h", "Beta")

        list_ctx = _ctx()
        await p.announcement_list(list_ctx)

        list_ctx.respond.assert_awaited_once()
        call_kwargs = list_ctx.respond.call_args
        embeds = call_kwargs.kwargs.get("embeds") or call_kwargs[1].get("embeds", [])
        assert len(embeds) == 2

    async def test_guilds_isolated(self, tmp_path) -> None:
        p = _plugin(tmp_path)
        ctx_a = _ctx(guild_id=100)
        channel = MagicMock()
        channel.id = 555
        channel.mention = "<#555>"

        await p.announcement_add(ctx_a, channel, "1h", "Guild A msg")

        from easycord.server_config import ServerConfigStore
        store = ServerConfigStore(str(tmp_path / "announcements"))
        cfg_b = await store.load(200)
        data_b = cfg_b.get_other("announcements", {})
        assert data_b.get("items", []) == []


# ---------------------------------------------------------------------------
# Layer 3: command flow with MagicMock
# ---------------------------------------------------------------------------

class TestCommandFlow:
    async def test_add_invalid_interval(self, tmp_path) -> None:
        p = _plugin(tmp_path)
        ctx = _ctx()
        channel = MagicMock()
        channel.id = 555
        channel.mention = "<#555>"

        await p.announcement_add(ctx, channel, "bad-interval", "msg")

        ctx.respond.assert_awaited_once()
        response_text = ctx.respond.call_args[0][0]
        assert "Invalid" in response_text or "invalid" in response_text.lower()

    async def test_add_stores_announcement(self, tmp_path) -> None:
        p = _plugin(tmp_path)
        ctx = _ctx()
        channel = MagicMock()
        channel.id = 777
        channel.mention = "<#777>"

        await p.announcement_add(ctx, channel, "30m", "Hello!")

        ctx.respond.assert_awaited_once()
        call_args = ctx.respond.call_args[0][0]
        assert "Announcement #1" in call_args

    async def test_list_empty(self, tmp_path) -> None:
        p = _plugin(tmp_path)
        ctx = _ctx()

        await p.announcement_list(ctx)

        ctx.respond.assert_awaited_once()
        response_text = ctx.respond.call_args[0][0]
        assert "No announcements" in response_text

    async def test_remove_not_found(self, tmp_path) -> None:
        p = _plugin(tmp_path)
        ctx = _ctx()

        await p.announcement_remove(ctx, 999)

        ctx.respond.assert_awaited_once()
        response_text = ctx.respond.call_args[0][0]
        assert "999" in response_text

    async def test_remove_success(self, tmp_path) -> None:
        p = _plugin(tmp_path)
        ctx = _ctx()
        channel = MagicMock()
        channel.id = 555
        channel.mention = "<#555>"

        await p.announcement_add(ctx, channel, "1h", "Goodbye!")

        remove_ctx = _ctx()
        await p.announcement_remove(remove_ctx, 1)

        remove_ctx.respond.assert_awaited_once()
        response_text = remove_ctx.respond.call_args[0][0]
        assert "#1" in response_text
