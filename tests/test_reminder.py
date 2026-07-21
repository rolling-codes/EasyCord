"""Tests for ReminderPlugin — pure functions, store logic, and command flow."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import discord

from easycord.plugins.reminder import ReminderPlugin, _reminder_embed


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
    ctx.channel = MagicMock(spec=discord.TextChannel)
    ctx.channel.id = 55
    ctx.is_admin = True
    ctx.member = MagicMock()
    ctx.member.guild_permissions = MagicMock()
    ctx.member.guild_permissions.manage_guild = True
    return ctx


def _plugin(tmp_path) -> ReminderPlugin:
    p = ReminderPlugin.__new__(ReminderPlugin)
    ReminderPlugin.__init__(p, store_path=str(tmp_path / "reminder"))
    return p


def _make_reminder(
    rid: int = 1,
    user_id: int = 1,
    channel_id: int = 55,
    message: str = "Test reminder",
    done: bool = False,
    offset_seconds: int = 3600,
) -> dict:
    fire_at = (datetime.now(timezone.utc) + timedelta(seconds=offset_seconds)).isoformat()
    return {
        "id": rid,
        "user_id": user_id,
        "channel_id": channel_id,
        "message": message,
        "fire_at": fire_at,
        "done": done,
    }


# ---------------------------------------------------------------------------
# Layer 1 — Pure function tests
# ---------------------------------------------------------------------------

class TestPureFunctions:
    def test_reminder_embed_contains_message(self) -> None:
        reminder = _make_reminder(message="Pick up laundry")
        embed = _reminder_embed(reminder)
        assert embed.description == "Pick up laundry"

    def test_reminder_embed_title(self) -> None:
        reminder = _make_reminder()
        embed = _reminder_embed(reminder)
        assert embed.title is not None
        assert "Reminder" in embed.title

    def test_reminder_embed_has_footer(self) -> None:
        reminder = _make_reminder()
        embed = _reminder_embed(reminder)
        assert embed.footer is not None
        assert embed.footer.text is not None

    def test_reminder_embed_bad_fire_at(self) -> None:
        reminder = {"id": 1, "message": "hello", "fire_at": "not-a-date"}
        embed = _reminder_embed(reminder)
        assert embed.description == "hello"
        assert embed.footer.text is not None
        assert "unknown time" in embed.footer.text

    def test_reminder_embed_empty_message(self) -> None:
        reminder = _make_reminder(message="")
        embed = _reminder_embed(reminder)
        assert embed.description == ""

    def test_parse_duration_imported(self) -> None:
        from easycord.plugins.reminder import _parse_duration as pd
        assert pd("1h") == 3600

    def test_parse_duration_minutes(self) -> None:
        from easycord.plugins.reminder import _parse_duration as pd
        assert pd("30m") == 1800

    def test_parse_duration_days(self) -> None:
        from easycord.plugins.reminder import _parse_duration as pd
        assert pd("2d") == 172800

    def test_parse_duration_seconds(self) -> None:
        from easycord.plugins.reminder import _parse_duration as pd
        assert pd("45s") == 45

    def test_parse_duration_invalid_raises(self) -> None:
        import pytest as _pytest

        from easycord.plugins.reminder import _parse_duration as pd
        with _pytest.raises(ValueError):
            pd("not-a-duration")


# ---------------------------------------------------------------------------
# Layer 2 — Store tests (tmp_path)
# ---------------------------------------------------------------------------

class TestReminderStore:
    async def test_add_reminder_persists(self, tmp_path) -> None:
        p = _plugin(tmp_path)
        guild_id = 100
        reminder = _make_reminder(rid=1)

        async with p._guild_lock(guild_id):
            cfg = await p._store.load(guild_id)
            data = cfg.get_other("reminders", {})
            data.setdefault("reminders", []).append(reminder)
            data["next_id"] = 2
            cfg.set_other("reminders", data)
            await p._store.save(cfg)

        cfg2 = await p._store.load(guild_id)
        data2 = cfg2.get_other("reminders", {})
        assert len(data2["reminders"]) == 1
        assert data2["reminders"][0]["id"] == 1
        assert data2["next_id"] == 2

    async def test_cancel_reminder_marks_done(self, tmp_path) -> None:
        p = _plugin(tmp_path)
        guild_id = 100
        reminder = _make_reminder(rid=1, done=False)

        async with p._guild_lock(guild_id):
            cfg = await p._store.load(guild_id)
            data = cfg.get_other("reminders", {})
            data.setdefault("reminders", []).append(reminder)
            data["next_id"] = 2
            cfg.set_other("reminders", data)
            await p._store.save(cfg)

        async with p._guild_lock(guild_id):
            cfg = await p._store.load(guild_id)
            data = cfg.get_other("reminders", {})
            for r in data["reminders"]:
                if r["id"] == 1:
                    r["done"] = True
            cfg.set_other("reminders", data)
            await p._store.save(cfg)

        cfg3 = await p._store.load(guild_id)
        data3 = cfg3.get_other("reminders", {})
        assert data3["reminders"][0]["done"] is True

    async def test_list_reminders_filters_done(self, tmp_path) -> None:
        p = _plugin(tmp_path)
        guild_id = 100
        r1 = _make_reminder(rid=1, done=False)
        r2 = _make_reminder(rid=2, done=True)

        async with p._guild_lock(guild_id):
            cfg = await p._store.load(guild_id)
            data = cfg.get_other("reminders", {})
            data["reminders"] = [r1, r2]
            data["next_id"] = 3
            cfg.set_other("reminders", data)
            await p._store.save(cfg)

        cfg2 = await p._store.load(guild_id)
        data2 = cfg2.get_other("reminders", {})
        pending = [r for r in data2["reminders"] if not r["done"]]
        assert len(pending) == 1
        assert pending[0]["id"] == 1

    async def test_guilds_isolated(self, tmp_path) -> None:
        p = _plugin(tmp_path)
        guild_a, guild_b = 100, 200

        async with p._guild_lock(guild_a):
            cfg = await p._store.load(guild_a)
            data = cfg.get_other("reminders", {})
            data["reminders"] = [_make_reminder(rid=1)]
            data["next_id"] = 2
            cfg.set_other("reminders", data)
            await p._store.save(cfg)

        cfg_b = await p._store.load(guild_b)
        data_b = cfg_b.get_other("reminders", {})
        assert data_b.get("reminders", []) == []


# ---------------------------------------------------------------------------
# Layer 3 — Command flow tests
# ---------------------------------------------------------------------------

class TestReminderCommands:
    async def test_remind_invalid_duration(self, tmp_path) -> None:
        p = _plugin(tmp_path)
        ctx = _ctx()

        await p.remind(ctx, "not-a-duration", "hello")

        ctx.respond.assert_called_once()
        args, kwargs = ctx.respond.call_args
        assert kwargs.get("ephemeral") is True

    async def test_remind_stores_and_responds(self, tmp_path) -> None:
        p = _plugin(tmp_path)
        ctx = _ctx(guild_id=100, user_id=1)

        # Patch create_task to avoid actual asyncio scheduling
        import asyncio
        from unittest.mock import patch

        with patch.object(asyncio, "create_task", side_effect=lambda c: (c.close(), MagicMock())[1]):
            await p.remind(ctx, "30m", "Buy milk")

        ctx.respond.assert_called_once()
        _, kwargs = ctx.respond.call_args
        assert kwargs.get("ephemeral") is True
        assert "embed" in kwargs

        cfg = await p._store.load(100)
        data = cfg.get_other("reminders", {})
        assert len(data["reminders"]) == 1
        assert data["reminders"][0]["message"] == "Buy milk"
        assert data["reminders"][0]["done"] is False

    async def test_reminders_list_empty(self, tmp_path) -> None:
        p = _plugin(tmp_path)
        ctx = _ctx(guild_id=100, user_id=1)

        await p.reminders(ctx)

        ctx.respond.assert_called_once()
        args, kwargs = ctx.respond.call_args
        assert kwargs.get("ephemeral") is True
        response_text = args[0] if args else ""
        assert "no pending" in response_text.lower() or "no reminders" in response_text.lower()

    async def test_reminder_cancel_not_found(self, tmp_path) -> None:
        p = _plugin(tmp_path)
        ctx = _ctx(guild_id=100, user_id=1)

        await p.reminder_cancel(ctx, 999)

        ctx.respond.assert_called_once()
        args, kwargs = ctx.respond.call_args
        assert kwargs.get("ephemeral") is True
        response_text = args[0] if args else ""
        assert "999" in response_text

    async def test_reminder_cancel_success(self, tmp_path) -> None:
        p = _plugin(tmp_path)
        ctx = _ctx(guild_id=100, user_id=1)

        import asyncio
        from unittest.mock import patch

        with patch.object(asyncio, "create_task", side_effect=lambda c: (c.close(), MagicMock())[1]):
            await p.remind(ctx, "1h", "Test message")
        ctx.respond.reset_mock()

        await p.reminder_cancel(ctx, 1)

        ctx.respond.assert_called_once()
        args, kwargs = ctx.respond.call_args
        assert kwargs.get("ephemeral") is True
        response_text = args[0] if args else ""
        assert "#1" in response_text or "1" in response_text

        cfg = await p._store.load(100)
        data = cfg.get_other("reminders", {})
        assert data["reminders"][0]["done"] is True

    async def test_reminders_list_shows_pending(self, tmp_path) -> None:
        p = _plugin(tmp_path)
        ctx = _ctx(guild_id=100, user_id=1)

        import asyncio
        from unittest.mock import patch

        with patch.object(asyncio, "create_task", side_effect=lambda c: (c.close(), MagicMock())[1]):
            await p.remind(ctx, "2h", "Call dentist")
        ctx.respond.reset_mock()

        await p.reminders(ctx)

        ctx.respond.assert_called_once()
        _, kwargs = ctx.respond.call_args
        assert "embed" in kwargs
        embed = kwargs["embed"]
        assert embed.description is not None
        assert "Call dentist" in embed.description
