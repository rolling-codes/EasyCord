"""Comprehensive offline tests for PollsPlugin."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import discord

from easycord.plugins.polls import (
    PollsPlugin,
    _bar,
    _format_option_line,
    _is_valid_duration,
    _poll_options,
    _tally,
    build_poll_embed,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _plugin(tmp_path) -> PollsPlugin:
    """Construct a PollsPlugin with in-memory-compatible store in a temp dir."""
    p = PollsPlugin.__new__(PollsPlugin)
    PollsPlugin.__init__(p, store_path=str(tmp_path / "polls"))
    bot = MagicMock()
    bot.add_view = MagicMock()
    bot.get_guild = MagicMock(return_value=None)
    p._bot = bot
    return p


def _ctx(guild_id: int = 100, user_id: int = 1, *, is_sendable: bool = True) -> MagicMock:
    """Return a minimal Context mock sufficient for PollsPlugin.poll."""
    ctx = MagicMock()
    ctx.guild = MagicMock()
    ctx.guild.id = guild_id
    ctx.respond = AsyncMock()

    # ctx.t acts as a passthrough returning the `default` kwarg (or key)
    ctx.t = MagicMock(side_effect=lambda key, *, default=None, **kw: default if default is not None else key)

    ctx.user = MagicMock()
    ctx.user.id = user_id

    # ctx.channel must be an instance of a SENDABLE_CHANNEL_TYPES type when valid
    if is_sendable:
        channel = MagicMock(spec=discord.TextChannel)
        channel.id = 55
    else:
        channel = MagicMock(spec=discord.CategoryChannel)
        channel.id = 55
    ctx.channel = channel

    # interaction.original_response() returns a message with an id and edit
    fake_msg = MagicMock()
    fake_msg.id = 900000000000000001
    fake_msg.edit = AsyncMock()
    ctx.interaction = MagicMock()
    ctx.interaction.original_response = AsyncMock(return_value=fake_msg)
    return ctx


async def _seed_active_poll(
    plugin: PollsPlugin,
    *,
    guild_id: int = 100,
    message_id: int = 42,
    question: str = "Best colour?",
    options: list[str] | None = None,
    votes: dict[str, int] | None = None,
    seconds_from_now: float = 3600.0,
    channel_id: int = 55,
) -> None:
    """Directly write an active poll into the plugin's store."""
    options = options or ["Red", "Blue"]
    votes = votes or {}
    end_dt = datetime.now(timezone.utc) + timedelta(seconds=seconds_from_now)
    async with plugin._guild_lock(guild_id):
        cfg = await plugin._store.load(guild_id)
        polls: dict = cfg.get_other("polls", {})
        polls[str(message_id)] = {
            "channel_id": channel_id,
            "question": question,
            "options": options,
            "votes": votes,
            "end_time": end_dt.isoformat(),
            "status": "active",
        }
        cfg.set_other("polls", polls)
        await plugin._store.save(cfg)


# ---------------------------------------------------------------------------
# Pure function tests
# ---------------------------------------------------------------------------

class TestPollOptions:
    def test_filters_empty_strings(self) -> None:
        assert _poll_options("A", "", "B") == ["A", "B"]

    def test_all_blank_returns_empty(self) -> None:
        assert _poll_options("", "  ", "") == []

    def test_strips_whitespace_only_entries(self) -> None:
        result = _poll_options("Alpha", "   ", "Beta")
        assert result == ["Alpha", "Beta"]

    def test_all_provided(self) -> None:
        assert _poll_options("A", "B", "C", "D", "E") == ["A", "B", "C", "D", "E"]

    def test_two_options_pass_through(self) -> None:
        assert _poll_options("Yes", "No") == ["Yes", "No"]


class TestIsValidDuration:
    def test_minimum_valid_is_five(self) -> None:
        assert _is_valid_duration(5) is True

    def test_four_is_invalid(self) -> None:
        assert _is_valid_duration(4) is False

    def test_zero_is_invalid(self) -> None:
        assert _is_valid_duration(0) is False

    def test_large_value_valid(self) -> None:
        assert _is_valid_duration(86400) is True


class TestTally:
    def test_empty_votes_returns_zeros(self) -> None:
        assert _tally(["A", "B"], {}) == [0, 0]

    def test_single_vote_for_first(self) -> None:
        assert _tally(["A", "B"], {"1": 0}) == [1, 0]

    def test_multiple_voters(self) -> None:
        votes = {"1": 0, "2": 1, "3": 0}
        assert _tally(["A", "B"], votes) == [2, 1]

    def test_all_votes_for_second(self) -> None:
        votes = {"1": 1, "2": 1}
        assert _tally(["X", "Y"], votes) == [0, 2]

    def test_vote_change_reflected(self) -> None:
        # Same user key appears once — last write wins in real code; tally just counts
        votes = {"1": 0, "2": 0, "3": 1}
        assert _tally(["A", "B"], votes) == [2, 1]


class TestBar:
    def test_full_bar(self) -> None:
        assert _bar(10) == "█" * 10

    def test_empty_bar(self) -> None:
        assert _bar(0) == "░" * 10

    def test_half_bar(self) -> None:
        assert _bar(5) == "█████░░░░░"

    def test_bar_always_ten_chars(self) -> None:
        for i in range(11):
            assert len(_bar(i)) == 10


class TestFormatOptionLine:
    def test_contains_option_name(self) -> None:
        line = _format_option_line("Alpha", 3, 10)
        assert "Alpha" in line

    def test_contains_vote_count(self) -> None:
        line = _format_option_line("Beta", 1, 5)
        assert "1 vote" in line

    def test_plural_votes(self) -> None:
        line = _format_option_line("Gamma", 2, 10)
        assert "2 votes" in line

    def test_singular_vote(self) -> None:
        line = _format_option_line("Delta", 1, 1)
        assert "1 vote" in line
        assert "votes" not in line.replace("1 vote", "")

    def test_percentage_shown(self) -> None:
        line = _format_option_line("X", 1, 2)  # 50%
        assert "50%" in line


class TestBuildPollEmbed:
    def test_question_in_title(self) -> None:
        embed = build_poll_embed("Cats or Dogs?", ["Cats", "Dogs"], {})
        assert "Cats or Dogs?" in embed.title

    def test_active_embed_blurple(self) -> None:
        embed = build_poll_embed("Q?", ["A", "B"], {})
        assert embed.color == discord.Color.blurple()

    def test_closed_embed_greyple(self) -> None:
        embed = build_poll_embed("Q?", ["A", "B"], {}, closed=True)
        assert embed.color == discord.Color.greyple()

    def test_active_footer_has_time(self) -> None:
        embed = build_poll_embed("Q?", ["A", "B"], {}, seconds_remaining=120.0)
        assert "120" in embed.footer.text

    def test_closed_footer_text(self) -> None:
        embed = build_poll_embed("Q?", ["A", "B"], {}, closed=True)
        assert "closed" in embed.footer.text.lower()

    def test_options_in_description(self) -> None:
        embed = build_poll_embed("Q?", ["Red", "Blue"], {})
        assert "Red" in embed.description
        assert "Blue" in embed.description

    def test_vote_counts_reflected(self) -> None:
        # user 1 and 2 both voted option 0 (Red)
        votes = {"1": 0, "2": 0}
        embed = build_poll_embed("Q?", ["Red", "Blue"], votes)
        assert "2 votes" in embed.description


# ---------------------------------------------------------------------------
# PollsPlugin command tests
# ---------------------------------------------------------------------------

class TestPollCreate:
    async def test_creates_embed_and_stores_poll(self, tmp_path) -> None:
        p = _plugin(tmp_path)
        ctx = _ctx()

        await p.poll(ctx, "Cats or dogs?", "Cats", "Dogs")

        ctx.respond.assert_called_once()
        _, kwargs = ctx.respond.call_args
        assert isinstance(kwargs.get("embed"), discord.Embed)

        # Verify storage
        cfg = await p._store.load(100)
        polls = cfg.get_other("polls", {})
        assert len(polls) == 1
        data = next(iter(polls.values()))
        assert data["question"] == "Cats or dogs?"
        assert data["options"] == ["Cats", "Dogs"]
        assert data["status"] == "active"
        assert "votes" in data
        assert data["votes"] == {}

    async def test_registers_view_on_bot(self, tmp_path) -> None:
        p = _plugin(tmp_path)
        ctx = _ctx()

        await p.poll(ctx, "Q?", "Yes", "No")

        p._bot.add_view.assert_called_once()

    async def test_schedules_timer(self, tmp_path) -> None:
        p = _plugin(tmp_path)
        ctx = _ctx()

        await p.poll(ctx, "Q?", "A", "B", duration=30)

        assert any(p._timers.values()), "Expected a timer task to be scheduled"

    async def test_guild_isolated_storage(self, tmp_path) -> None:
        p = _plugin(tmp_path)

        ctx_a = _ctx(guild_id=100)
        ctx_b = _ctx(guild_id=200)

        # Use different fake message IDs so they don't collide
        msg_a = MagicMock()
        msg_a.id = 1001
        msg_a.edit = AsyncMock()
        ctx_a.interaction.original_response = AsyncMock(return_value=msg_a)

        msg_b = MagicMock()
        msg_b.id = 2001
        msg_b.edit = AsyncMock()
        ctx_b.interaction.original_response = AsyncMock(return_value=msg_b)

        await p.poll(ctx_a, "Guild A poll", "Yes", "No")
        await p.poll(ctx_b, "Guild B poll", "Red", "Blue")

        cfg_a = await p._store.load(100)
        cfg_b = await p._store.load(200)

        polls_a = cfg_a.get_other("polls", {})
        polls_b = cfg_b.get_other("polls", {})

        assert len(polls_a) == 1
        assert len(polls_b) == 1
        assert next(iter(polls_a.values()))["question"] == "Guild A poll"
        assert next(iter(polls_b.values()))["question"] == "Guild B poll"

    async def test_less_than_two_options_rejected(self, tmp_path) -> None:
        p = _plugin(tmp_path)
        ctx = _ctx()

        # Only one non-empty option provided
        await p.poll(ctx, "Solo?", "Only", "", "", "", "")

        ctx.respond.assert_called_once()
        _, kwargs = ctx.respond.call_args
        assert kwargs.get("ephemeral") is True

    async def test_zero_options_rejected(self, tmp_path) -> None:
        p = _plugin(tmp_path)
        ctx = _ctx()

        await p.poll(ctx, "Empty?", "", "")

        ctx.respond.assert_called_once()
        _, kwargs = ctx.respond.call_args
        assert kwargs.get("ephemeral") is True

    async def test_duration_below_minimum_rejected(self, tmp_path) -> None:
        p = _plugin(tmp_path)
        ctx = _ctx()

        await p.poll(ctx, "Q?", "A", "B", duration=4)

        ctx.respond.assert_called_once()
        _, kwargs = ctx.respond.call_args
        assert kwargs.get("ephemeral") is True

    async def test_no_guild_returns_early(self, tmp_path) -> None:
        p = _plugin(tmp_path)
        ctx = _ctx()
        ctx.guild = None

        await p.poll(ctx, "Q?", "A", "B")

        ctx.respond.assert_not_called()

    async def test_non_sendable_channel_rejected(self, tmp_path) -> None:
        p = _plugin(tmp_path)
        ctx = _ctx(is_sendable=False)

        await p.poll(ctx, "Q?", "A", "B")

        ctx.respond.assert_called_once()
        _, kwargs = ctx.respond.call_args
        assert kwargs.get("ephemeral") is True

    async def test_five_options_accepted(self, tmp_path) -> None:
        p = _plugin(tmp_path)
        ctx = _ctx()

        await p.poll(ctx, "Which?", "A", "B", "C", "D", "E")

        # Should succeed without ephemeral error
        ctx.respond.assert_called_once()
        _, kwargs = ctx.respond.call_args
        assert kwargs.get("ephemeral") is not True

    async def test_default_duration_is_60(self, tmp_path) -> None:
        p = _plugin(tmp_path)
        ctx = _ctx()

        await p.poll(ctx, "Q?", "A", "B")

        cfg = await p._store.load(100)
        polls = cfg.get_other("polls", {})
        data = next(iter(polls.values()))
        end_time = datetime.fromisoformat(data["end_time"])
        now = datetime.now(timezone.utc)
        remaining = (end_time - now).total_seconds()
        assert 55 <= remaining <= 65, f"Expected ~60s remaining, got {remaining:.1f}s"

    async def test_ctx_t_called_for_error_message(self, tmp_path) -> None:
        p = _plugin(tmp_path)
        ctx = _ctx()

        await p.poll(ctx, "Q?", "", "")  # triggers min_options error

        ctx.t.assert_called()

    async def test_stored_end_time_is_isoformat(self, tmp_path) -> None:
        p = _plugin(tmp_path)
        ctx = _ctx()

        await p.poll(ctx, "Q?", "X", "Y", duration=120)

        cfg = await p._store.load(100)
        polls = cfg.get_other("polls", {})
        data = next(iter(polls.values()))
        # Should not raise
        datetime.fromisoformat(data["end_time"])


# ---------------------------------------------------------------------------
# _close_poll logic (timer expiry path)
# ---------------------------------------------------------------------------

class TestClosePoll:
    async def test_marks_poll_closed_in_store(self, tmp_path) -> None:
        p = _plugin(tmp_path)
        await _seed_active_poll(p, guild_id=100, message_id=42)

        # Isolate _close_poll from Discord API side effects
        guild_mock = MagicMock()
        channel_mock = MagicMock(spec=discord.TextChannel)
        msg_mock = MagicMock()
        msg_mock.edit = AsyncMock()
        channel_mock.fetch_message = AsyncMock(return_value=msg_mock)
        guild_mock.get_channel = MagicMock(return_value=channel_mock)
        p._bot.get_guild = MagicMock(return_value=guild_mock)

        await p._close_poll(100, 42)

        cfg = await p._store.load(100)
        polls = cfg.get_other("polls", {})
        assert polls["42"]["status"] == "closed"

    async def test_close_already_closed_is_noop(self, tmp_path) -> None:
        p = _plugin(tmp_path)
        await _seed_active_poll(p, guild_id=100, message_id=99)

        # Close it once
        p._bot.get_guild = MagicMock(return_value=None)
        await p._close_poll(100, 99)

        # Close again — should not raise or alter other data
        await p._close_poll(100, 99)

        cfg = await p._store.load(100)
        assert cfg.get_other("polls", {})["99"]["status"] == "closed"

    async def test_close_unknown_poll_is_noop(self, tmp_path) -> None:
        p = _plugin(tmp_path)
        # No poll seeded — should return silently
        await p._close_poll(100, 9999)

    async def test_close_removes_timer_entry(self, tmp_path) -> None:
        p = _plugin(tmp_path)
        await _seed_active_poll(p, guild_id=100, message_id=77)

        # Manually plant a fake timer task
        fake_task = MagicMock()
        p._timers[100] = {77: fake_task}

        p._bot.get_guild = MagicMock(return_value=None)
        await p._close_poll(100, 77)

        assert 77 not in p._timers.get(100, {})

    async def test_close_edits_message_with_closed_embed(self, tmp_path) -> None:
        p = _plugin(tmp_path)
        await _seed_active_poll(
            p,
            guild_id=100,
            message_id=55,
            question="Pick one",
            options=["Alpha", "Beta"],
            votes={"1": 0},
        )
        guild_mock = MagicMock()
        channel_mock = MagicMock(spec=discord.TextChannel)
        msg_mock = MagicMock()
        msg_mock.edit = AsyncMock()
        channel_mock.fetch_message = AsyncMock(return_value=msg_mock)
        guild_mock.get_channel = MagicMock(return_value=channel_mock)
        p._bot.get_guild = MagicMock(return_value=guild_mock)

        await p._close_poll(100, 55)

        msg_mock.edit.assert_called_once()
        call_kwargs = msg_mock.edit.call_args.kwargs
        embed = call_kwargs.get("embed")
        assert embed is not None
        assert embed.color == discord.Color.greyple()  # closed colour


# ---------------------------------------------------------------------------
# Vote tallying and results calculation
# ---------------------------------------------------------------------------

class TestVoteResults:
    def test_winner_is_option_with_most_votes(self) -> None:
        options = ["Red", "Green", "Blue"]
        votes = {"1": 0, "2": 0, "3": 2, "4": 0}  # Red=3, Blue=1
        counts = _tally(options, votes)
        winner_idx = counts.index(max(counts))
        assert options[winner_idx] == "Red"

    def test_tie_represented_in_counts(self) -> None:
        options = ["A", "B"]
        votes = {"1": 0, "2": 1}
        counts = _tally(options, votes)
        assert counts == [1, 1]

    def test_total_votes_match_voter_count(self) -> None:
        options = ["X", "Y", "Z"]
        votes = {"1": 0, "2": 1, "3": 2, "4": 0, "5": 1}
        counts = _tally(options, votes)
        assert sum(counts) == len(votes)

    def test_no_votes_all_zero(self) -> None:
        options = ["A", "B", "C"]
        counts = _tally(options, {})
        assert counts == [0, 0, 0]


# ---------------------------------------------------------------------------
# Duplicate vote guard (via _PollView callback internals via store)
# ---------------------------------------------------------------------------

class TestDuplicateVoteGuard:
    async def test_same_user_vote_overwrites_not_duplicates(self, tmp_path) -> None:
        """Votes are stored by user-id key; a repeat vote replaces, not appends."""
        p = _plugin(tmp_path)
        await _seed_active_poll(
            p,
            guild_id=100,
            message_id=10,
            options=["A", "B"],
            votes={"42": 0},   # user 42 already voted for option 0 (A)
        )

        # Simulate user 42 changing their vote to option 1 (B)
        async with p._guild_lock(100):
            cfg = await p._store.load(100)
            polls = cfg.get_other("polls", {})
            polls["10"]["votes"]["42"] = 1
            cfg.set_other("polls", polls)
            await p._store.save(cfg)

        cfg = await p._store.load(100)
        votes = cfg.get_other("polls", {})["10"]["votes"]
        assert votes == {"42": 1}, "Should have exactly one entry for user 42"
        counts = _tally(["A", "B"], votes)
        assert counts == [0, 1], "Only the updated vote should count"

    async def test_two_users_get_distinct_entries(self, tmp_path) -> None:
        p = _plugin(tmp_path)
        await _seed_active_poll(p, guild_id=100, message_id=11, options=["X", "Y"])

        async with p._guild_lock(100):
            cfg = await p._store.load(100)
            polls = cfg.get_other("polls", {})
            polls["11"]["votes"]["1"] = 0
            polls["11"]["votes"]["2"] = 1
            cfg.set_other("polls", polls)
            await p._store.save(cfg)

        cfg = await p._store.load(100)
        votes = cfg.get_other("polls", {})["11"]["votes"]
        assert len(votes) == 2
        counts = _tally(["X", "Y"], votes)
        assert counts == [1, 1]


# ---------------------------------------------------------------------------
# on_unload cancels timers
# ---------------------------------------------------------------------------

class TestOnUnload:
    async def test_unload_cancels_all_timers(self, tmp_path) -> None:
        p = _plugin(tmp_path)

        task_a = MagicMock()
        task_b = MagicMock()
        p._timers = {100: {1: task_a}, 200: {2: task_b}}

        await p.on_unload()

        task_a.cancel.assert_called_once()
        task_b.cancel.assert_called_once()
        assert p._timers == {}
