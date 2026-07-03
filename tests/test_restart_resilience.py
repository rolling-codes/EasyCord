"""Restart-resilience tests for Polls, Reminders, and Birthday plugins.

These exercise the real plugins' persistence and on_ready restore paths: state
is reloaded from the per-guild store after a simulated restart, timers/tasks are
re-armed, delivery is idempotent (the `done` flag guards double-fires), and
corrupted payloads are skipped instead of crashing startup.
"""
from __future__ import annotations

import datetime as dt
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from easycord.plugins.birthday import BirthdayPlugin
from easycord.plugins.polls import PollsPlugin
from easycord.plugins.reminder import ReminderPlugin

pytestmark = pytest.mark.asyncio


# ── seeding helpers ───────────────────────────────────────────


async def _seed_poll(plugin, guild_id, message_id, *, status="active",
                     end_offset=3600.0, votes=None, options=None, corrupt=False):
    cfg = await plugin._store.load(guild_id)
    polls = cfg.get_other("polls", {})
    if corrupt:
        polls[str(message_id)] = {"status": "active"}  # missing question/options/end_time
    else:
        end_time = (datetime.now(timezone.utc) + timedelta(seconds=end_offset)).isoformat()
        polls[str(message_id)] = {
            "status": status,
            "question": "Favourite colour?",
            "options": options or ["Red", "Blue"],
            "end_time": end_time,
            "votes": votes or {},
        }
    cfg.set_other("polls", polls)
    await plugin._store.save(cfg)


async def _seed_reminder(plugin, guild_id, rid, *, fire_offset=3600.0,
                         done=False, channel_id=55, user_id=7):
    cfg = await plugin._store.load(guild_id)
    data = cfg.get_other("reminders", {})
    fire_at = (datetime.now(timezone.utc) + timedelta(seconds=fire_offset)).isoformat()
    data.setdefault("reminders", []).append({
        "id": rid, "user_id": user_id, "channel_id": channel_id,
        "message": "ping", "fire_at": fire_at, "done": done,
    })
    data["next_id"] = rid + 1
    cfg.set_other("reminders", data)
    await plugin._store.save(cfg)


async def _seed_birthday(plugin, guild_id, uid, today, *, channel_id=99, role_id=12):
    cfg = await plugin._store.load(guild_id)
    data = cfg.get_other("birthday", {})
    data["channel_id"] = channel_id
    data["role_id"] = role_id
    data.setdefault("birthdays", {})[str(uid)] = {"month": today.month, "day": today.day}
    data.setdefault("role_assigned", {})
    cfg.set_other("birthday", data)
    await plugin._store.save(cfg)


def _text_channel(send=None):
    channel = MagicMock(spec=discord.TextChannel)
    channel.send = send or AsyncMock()
    return channel


# ── Polls ─────────────────────────────────────────────────────


class TestPollsPluginRestartResilience:
    async def test_active_views_re_register_custom_ids(self, tmp_path):
        plugin = PollsPlugin(store_path=str(tmp_path / "polls"))
        plugin._bot = MagicMock()
        await _seed_poll(plugin, 1, 555, options=["Red", "Blue"])

        await plugin.on_ready()

        plugin._bot.add_view.assert_called_once()
        view = plugin._bot.add_view.call_args.args[0]
        assert plugin._bot.add_view.call_args.kwargs["message_id"] == 555
        custom_ids = [c.custom_id for c in view.children]
        assert "poll:vote:555:0" in custom_ids
        assert "poll:vote:555:1" in custom_ids
        await plugin.on_unload()

    async def test_pre_existing_votes_match_db_states(self, tmp_path):
        plugin = PollsPlugin(store_path=str(tmp_path / "polls"))
        plugin._bot = MagicMock()
        await _seed_poll(plugin, 1, 555, votes={"10": 0, "11": 1})

        await plugin.on_ready()

        cfg = await plugin._store.load(1)
        restored = cfg.get_other("polls", {})["555"]["votes"]
        assert restored == {"10": 0, "11": 1}
        await plugin.on_unload()

    async def test_duration_timers_resume_without_restarting(self, tmp_path):
        plugin = PollsPlugin(store_path=str(tmp_path / "polls"))
        plugin._bot = MagicMock()
        await _seed_poll(plugin, 1, 555, end_offset=3600.0)

        await plugin.on_ready()

        assert 555 in plugin._timers.get(1, {})
        await plugin.on_unload()
        assert plugin._timers == {}

    async def test_skip_corrupted_database_payloads(self, tmp_path):
        plugin = PollsPlugin(store_path=str(tmp_path / "polls"))
        plugin._bot = MagicMock()
        await _seed_poll(plugin, 1, 555)            # valid
        await _seed_poll(plugin, 1, 999, corrupt=True)

        await plugin.on_ready()  # must not raise

        assert 555 in plugin._timers.get(1, {})     # valid poll resumed
        assert 999 not in plugin._timers.get(1, {})  # corrupt one skipped
        await plugin.on_unload()


# ── Reminders ─────────────────────────────────────────────────


class TestRemindersPluginRestartResilience:
    async def test_scheduled_reminder_fires_accurately_after_crash(self, tmp_path):
        plugin = ReminderPlugin(store_path=str(tmp_path / "reminder"))
        plugin._bot = MagicMock()
        await _seed_reminder(plugin, 100, 1, fire_offset=3600.0)

        await plugin.on_ready()

        assert 1 in plugin._tasks.get(100, {})  # pending reminder re-scheduled
        await plugin.on_unload()

    async def test_event_execution_idempotency_during_fire(self, tmp_path):
        plugin = ReminderPlugin(store_path=str(tmp_path / "reminder"))
        channel = _text_channel()
        guild = MagicMock()
        guild.get_channel.return_value = channel
        bot = MagicMock()
        bot.get_guild.return_value = guild
        plugin._bot = bot
        await _seed_reminder(plugin, 100, 1, channel_id=55, user_id=7)

        await plugin._deliver_reminder(100, 1)
        await plugin._deliver_reminder(100, 1)  # second fire must be a no-op

        channel.send.assert_awaited_once()
        cfg = await plugin._store.load(100)
        assert cfg.get_other("reminders", {})["reminders"][0]["done"] is True

    async def test_reminder_rescheduling_on_missed_window(self, tmp_path):
        plugin = ReminderPlugin(store_path=str(tmp_path / "reminder"))
        bot = MagicMock()
        bot.get_guild.return_value = None  # deliver is a no-op even if it fires
        plugin._bot = bot
        # fire_at already in the past -> missed window, must still be re-scheduled (delay 0)
        await _seed_reminder(plugin, 100, 1, fire_offset=-120.0)

        await plugin.on_ready()

        assert 1 in plugin._tasks.get(100, {})
        await plugin.on_unload()


# ── Birthday ──────────────────────────────────────────────────


class TestBirthdayPluginRestartResilience:
    def _wire_bot(self, plugin, *, channel, member, role):
        guild = MagicMock()
        guild.get_channel.return_value = channel
        guild.get_member.return_value = member
        guild.get_role.return_value = role
        bot = MagicMock()
        bot.get_guild.return_value = guild
        plugin._bot = bot

    async def test_scheduled_role_drops_execute_exactly_once(self, tmp_path):
        plugin = BirthdayPlugin(store_path=str(tmp_path / "birthday"))
        today = dt.datetime.now(dt.timezone.utc).date()
        channel = _text_channel()
        member = MagicMock()
        member.add_roles = AsyncMock()
        role = MagicMock()
        role.id = 12
        self._wire_bot(plugin, channel=channel, member=member, role=role)
        await _seed_birthday(plugin, 1, 42, today)

        await plugin._check_guild_birthdays(1, today)

        member.add_roles.assert_awaited_once()
        assert len(plugin._role_tasks) == 1  # exactly one delayed role-drop scheduled
        cfg = await plugin._store.load(1)
        assert "42" in cfg.get_other("birthday", {})["role_assigned"]
        await plugin.on_unload()

    async def test_graceful_handling_of_revoked_permissions(self, tmp_path):
        plugin = BirthdayPlugin(store_path=str(tmp_path / "birthday"))
        today = dt.datetime.now(dt.timezone.utc).date()
        channel = _text_channel()
        member = MagicMock()
        member.add_roles = AsyncMock(side_effect=discord.Forbidden(MagicMock(), "no perms"))
        role = MagicMock()
        role.id = 12
        self._wire_bot(plugin, channel=channel, member=member, role=role)
        await _seed_birthday(plugin, 1, 42, today)

        # Must not raise even though add_roles was revoked; announcement still goes out.
        await plugin._check_guild_birthdays(1, today)

        channel.send.assert_awaited_once()
        assert len(plugin._role_tasks) == 0  # no drop scheduled when assignment failed
        await plugin.on_unload()

    async def test_birthday_announcement_idempotency(self, tmp_path):
        plugin = BirthdayPlugin(store_path=str(tmp_path / "birthday"))
        today = dt.datetime.now(dt.timezone.utc).date()
        channel = _text_channel()
        member = MagicMock()
        member.add_roles = AsyncMock()
        role = MagicMock()
        role.id = 12
        self._wire_bot(plugin, channel=channel, member=member, role=role)
        await _seed_birthday(plugin, 1, 42, today)

        await plugin._check_guild_birthdays(1, today)
        assert channel.send.await_count == 1

        # A restart (on_ready) defers checks to the next midnight — it must NOT
        # re-announce today's birthday, so the count stays at one.
        await plugin.on_ready()
        assert channel.send.await_count == 1
        await plugin.on_unload()
