"""Tests for the guild_sync_timeout parameter on Bot and BotConfig.

TDD: these tests are written BEFORE the implementation and must initially fail.
"""
from __future__ import annotations

import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock

from easycord import Bot, BotConfig


# ---------------------------------------------------------------------------
# Helper: build a minimal mock db that works with setup_hook
# ---------------------------------------------------------------------------

def _make_mock_db(sync_guilds_side_effect=None):
    db = MagicMock()
    db.auto_sync_guilds = True
    db.ensure_schema = AsyncMock()
    db.close = AsyncMock()
    if sync_guilds_side_effect is not None:
        db.sync_guilds = AsyncMock(side_effect=sync_guilds_side_effect)
    else:
        db.sync_guilds = AsyncMock()
    return db


# ---------------------------------------------------------------------------
# 1. Bot constructor stores guild_sync_timeout
# ---------------------------------------------------------------------------

async def test_bot_stores_guild_sync_timeout_default() -> None:
    bot = Bot(auto_sync=False, db_backend="memory")
    try:
        assert bot._guild_sync_timeout == 30.0
    finally:
        await bot.close()


async def test_bot_stores_custom_guild_sync_timeout() -> None:
    bot = Bot(auto_sync=False, db_backend="memory", guild_sync_timeout=5.0)
    try:
        assert bot._guild_sync_timeout == 5.0
    finally:
        await bot.close()


async def test_bot_stores_none_guild_sync_timeout() -> None:
    bot = Bot(auto_sync=False, db_backend="memory", guild_sync_timeout=None)
    try:
        assert bot._guild_sync_timeout is None
    finally:
        await bot.close()


async def test_bot_stores_zero_guild_sync_timeout() -> None:
    # <=0 means no timeout (opt-out)
    bot = Bot(auto_sync=False, db_backend="memory", guild_sync_timeout=0.0)
    try:
        assert bot._guild_sync_timeout == 0.0
    finally:
        await bot.close()


# ---------------------------------------------------------------------------
# 2. Timeout path: slow sync is abandoned and a warning is logged
# ---------------------------------------------------------------------------

async def test_setup_hook_sync_timeout_logs_warning_and_continues(caplog) -> None:
    """When sync_guilds is slow and timeout fires, startup continues (no raise)."""

    async def slow_sync(guild_ids):
        await asyncio.sleep(10)  # longer than the tiny test timeout

    db = _make_mock_db(sync_guilds_side_effect=slow_sync)
    bot = Bot(auto_sync=False, database=db, guild_sync_timeout=0.05)
    bot.tree.sync = AsyncMock()
    try:
        with caplog.at_level(logging.WARNING, logger="easycord"):
            await bot.setup_hook()

        # Must not raise — startup continued
        # A warning must have been emitted
        messages = [r.getMessage() for r in caplog.records]
        assert any("timed out" in msg.lower() or "timeout" in msg.lower() for msg in messages), (
            f"Expected a timeout warning; got: {messages}"
        )
    finally:
        await bot.close()


async def test_on_ready_sync_timeout_logs_warning_and_continues(caplog) -> None:
    """Same guarantee for on_ready's call site."""

    async def slow_sync(guild_ids):
        await asyncio.sleep(10)

    db = _make_mock_db(sync_guilds_side_effect=slow_sync)
    bot = Bot(auto_sync=False, database=db, guild_sync_timeout=0.05)
    try:
        with caplog.at_level(logging.WARNING, logger="easycord"):
            await bot.on_ready()

        messages = [r.getMessage() for r in caplog.records]
        assert any("timed out" in msg.lower() or "timeout" in msg.lower() for msg in messages), (
            f"Expected a timeout warning; got: {messages}"
        )
    finally:
        await bot.close()


# ---------------------------------------------------------------------------
# 3. No-timeout path: sync runs to completion when timeout is None or <=0
# ---------------------------------------------------------------------------

async def test_setup_hook_no_timeout_sync_completes() -> None:
    """With guild_sync_timeout=None, sync_guilds runs to completion."""
    db = _make_mock_db()
    bot = Bot(auto_sync=False, database=db, guild_sync_timeout=None)
    bot.tree.sync = AsyncMock()
    try:
        await bot.setup_hook()
        db.sync_guilds.assert_awaited_once()
    finally:
        await bot.close()


async def test_on_ready_no_timeout_sync_completes() -> None:
    """With guild_sync_timeout=0 (opt-out), sync_guilds runs to completion."""
    db = _make_mock_db()
    bot = Bot(auto_sync=False, database=db, guild_sync_timeout=0.0)
    try:
        await bot.on_ready()
        db.sync_guilds.assert_awaited_once()
    finally:
        await bot.close()


# ---------------------------------------------------------------------------
# 4. Elapsed time is bounded by the timeout (not the slow duration)
# ---------------------------------------------------------------------------

async def test_setup_hook_sync_timeout_is_bounded() -> None:
    """Total elapsed during setup_hook must be well under the slow sleep duration."""
    import time

    async def slow_sync(guild_ids):
        await asyncio.sleep(10)

    db = _make_mock_db(sync_guilds_side_effect=slow_sync)
    bot = Bot(auto_sync=False, database=db, guild_sync_timeout=0.1)
    bot.tree.sync = AsyncMock()
    try:
        start = time.monotonic()
        await bot.setup_hook()
        elapsed = time.monotonic() - start
        # Should finish in well under 1 second, not 10 seconds
        assert elapsed < 2.0, f"Expected fast exit due to timeout; elapsed={elapsed:.2f}s"
    finally:
        await bot.close()


# ---------------------------------------------------------------------------
# 5. BotConfig: guild_sync_timeout field and env-var plumbing
# ---------------------------------------------------------------------------

def test_botconfig_default_guild_sync_timeout() -> None:
    cfg = BotConfig(token="token")
    assert cfg.guild_sync_timeout == 30.0


def test_botconfig_explicit_guild_sync_timeout() -> None:
    cfg = BotConfig(token="token", guild_sync_timeout=60.0)
    assert cfg.guild_sync_timeout == 60.0


def test_botconfig_none_guild_sync_timeout() -> None:
    cfg = BotConfig(token="token", guild_sync_timeout=None)
    assert cfg.guild_sync_timeout is None


def test_botconfig_from_env_reads_guild_sync_timeout(monkeypatch) -> None:
    monkeypatch.setenv("DISCORD_TOKEN", "tok")
    monkeypatch.setenv("EASYCORD_GUILD_SYNC_TIMEOUT", "45.5")
    cfg = BotConfig.from_env()
    assert cfg.guild_sync_timeout == 45.5


def test_botconfig_from_env_guild_sync_timeout_missing_uses_default(monkeypatch) -> None:
    monkeypatch.setenv("DISCORD_TOKEN", "tok")
    monkeypatch.delenv("EASYCORD_GUILD_SYNC_TIMEOUT", raising=False)
    cfg = BotConfig.from_env()
    assert cfg.guild_sync_timeout == 30.0


async def test_botconfig_build_bot_passes_guild_sync_timeout() -> None:
    cfg = BotConfig(token="token", guild_sync_timeout=15.0)
    bot = cfg.build_bot(auto_sync=False, db_backend="memory")
    try:
        assert bot._guild_sync_timeout == 15.0
    finally:
        await bot.close()
