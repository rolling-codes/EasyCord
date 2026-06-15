"""Concurrency and load stress tests for EasyCord framework subsystems.

Exercises shared mutable state under asyncio concurrent load.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from easycord.conversation_memory import ConversationMemory
from easycord.i18n import LocalizationManager
from easycord.middleware import build_chain, rate_limit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ctx(user_id: int = 1, guild_id: int | None = 100) -> MagicMock:
    ctx = MagicMock()
    ctx.user = MagicMock()
    ctx.user.id = user_id
    ctx.guild = MagicMock() if guild_id is not None else None
    if ctx.guild is not None:
        ctx.guild.id = guild_id
    ctx.respond = AsyncMock()
    ctx.t = lambda key, default="", **kw: default.format(**kw) if kw else default
    ctx.command_name = "test_cmd"
    ctx.channel = MagicMock()
    ctx.channel.id = 9999
    return ctx


# ---------------------------------------------------------------------------
# A. rate_limit closure — concurrent load
# ---------------------------------------------------------------------------

class TestRateLimitConcurrency:
    """rate_limit closure holds _history without a lock.

    In asyncio, the GIL + cooperative scheduling prevents true data races,
    but these tests verify correctness invariants under high concurrency.
    """

    @pytest.mark.asyncio
    async def test_same_user_at_most_limit_pass(self) -> None:
        """100 concurrent calls from the same user: at most `limit` proceed."""
        mw = rate_limit(limit=5, window=60.0)
        passed = 0

        async def inner() -> None:
            nonlocal passed
            passed += 1

        async def run_one(ctx: MagicMock) -> None:
            await build_chain(ctx, inner, [mw])()

        ctxs = [_ctx(user_id=42) for _ in range(100)]
        await asyncio.gather(*[run_one(c) for c in ctxs])
        assert passed <= 5

    @pytest.mark.asyncio
    async def test_multi_user_independent_limits(self) -> None:
        """20 users × 5 calls each — each user limited independently."""
        mw = rate_limit(limit=2, window=60.0)
        passed = 0

        async def inner() -> None:
            nonlocal passed
            passed += 1

        ctxs = [_ctx(user_id=uid) for uid in range(20) for _ in range(5)]
        await asyncio.gather(*[build_chain(c, inner, [mw])() for c in ctxs])

        # 20 users × 2 each = 40 max; at least 1 per user must pass
        assert passed <= 40
        assert passed >= 20

    @pytest.mark.asyncio
    async def test_no_exception_under_burst_load(self) -> None:
        """50 concurrent calls across 5 users must not raise any exception."""
        mw = rate_limit(limit=3, window=2.0)
        ctxs = [_ctx(user_id=i % 5) for i in range(50)]
        await asyncio.gather(*[
            build_chain(c, AsyncMock(), [mw])()
            for c in ctxs
        ])

    @pytest.mark.asyncio
    async def test_rate_limit_invalid_limit_raises(self) -> None:
        with pytest.raises(ValueError, match="limit"):
            rate_limit(limit=0)

    @pytest.mark.asyncio
    async def test_rate_limit_invalid_window_raises(self) -> None:
        with pytest.raises(ValueError, match="window"):
            rate_limit(limit=1, window=0.0)

    @pytest.mark.asyncio
    async def test_respond_called_when_limited(self) -> None:
        """A rate-limited request responds with an error message."""
        mw = rate_limit(limit=1, window=60.0)
        proceed_mock = AsyncMock()
        ctx = _ctx(user_id=99)

        # First call passes
        await build_chain(ctx, proceed_mock, [mw])()
        assert proceed_mock.call_count == 1

        # Second call is rate-limited
        await build_chain(ctx, proceed_mock, [mw])()
        assert proceed_mock.call_count == 1  # didn't proceed again
        ctx.respond.assert_called()  # responded with limit message


# ---------------------------------------------------------------------------
# B. ConversationMemory — eviction and load
# ---------------------------------------------------------------------------

class TestConversationMemoryLoad:
    """ConversationMemory eviction path exercises dict iteration + deletion."""

    @pytest.mark.asyncio
    async def test_eviction_stays_within_cap(self) -> None:
        """Creating beyond capacity keeps total ≤ max_conversations."""
        mem = ConversationMemory(max_conversations=50)
        for i in range(75):
            mem.get_or_create(user_id=i, guild_id=1)
        assert len(mem._conversations) <= 50

    @pytest.mark.asyncio
    async def test_same_key_returns_same_object(self) -> None:
        """Repeated get_or_create for the same key returns the same conv."""
        mem = ConversationMemory(max_conversations=100)
        first = mem.get_or_create(user_id=7, guild_id=42)
        for _ in range(20):
            result = mem.get_or_create(user_id=7, guild_id=42)
            assert result is first

    @pytest.mark.asyncio
    async def test_cleanup_expired_removes_old_conversations(self) -> None:
        """cleanup_expired removes conversations whose last_updated is past TTL."""
        mem = ConversationMemory(max_conversations=100, default_max_age_minutes=60)
        for i in range(20):
            mem.get_or_create(user_id=i, guild_id=1)

        past = datetime.now(timezone.utc) - timedelta(hours=2)
        for conv in mem._conversations.values():
            conv.last_updated = past

        removed = mem.cleanup_expired()
        assert removed == 20
        assert len(mem._conversations) == 0

    @pytest.mark.asyncio
    async def test_cleanup_expired_no_false_removals(self) -> None:
        """cleanup_expired leaves fresh conversations untouched."""
        mem = ConversationMemory(max_conversations=100, default_max_age_minutes=60)
        for i in range(10):
            mem.get_or_create(user_id=i, guild_id=1)

        removed = mem.cleanup_expired()
        assert removed == 0
        assert len(mem._conversations) == 10

    @pytest.mark.asyncio
    async def test_sequential_eviction_no_exception(self) -> None:
        """Filling past capacity repeatedly must not raise RuntimeError."""
        mem = ConversationMemory(max_conversations=10)
        for i in range(100):
            mem.get_or_create(user_id=i, guild_id=None)
        # Should not raise; count bounded
        assert len(mem._conversations) <= 10

    @pytest.mark.asyncio
    async def test_add_messages_to_eviction_survivors(self) -> None:
        """Conversations that survive eviction are still usable."""
        mem = ConversationMemory(max_conversations=5)
        for i in range(5):
            c = mem.get_or_create(user_id=i, guild_id=1)
            c.add_turn("user", f"hello from {i}")

        # Add 5 more — evicts the oldest 5
        for i in range(5, 10):
            mem.get_or_create(user_id=i, guild_id=1)

        # The surviving conversations should still be valid
        for conv in mem._conversations.values():
            assert isinstance(conv.user_id, int)

    @pytest.mark.asyncio
    async def test_stats_consistent_after_eviction(self) -> None:
        """get_stats() reflects actual count after eviction."""
        mem = ConversationMemory(max_conversations=5)
        for i in range(20):
            mem.get_or_create(user_id=i, guild_id=1)
        stats = mem.get_stats()
        assert stats["total_conversations"] <= 5


# ---------------------------------------------------------------------------
# C. LocalizationManager — metric counters under load
# ---------------------------------------------------------------------------

class TestLocalizationManagerLoad:
    """LocalizationManager._metrics uses non-atomic +=.

    These tests verify no crash under sequential call volume
    and that counter semantics are correct.
    """

    def _make_lm(self) -> LocalizationManager:
        lm = LocalizationManager(default_locale="en-US", track_metrics=True)
        lm.register("en-US", {"greeting": "Hello", "farewell": "Goodbye"})
        return lm

    @pytest.mark.asyncio
    async def test_cache_hits_tracked(self) -> None:
        """cache_hits increments for every successful lookup."""
        lm = self._make_lm()
        for _ in range(200):
            lm.get("greeting", locale="en-US")
        metrics = lm.get_metrics()
        assert metrics["cache_hits"] == 200

    @pytest.mark.asyncio
    async def test_cache_misses_tracked(self) -> None:
        """Missing key increments missing_keys counter each time."""
        lm = self._make_lm()
        for _ in range(50):
            lm.get("no_such_key", locale="en-US")
        metrics = lm.get_metrics()
        assert metrics["missing_keys"] == 50

    @pytest.mark.asyncio
    async def test_fallback_resolution_tracked(self) -> None:
        """Key missing in user locale but found in default increments fallback_resolution."""
        lm = LocalizationManager(default_locale="en-US", track_metrics=True)
        lm.register("en-US", {"greeting": "Hello"})
        for _ in range(10):
            lm.get("greeting", locale="fr-FR")
        metrics = lm.get_metrics()
        assert metrics["fallback_resolution"] == 10

    @pytest.mark.asyncio
    async def test_reset_metrics_zeros_all_counters(self) -> None:
        """reset_metrics() sets all counters to zero."""
        lm = self._make_lm()
        for _ in range(10):
            lm.get("greeting", locale="en-US")
            lm.get("missing", locale="en-US")
        lm.reset_metrics()
        metrics = lm.get_metrics()
        assert metrics["cache_hits"] == 0
        assert metrics["cache_misses"] == 0
        assert metrics["missing_keys"] == 0

    @pytest.mark.asyncio
    async def test_locale_frequency_bounded(self) -> None:
        """locale_frequency dict stays within max_tracked_locales."""
        lm = LocalizationManager(
            default_locale="en-US",
            track_metrics=True,
            max_tracked_locales=5,
        )
        lm.register("en-US", {"k": "v"})
        for i in range(20):
            lm.register(f"xx-{i:02d}", {"k": f"value_{i}"})
            lm.get("k", locale=f"xx-{i:02d}")
        metrics = lm.get_metrics()
        freq = metrics["locale_frequency"]
        assert isinstance(freq, dict) and len(freq) <= 5

    @pytest.mark.asyncio
    async def test_no_exception_on_empty_catalog(self) -> None:
        """get() with no catalogs registered returns the default."""
        lm = LocalizationManager(default_locale="en-US", track_metrics=False)
        result = lm.get("some_key", default="fallback")
        assert result == "fallback"

    @pytest.mark.asyncio
    async def test_get_returns_default_when_key_missing(self) -> None:
        lm = self._make_lm()
        result = lm.get("nonexistent", locale="en-US", default="my_default")
        assert result == "my_default"
