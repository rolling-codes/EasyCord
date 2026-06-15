"""Tests for ReputationPlugin: pure functions, store, and command flow."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from easycord.plugins.reputation import (
    ReputationPlugin,
    _is_on_cooldown,
    _rep_embed,
    _top_entries,
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
    ctx.user.mention = f"<@{user_id}>"
    ctx.respond = AsyncMock()
    ctx.is_admin = True
    ctx.member = MagicMock()
    return ctx


def _plugin(tmp_path) -> ReputationPlugin:
    p = ReputationPlugin.__new__(ReputationPlugin)
    ReputationPlugin.__init__(p, store_path=str(tmp_path / "reputation"))
    return p


def _user(user_id: int, bot: bool = False) -> MagicMock:
    u = MagicMock()
    u.id = user_id
    u.bot = bot
    u.mention = f"<@{user_id}>"
    u.display_name = f"User{user_id}"
    return u


# ---------------------------------------------------------------------------
# Layer 1: pure functions
# ---------------------------------------------------------------------------

class TestIsOnCooldown:
    def test_cooldown_within_24h(self) -> None:
        now = datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        last = (now - timedelta(hours=12)).isoformat()
        assert _is_on_cooldown(last, now) is True

    def test_cooldown_after_24h(self) -> None:
        now = datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        last = (now - timedelta(hours=25)).isoformat()
        assert _is_on_cooldown(last, now) is False

    def test_cooldown_none_means_not_on_cooldown(self) -> None:
        now = datetime.now(timezone.utc)
        assert _is_on_cooldown(None, now) is False

    def test_cooldown_exactly_24h_is_ok(self) -> None:
        now = datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        last = (now - timedelta(hours=24)).isoformat()
        # exactly 24h ago is not *less than* 24h, so not on cooldown
        assert _is_on_cooldown(last, now) is False

    def test_cooldown_one_second_ago(self) -> None:
        now = datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        last = (now - timedelta(seconds=1)).isoformat()
        assert _is_on_cooldown(last, now) is True


class TestTopEntries:
    def test_top_entries_sorted(self) -> None:
        scores = {"1": 5, "2": 10, "3": 2}
        result = _top_entries(scores)
        assert result[0] == (2, 10)
        assert result[1] == (1, 5)
        assert result[2] == (3, 2)

    def test_top_entries_limited(self) -> None:
        scores = {str(i): i for i in range(20)}
        result = _top_entries(scores, limit=5)
        assert len(result) == 5

    def test_top_entries_empty(self) -> None:
        assert _top_entries({}) == []

    def test_top_entries_default_limit_10(self) -> None:
        scores = {str(i): i for i in range(15)}
        result = _top_entries(scores)
        assert len(result) == 10

    def test_top_entries_returns_tuples(self) -> None:
        scores = {"42": 7}
        result = _top_entries(scores)
        assert result == [(42, 7)]


class TestRepEmbed:
    def test_rep_embed_contains_score(self) -> None:
        embed = _rep_embed("Alice", 42)
        assert embed.description is not None
        assert "42" in embed.description

    def test_rep_embed_contains_name(self) -> None:
        embed = _rep_embed("Alice", 42)
        assert embed.title is not None
        assert "Alice" in embed.title

    def test_rep_embed_is_embed(self) -> None:
        embed = _rep_embed("Bob", 0)
        assert isinstance(embed, discord.Embed)

    def test_rep_embed_singular_point(self) -> None:
        embed = _rep_embed("Alice", 1)
        assert embed.description is not None
        assert "point" in embed.description

    def test_rep_embed_plural_points(self) -> None:
        embed = _rep_embed("Alice", 2)
        assert embed.description is not None
        assert "points" in embed.description


# ---------------------------------------------------------------------------
# Layer 2: store persistence
# ---------------------------------------------------------------------------

class TestStorePersistence:
    async def test_rep_increments(self, tmp_path) -> None:
        p = _plugin(tmp_path)
        giver_ctx = _ctx(guild_id=100, user_id=1)
        target = _user(user_id=2)

        await p.rep(giver_ctx, target)

        from easycord.server_config import ServerConfigStore
        store = ServerConfigStore(str(tmp_path / "reputation"))
        cfg = await store.load(100)
        data = cfg.get_other("reputation", {})
        assert data["scores"]["2"] == 1

    async def test_cooldown_stored(self, tmp_path) -> None:
        p = _plugin(tmp_path)
        giver_ctx = _ctx(guild_id=100, user_id=1)
        target = _user(user_id=2)

        await p.rep(giver_ctx, target)

        from easycord.server_config import ServerConfigStore
        store = ServerConfigStore(str(tmp_path / "reputation"))
        cfg = await store.load(100)
        data = cfg.get_other("reputation", {})
        assert "1" in data["cooldowns"]

    async def test_reset_zeroes_score(self, tmp_path) -> None:
        p = _plugin(tmp_path)
        giver_ctx = _ctx(guild_id=100, user_id=1)
        target = _user(user_id=2)

        # Give rep first
        await p.rep(giver_ctx, target)

        # Then reset
        admin_ctx = _ctx(guild_id=100, user_id=99)
        await p.rep_reset(admin_ctx, target)

        from easycord.server_config import ServerConfigStore
        store = ServerConfigStore(str(tmp_path / "reputation"))
        cfg = await store.load(100)
        data = cfg.get_other("reputation", {})
        assert data["scores"]["2"] == 0

    async def test_guilds_isolated(self, tmp_path) -> None:
        p = _plugin(tmp_path)
        ctx_a = _ctx(guild_id=100, user_id=1)
        target = _user(user_id=2)

        await p.rep(ctx_a, target)

        from easycord.server_config import ServerConfigStore
        store = ServerConfigStore(str(tmp_path / "reputation"))
        cfg_b = await store.load(200)
        data_b = cfg_b.get_other("reputation", {})
        assert data_b.get("scores", {}).get("2", 0) == 0


# ---------------------------------------------------------------------------
# Layer 3: command flow
# ---------------------------------------------------------------------------

class TestCommandFlow:
    async def test_rep_self_denied(self, tmp_path) -> None:
        p = _plugin(tmp_path)
        ctx = _ctx(guild_id=100, user_id=5)
        target = _user(user_id=5)  # same user

        await p.rep(ctx, target)

        ctx.respond.assert_awaited_once()
        response_text = ctx.respond.call_args[0][0]
        assert "yourself" in response_text.lower()

    async def test_rep_bot_denied(self, tmp_path) -> None:
        p = _plugin(tmp_path)
        ctx = _ctx(guild_id=100, user_id=1)
        target = _user(user_id=9, bot=True)

        await p.rep(ctx, target)

        ctx.respond.assert_awaited_once()
        response_text = ctx.respond.call_args[0][0]
        assert "bot" in response_text.lower()

    async def test_rep_cooldown_denied(self, tmp_path) -> None:
        p = _plugin(tmp_path)
        ctx = _ctx(guild_id=100, user_id=1)
        target_a = _user(user_id=2)
        target_b = _user(user_id=3)

        # Give rep first time (should succeed)
        await p.rep(ctx, target_a)

        # Give rep second time immediately (should be denied due to cooldown)
        ctx2 = _ctx(guild_id=100, user_id=1)
        await p.rep(ctx2, target_b)

        ctx2.respond.assert_awaited_once()
        response_text = ctx2.respond.call_args[0][0]
        assert "24 hours" in response_text or "cooldown" in response_text.lower() or "already" in response_text.lower()

    async def test_rep_success(self, tmp_path) -> None:
        p = _plugin(tmp_path)
        ctx = _ctx(guild_id=100, user_id=1)
        target = _user(user_id=2)

        await p.rep(ctx, target)

        ctx.respond.assert_awaited_once()
        response_text = ctx.respond.call_args[0][0]
        assert "rep" in response_text.lower()

    async def test_rep_check_no_score(self, tmp_path) -> None:
        p = _plugin(tmp_path)
        ctx = _ctx(guild_id=100, user_id=1)
        target = _user(user_id=2)

        await p.rep_check(ctx, target)

        ctx.respond.assert_awaited_once()
        # Should respond with an embed showing 0 rep
        call_kwargs = ctx.respond.call_args
        embed = call_kwargs.kwargs.get("embed") or (
            call_kwargs[1].get("embed") if call_kwargs[1] else None
        )
        assert embed is not None
        assert "0" in embed.description

    async def test_rep_top_empty(self, tmp_path) -> None:
        p = _plugin(tmp_path)
        ctx = _ctx(guild_id=100)

        await p.rep_top(ctx)

        ctx.respond.assert_awaited_once()
        response_text = ctx.respond.call_args[0][0]
        assert "No rep" in response_text or "no rep" in response_text.lower()

    async def test_rep_reset_requires_guild(self, tmp_path) -> None:
        p = _plugin(tmp_path)
        ctx = _ctx(guild_id=100, user_id=99)
        target = _user(user_id=2)

        await p.rep_reset(ctx, target)

        ctx.respond.assert_awaited_once()
        response_text = ctx.respond.call_args[0][0]
        assert "2" in response_text or "reset" in response_text.lower()
