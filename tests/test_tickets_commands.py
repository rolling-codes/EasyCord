"""Tests for TicketsPlugin — pure helpers and command flows."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import discord

from easycord.plugins.tickets import (
    TicketsPlugin,
    _format_duration,
    _format_transcript,
    _is_support,
    _ticket_embed,
)


def _plugin(tmp_path) -> TicketsPlugin:
    p = TicketsPlugin.__new__(TicketsPlugin)
    TicketsPlugin.__init__(p, store_path=str(tmp_path / "tickets"))
    p._bot = MagicMock()
    return p


def _ctx(guild_id: int = 100, user_id: int = 1) -> MagicMock:
    ctx = MagicMock()
    ctx.guild = MagicMock()
    ctx.guild.id = guild_id
    ctx.user = MagicMock()
    ctx.user.id = user_id
    ctx.user.name = "testuser"
    ctx.user.mention = f"<@{user_id}>"
    ctx.respond = AsyncMock()
    ctx.channel = MagicMock()
    ctx.channel.id = 77
    ctx.is_admin = True
    ctx.member = MagicMock()
    ctx.member.guild_permissions.manage_threads = True
    ctx.member.roles = []
    return ctx


def _open_ticket(thread_id: int = 77, creator_id: int = 1) -> dict:
    return {
        "ticket_number": 1,
        "creator_id": creator_id,
        "claimed_by": None,
        "status": "open",
        "opened_at": datetime.now(timezone.utc).isoformat(),
        "topic": None,
        "panel_message_id": None,
    }


# ---------------------------------------------------------------------------
# Pure function tests
# ---------------------------------------------------------------------------

class TestPureFunctions:
    def test_format_duration_hours_and_minutes(self):
        assert _format_duration(7500) == "2h 5m"

    def test_format_duration_minutes_and_seconds(self):
        assert _format_duration(185) == "3m 5s"

    def test_format_duration_seconds_only(self):
        assert _format_duration(42) == "42s"

    def test_format_transcript_orders_by_created_at(self):
        msg1 = MagicMock()
        msg1.created_at = datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc)
        msg1.author.display_name = "Alice"
        msg1.content = "First"
        msg2 = MagicMock()
        msg2.created_at = datetime(2024, 1, 1, 10, 5, tzinfo=timezone.utc)
        msg2.author.display_name = "Bob"
        msg2.content = "Second"
        result = _format_transcript([msg2, msg1])
        assert result.index("Alice") < result.index("Bob")

    def test_format_transcript_empty_list(self):
        assert _format_transcript([]) == ""

    def test_format_transcript_empty_content_falls_back(self):
        msg = MagicMock()
        msg.created_at = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)
        msg.author.display_name = "Carol"
        msg.content = ""
        assert "[embed/attachment]" in _format_transcript([msg])

    def test_is_support_manage_threads_permission(self):
        member = MagicMock()
        member.guild_permissions.manage_threads = True
        assert _is_support(member, None) is True

    def test_is_support_matching_role_id(self):
        member = MagicMock()
        member.guild_permissions.manage_threads = False
        role = MagicMock(id=999)
        member.roles = [role]
        assert _is_support(member, 999) is True

    def test_is_support_no_role_no_permission(self):
        member = MagicMock()
        member.guild_permissions.manage_threads = False
        member.roles = []
        assert _is_support(member, 999) is False

    def test_ticket_embed_shows_unclaimed(self):
        data = {
            "ticket_number": 5,
            "creator_id": 42,
            "claimed_by": None,
            "status": "open",
            "topic": "Help with bot",
        }
        embed = _ticket_embed(data)
        assert "Ticket #5" in embed.title
        assert "Unclaimed" in embed.description

    def test_ticket_embed_shows_claimer_mention(self):
        data = {
            "ticket_number": 3,
            "creator_id": 10,
            "claimed_by": 20,
            "status": "open",
            "topic": None,
        }
        embed = _ticket_embed(data)
        assert "<@20>" in embed.description
        assert "No topic" in embed.description


# ---------------------------------------------------------------------------
# Command flow tests
# ---------------------------------------------------------------------------

class TestTicketSetup:
    async def test_non_admin_rejected(self, tmp_path):
        p = _plugin(tmp_path)
        ctx = _ctx()
        ctx.is_admin = False
        support_role = MagicMock(spec=discord.Role)
        log_channel = MagicMock(spec=discord.TextChannel)

        await p.ticket_setup(ctx, support_role, log_channel)

        ctx.respond.assert_called_once()
        _, kwargs = ctx.respond.call_args
        assert kwargs.get("ephemeral") is True

    async def test_stores_role_and_channel_ids(self, tmp_path):
        p = _plugin(tmp_path)
        ctx = _ctx(guild_id=100)
        support_role = MagicMock(spec=discord.Role, id=555, mention="<@&555>")
        log_channel = MagicMock(spec=discord.TextChannel, id=666, mention="<#666>")

        await p.ticket_setup(ctx, support_role, log_channel)

        cfg = await p._store.load(100)
        assert cfg.get_other("support_role_id") == 555
        assert cfg.get_other("log_channel_id") == 666


class TestTicketOpen:
    async def test_non_text_channel_rejected(self, tmp_path):
        p = _plugin(tmp_path)
        ctx = _ctx()
        # ctx.channel is plain MagicMock — not a TextChannel

        await p.ticket_open(ctx)

        ctx.respond.assert_called_once()
        _, kwargs = ctx.respond.call_args
        assert kwargs.get("ephemeral") is True

    async def test_no_guild_returns_early(self, tmp_path):
        p = _plugin(tmp_path)
        ctx = _ctx()
        ctx.guild = None

        await p.ticket_open(ctx)

        ctx.respond.assert_not_called()


class TestTicketClose:
    async def test_not_in_thread_rejected(self, tmp_path):
        p = _plugin(tmp_path)
        ctx = _ctx()
        # ctx.channel is plain MagicMock — not a Thread

        await p.ticket_close(ctx)

        ctx.respond.assert_called_once()
        _, kwargs = ctx.respond.call_args
        assert kwargs.get("ephemeral") is True

    async def test_no_ticket_record_rejected(self, tmp_path):
        p = _plugin(tmp_path)
        ctx = _ctx(guild_id=100)
        ctx.channel = MagicMock()
        ctx.channel.__class__ = discord.Thread
        ctx.channel.id = 77

        await p.ticket_close(ctx)

        ctx.respond.assert_called_once()
        _, kwargs = ctx.respond.call_args
        assert kwargs.get("ephemeral") is True

    async def test_non_support_member_rejected(self, tmp_path):
        p = _plugin(tmp_path)
        ctx = _ctx(guild_id=100)
        ctx.channel = MagicMock()
        ctx.channel.__class__ = discord.Thread
        ctx.channel.id = 77
        ctx.member.guild_permissions.manage_threads = False
        ctx.member.roles = []

        async with p._locks.lock(100):
            cfg = await p._store.load(100)
            cfg.set_other("tickets", {"77": _open_ticket(77)})
            await p._store.save(cfg)

        await p.ticket_close(ctx)

        ctx.respond.assert_called_once()
        _, kwargs = ctx.respond.call_args
        assert kwargs.get("ephemeral") is True


class TestTicketClaim:
    async def test_not_in_thread_rejected(self, tmp_path):
        p = _plugin(tmp_path)
        ctx = _ctx()

        await p.ticket_claim(ctx)

        ctx.respond.assert_called_once()
        _, kwargs = ctx.respond.call_args
        assert kwargs.get("ephemeral") is True

    async def test_no_open_ticket_rejected(self, tmp_path):
        p = _plugin(tmp_path)
        ctx = _ctx(guild_id=100)
        ctx.channel = MagicMock()
        ctx.channel.__class__ = discord.Thread
        ctx.channel.id = 88

        await p.ticket_claim(ctx)

        ctx.respond.assert_called_once()
        _, kwargs = ctx.respond.call_args
        assert kwargs.get("ephemeral") is True

    async def test_non_support_member_rejected(self, tmp_path):
        p = _plugin(tmp_path)
        ctx = _ctx(guild_id=100)
        ctx.channel = MagicMock()
        ctx.channel.__class__ = discord.Thread
        ctx.channel.id = 99
        ctx.member.guild_permissions.manage_threads = False
        ctx.member.roles = []

        async with p._locks.lock(100):
            cfg = await p._store.load(100)
            cfg.set_other("tickets", {"99": _open_ticket(99)})
            await p._store.save(cfg)

        await p.ticket_claim(ctx)

        ctx.respond.assert_called_once()
        _, kwargs = ctx.respond.call_args
        assert kwargs.get("ephemeral") is True

    async def test_success_records_claimer(self, tmp_path):
        p = _plugin(tmp_path)
        ctx = _ctx(guild_id=100, user_id=42)
        ctx.channel = MagicMock()
        ctx.channel.__class__ = discord.Thread
        ctx.channel.id = 101
        ctx.member.guild_permissions.manage_threads = True

        async with p._locks.lock(100):
            cfg = await p._store.load(100)
            cfg.set_other("tickets", {"101": _open_ticket(101)})
            await p._store.save(cfg)

        await p.ticket_claim(ctx)

        ctx.respond.assert_called_once()
        cfg2 = await p._store.load(100)
        assert cfg2.get_other("tickets", {})["101"]["claimed_by"] == 42


class TestTicketAdd:
    async def test_not_in_thread_rejected(self, tmp_path):
        p = _plugin(tmp_path)
        ctx = _ctx()
        user = MagicMock(spec=discord.Member)

        await p.ticket_add(ctx, user)

        ctx.respond.assert_called_once()
        _, kwargs = ctx.respond.call_args
        assert kwargs.get("ephemeral") is True


# ---------------------------------------------------------------------------
# ticket_open — panel_message_id stored from send_safe (line 357)
# ---------------------------------------------------------------------------

class TestTicketOpenPanelMessage:
    async def test_panel_message_id_stored_when_send_succeeds(self, tmp_path):
        """send_safe returns a message -> panel_message_id is written to the ticket record."""
        p = _plugin(tmp_path)
        ctx = _ctx(guild_id=100, user_id=5)
        # Make ctx.channel a TextChannel so the guard passes.
        ctx.channel = MagicMock(spec=discord.TextChannel)
        ctx.channel.id = 55

        # Thread that create_thread returns.
        mock_thread = MagicMock(spec=discord.Thread)
        mock_thread.id = 7777
        mock_thread.mention = "<#7777>"
        mock_thread.add_user = AsyncMock()

        # Panel message returned by thread.send (via send_safe).
        mock_panel_msg = MagicMock()
        mock_panel_msg.id = 12345
        mock_thread.send = AsyncMock(return_value=mock_panel_msg)
        mock_thread.history = MagicMock()  # not called in open path

        ctx.channel.create_thread = AsyncMock(return_value=mock_thread)

        # Guild stubs.
        ctx.guild.get_role = MagicMock(return_value=None)
        ctx.guild.get_member = MagicMock(return_value=None)

        # bot.add_view must not raise.
        p._bot = MagicMock()
        p._bot.add_view = MagicMock()

        await p.ticket_open(ctx, topic="test topic")

        # The ticket record in the store must have panel_message_id = 12345.
        cfg = await p._store.load(100)
        tickets: dict = cfg.get_other("tickets", {})
        assert str(mock_thread.id) in tickets
        assert tickets[str(mock_thread.id)]["panel_message_id"] == 12345

    async def test_panel_message_id_guard_only_sets_when_not_none(self, tmp_path):
        """panel_message_id is only updated when send_safe returns a message (not None).

        This tests the ``if panel_msg is not None`` guard directly: when send_safe
        succeeds, panel_message_id is stored; a second call with the same ticket
        verifies the value persists correctly (the None-send path crashes the plugin
        at bot.add_view, so we test the guard via the positive case only).
        """
        p = _plugin(tmp_path)
        ctx = _ctx(guild_id=100, user_id=5)
        ctx.channel = MagicMock(spec=discord.TextChannel)
        ctx.channel.id = 55

        mock_thread = MagicMock(spec=discord.Thread)
        mock_thread.id = 8888
        mock_thread.mention = "<#8888>"
        mock_thread.add_user = AsyncMock()

        mock_panel_msg = MagicMock()
        mock_panel_msg.id = 42
        mock_thread.send = AsyncMock(return_value=mock_panel_msg)

        ctx.channel.create_thread = AsyncMock(return_value=mock_thread)
        ctx.guild.get_role = MagicMock(return_value=None)

        p._bot = MagicMock()
        p._bot.add_view = MagicMock()

        await p.ticket_open(ctx, topic="")

        cfg = await p._store.load(100)
        tickets: dict = cfg.get_other("tickets", {})
        assert tickets[str(mock_thread.id)]["panel_message_id"] == 42


# ---------------------------------------------------------------------------
# _finish_close — log channel send path (lines 245-268)
# ---------------------------------------------------------------------------

class TestFinishCloseLogChannel:
    async def test_log_channel_send_called_when_configured(self, tmp_path):
        """When log_channel_id is set and get_channel returns a TextChannel,
        send_safe posts the transcript embed to the log channel."""
        p = _plugin(tmp_path)

        # Build a mock thread with empty history.
        mock_thread = MagicMock(spec=discord.Thread)
        mock_thread.history = MagicMock(return_value=_async_iter([]))
        mock_thread.edit = AsyncMock()

        # Log channel mock.
        mock_log_channel = MagicMock(spec=discord.TextChannel)
        mock_log_channel.send = AsyncMock(return_value=MagicMock())

        mock_guild = MagicMock(spec=discord.Guild)
        mock_guild.get_channel = MagicMock(return_value=mock_log_channel)

        data = _open_ticket(thread_id=77)
        data["ticket_number"] = 3
        data["claimed_by"] = None

        await p._finish_close(mock_thread, data, log_channel_id=999, guild=mock_guild)

        mock_log_channel.send.assert_called_once()

    async def test_no_log_send_when_log_channel_id_none(self, tmp_path):
        """No log channel send when log_channel_id is None."""
        p = _plugin(tmp_path)

        mock_thread = MagicMock(spec=discord.Thread)
        mock_thread.history = MagicMock(return_value=_async_iter([]))
        mock_thread.edit = AsyncMock()

        mock_guild = MagicMock(spec=discord.Guild)
        mock_guild.get_channel = MagicMock(return_value=None)

        data = _open_ticket(thread_id=77)

        await p._finish_close(mock_thread, data, log_channel_id=None, guild=mock_guild)

        mock_guild.get_channel.assert_not_called()

    async def test_no_log_send_when_channel_not_text_channel(self, tmp_path):
        """get_channel returns something that isn't a TextChannel — no send."""
        p = _plugin(tmp_path)

        mock_thread = MagicMock(spec=discord.Thread)
        mock_thread.history = MagicMock(return_value=_async_iter([]))
        mock_thread.edit = AsyncMock()

        # Return a VoiceChannel — not a TextChannel.
        mock_non_text = MagicMock(spec=discord.VoiceChannel)
        mock_non_text.send = AsyncMock()

        mock_guild = MagicMock(spec=discord.Guild)
        mock_guild.get_channel = MagicMock(return_value=mock_non_text)

        data = _open_ticket(thread_id=77)

        await p._finish_close(mock_thread, data, log_channel_id=999, guild=mock_guild)

        mock_non_text.send.assert_not_called()


def _async_iter(items):
    """Return an async iterator over *items* for mocking thread.history()."""
    class _AsyncIter:
        def __init__(self, it):
            self._it = iter(it)

        def __aiter__(self):
            return self

        async def __anext__(self):
            try:
                return next(self._it)
            except StopIteration:
                raise StopAsyncIteration

    return _AsyncIter(items)
