"""Tests for TicketsPlugin — pure helpers and command flows."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

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

        async with p._guild_lock(100):
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

        async with p._guild_lock(100):
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

        async with p._guild_lock(100):
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
