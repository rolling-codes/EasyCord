"""Tests for TicketsPlugin pure functions and store logic."""
from __future__ import annotations

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


# ---------------------------------------------------------------------------
# _format_duration
# ---------------------------------------------------------------------------

class TestFormatDuration:
    def test_seconds_only(self) -> None:
        assert _format_duration(45) == "45s"

    def test_minutes_and_seconds(self) -> None:
        assert _format_duration(90) == "1m 30s"

    def test_hours_and_minutes(self) -> None:
        assert _format_duration(7500) == "2h 5m"

    def test_zero(self) -> None:
        assert _format_duration(0) == "0s"

    def test_exact_hour(self) -> None:
        assert _format_duration(3600) == "1h 0m"

    def test_exact_minute(self) -> None:
        assert _format_duration(60) == "1m 0s"

    def test_float_input_truncated(self) -> None:
        result = _format_duration(90.9)
        assert result == "1m 30s"


# ---------------------------------------------------------------------------
# _format_transcript
# ---------------------------------------------------------------------------

def _make_message(content: str, author_name: str, ts_offset: int = 0) -> MagicMock:
    from datetime import datetime, timezone, timedelta
    msg = MagicMock(spec=discord.Message)
    msg.content = content
    msg.author = MagicMock()
    msg.author.display_name = author_name
    msg.created_at = datetime(2026, 6, 15, 12, 0, ts_offset, tzinfo=timezone.utc)
    return msg


class TestFormatTranscript:
    def test_empty_list(self) -> None:
        assert _format_transcript([]) == ""

    def test_single_message(self) -> None:
        msg = _make_message("Hello!", "Alice")
        result = _format_transcript([msg])
        assert "Alice" in result
        assert "Hello!" in result
        assert "12:00" in result

    def test_multiple_messages_sorted_by_time(self) -> None:
        m1 = _make_message("first", "Alice", ts_offset=0)
        m2 = _make_message("second", "Bob", ts_offset=5)
        result = _format_transcript([m2, m1])  # intentionally reversed
        lines = result.splitlines()
        assert "first" in lines[0]
        assert "second" in lines[1]

    def test_empty_content_shows_placeholder(self) -> None:
        msg = _make_message("", "Alice")
        result = _format_transcript([msg])
        assert "[embed/attachment]" in result

    def test_format_includes_timestamp(self) -> None:
        msg = _make_message("hi", "Alice")
        result = _format_transcript([msg])
        assert "[12:00]" in result


# ---------------------------------------------------------------------------
# _is_support
# ---------------------------------------------------------------------------

def _make_member(*, manage_threads: bool = False, role_ids: list[int] | None = None) -> MagicMock:
    member = MagicMock(spec=discord.Member)
    perms = MagicMock(spec=discord.Permissions)
    perms.manage_threads = manage_threads
    member.guild_permissions = perms
    roles = []
    for rid in (role_ids or []):
        role = MagicMock(spec=discord.Role)
        role.id = rid
        roles.append(role)
    member.roles = roles
    return member


class TestIsSupport:
    def test_manage_threads_is_support(self) -> None:
        member = _make_member(manage_threads=True)
        assert _is_support(member, None) is True

    def test_matching_role_is_support(self) -> None:
        member = _make_member(role_ids=[100, 200])
        assert _is_support(member, 200) is True

    def test_wrong_role_not_support(self) -> None:
        member = _make_member(role_ids=[100])
        assert _is_support(member, 999) is False

    def test_no_role_no_perm_not_support(self) -> None:
        member = _make_member()
        assert _is_support(member, 100) is False

    def test_no_support_role_configured(self) -> None:
        member = _make_member(role_ids=[100])
        assert _is_support(member, None) is False

    def test_manage_threads_overrides_missing_role(self) -> None:
        member = _make_member(manage_threads=True, role_ids=[])
        assert _is_support(member, 999) is True


# ---------------------------------------------------------------------------
# _ticket_embed
# ---------------------------------------------------------------------------

class TestTicketEmbed:
    def _data(self, **overrides) -> dict:
        base = {
            "ticket_number": 7,
            "creator_id": 111,
            "claimed_by": None,
            "status": "open",
            "topic": "Need help",
        }
        base.update(overrides)
        return base

    def test_title_includes_number(self) -> None:
        embed = _ticket_embed(self._data())
        assert embed.title is not None
        assert "#7" in embed.title

    def test_unclaimed_shows_unclaimed(self) -> None:
        embed = _ticket_embed(self._data())
        assert embed.description is not None
        assert "Unclaimed" in embed.description

    def test_claimed_shows_mention(self) -> None:
        embed = _ticket_embed(self._data(claimed_by=999))
        assert embed.description is not None
        assert "<@999>" in embed.description

    def test_topic_in_description(self) -> None:
        embed = _ticket_embed(self._data(topic="My issue"))
        assert embed.description is not None
        assert "My issue" in embed.description

    def test_no_topic_shows_placeholder(self) -> None:
        embed = _ticket_embed(self._data(topic=None))
        assert embed.description is not None
        assert "No topic" in embed.description

    def test_creator_mention_in_description(self) -> None:
        embed = _ticket_embed(self._data(creator_id=42))
        assert embed.description is not None
        assert "<@42>" in embed.description

    def test_color_is_green(self) -> None:
        embed = _ticket_embed(self._data())
        assert embed.color == discord.Color.green()


class TestFinishCloseTranscript:
    async def test_fetches_most_recent_messages_not_oldest(self) -> None:
        """The transcript must capture the most recent 100 messages (the
        resolution), so history() is fetched with oldest_first=False."""
        from datetime import datetime, timezone

        plugin = TicketsPlugin.__new__(TicketsPlugin)
        recorded: dict = {}

        def history(*, limit=None, oldest_first=None):
            recorded["limit"] = limit
            recorded["oldest_first"] = oldest_first

            async def _gen():
                for _ in ():  # empty async generator
                    yield

            return _gen()

        thread = MagicMock(spec=discord.Thread)
        thread.history = history
        thread.edit = AsyncMock()

        data = {
            "opened_at": datetime.now(timezone.utc).isoformat(),
            "ticket_number": 1,
            "creator_id": 1,
            "claimed_by": None,
        }
        # No log channel / guild -> skip posting; we only assert the fetch direction.
        await plugin._finish_close(thread, data, None, None)

        assert recorded["oldest_first"] is False
        assert recorded["limit"] == 100
