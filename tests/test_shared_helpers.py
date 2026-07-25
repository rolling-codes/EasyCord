"""Tests for easycord/plugins/_shared.py typed config accessors and respond_error."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

from easycord.plugins._shared import (
    GuildLockManager,
    MAX_TRACKED_GUILDS,
    get_id,
    get_ids,
    respond_error,
    set_id,
    set_ids,
)
from easycord.server_config import ServerConfig


def _cfg() -> ServerConfig:
    return ServerConfig(guild_id=1)


# ---------------------------------------------------------------------------
# get_id
# ---------------------------------------------------------------------------

def test_get_id_returns_int_for_stored_int():
    cfg = _cfg()
    cfg.set_other("channel", 555)
    assert get_id(cfg, "channel") == 555


def test_get_id_coerces_string_to_int():
    cfg = _cfg()
    cfg.set_other("channel", "777")
    assert get_id(cfg, "channel") == 777


def test_get_id_returns_none_for_missing_key():
    assert get_id(_cfg(), "missing") is None


def test_get_id_returns_none_for_none_value():
    cfg = _cfg()
    cfg.set_other("channel", None)
    assert get_id(cfg, "channel") is None


def test_get_id_returns_none_for_non_coercible_value():
    cfg = _cfg()
    cfg.set_other("channel", "not-a-number")
    assert get_id(cfg, "channel") is None


def test_get_id_returns_none_for_float_string():
    cfg = _cfg()
    cfg.set_other("channel", "3.14")
    assert get_id(cfg, "channel") is None


def test_get_id_returns_int_type():
    cfg = _cfg()
    cfg.set_other("role", "123")
    result = get_id(cfg, "role")
    assert isinstance(result, int)


# ---------------------------------------------------------------------------
# set_id
# ---------------------------------------------------------------------------

def test_set_id_stores_int():
    cfg = _cfg()
    set_id(cfg, "role", 123)
    assert cfg.get_other("role") == 123


def test_set_id_value_is_int_type():
    cfg = _cfg()
    set_id(cfg, "role", 456)
    assert isinstance(cfg.get_other("role"), int)


def test_set_id_none_removes_key():
    cfg = _cfg()
    cfg.set_other("role", 123)
    set_id(cfg, "role", None)
    assert not cfg.has_other("role")


def test_set_id_none_on_missing_key_is_noop():
    cfg = _cfg()
    set_id(cfg, "never_set", None)
    assert not cfg.has_other("never_set")


def test_set_id_get_id_round_trip():
    cfg = _cfg()
    set_id(cfg, "log_channel", 888)
    assert get_id(cfg, "log_channel") == 888


def test_set_id_overwrite():
    cfg = _cfg()
    set_id(cfg, "channel", 111)
    set_id(cfg, "channel", 222)
    assert get_id(cfg, "channel") == 222


# ---------------------------------------------------------------------------
# get_ids
# ---------------------------------------------------------------------------

def test_get_ids_returns_list_of_ints():
    cfg = _cfg()
    cfg.set_other("roles", [1, 2, 3])
    assert get_ids(cfg, "roles") == [1, 2, 3]


def test_get_ids_coerces_string_items():
    cfg = _cfg()
    cfg.set_other("roles", ["10", "20", "30"])
    assert get_ids(cfg, "roles") == [10, 20, 30]


def test_get_ids_returns_empty_for_missing_key():
    assert get_ids(_cfg(), "missing") == []


def test_get_ids_returns_empty_for_none_value():
    cfg = _cfg()
    cfg.set_other("roles", None)
    assert get_ids(cfg, "roles") == []


def test_get_ids_returns_empty_for_non_list_value():
    cfg = _cfg()
    cfg.set_other("roles", "not-a-list")
    assert get_ids(cfg, "roles") == []


def test_get_ids_skips_non_coercible_items():
    cfg = _cfg()
    cfg.set_other("roles", [1, "bad", 3])
    assert get_ids(cfg, "roles") == [1, 3]


def test_get_ids_accepts_tuple():
    cfg = _cfg()
    cfg.set_other("roles", (10, 20))
    assert get_ids(cfg, "roles") == [10, 20]


def test_get_ids_result_is_list():
    cfg = _cfg()
    cfg.set_other("roles", [1])
    assert isinstance(get_ids(cfg, "roles"), list)


# ---------------------------------------------------------------------------
# set_ids
# ---------------------------------------------------------------------------

def test_set_ids_stores_list():
    cfg = _cfg()
    set_ids(cfg, "roles", [100, 200])
    assert cfg.get_other("roles") == [100, 200]


def test_set_ids_round_trip_with_get_ids():
    cfg = _cfg()
    set_ids(cfg, "roles", [11, 22, 33])
    assert get_ids(cfg, "roles") == [11, 22, 33]


def test_set_ids_stores_ints():
    cfg = _cfg()
    set_ids(cfg, "roles", [1, 2, 3])
    assert all(isinstance(v, int) for v in cfg.get_other("roles"))


def test_set_ids_empty_list():
    cfg = _cfg()
    set_ids(cfg, "roles", [])
    assert cfg.get_other("roles") == []


# ---------------------------------------------------------------------------
# respond_error
# ---------------------------------------------------------------------------

async def test_respond_error_calls_respond_ephemeral():
    ctx = MagicMock()
    ctx.respond = AsyncMock()
    await respond_error(ctx, "Something went wrong.")
    ctx.respond.assert_called_once_with("Something went wrong.", ephemeral=True)


async def test_respond_error_passes_message_verbatim():
    ctx = MagicMock()
    ctx.respond = AsyncMock()
    await respond_error(ctx, "Access denied.")
    args, kwargs = ctx.respond.call_args
    assert args[0] == "Access denied."
    assert kwargs.get("ephemeral") is True


async def test_respond_error_sets_ephemeral_true():
    ctx = MagicMock()
    ctx.respond = AsyncMock()
    await respond_error(ctx, "Error.")
    _, kwargs = ctx.respond.call_args
    assert kwargs["ephemeral"] is True


async def test_respond_error_returns_none():
    ctx = MagicMock()
    ctx.respond = AsyncMock(return_value=None)
    result = await respond_error(ctx, "Oops.")
    assert result is None


# ---------------------------------------------------------------------------
# GuildLockManager eviction
# ---------------------------------------------------------------------------


def test_cleanup_removes_idle_locks_older_than_7_days():
    """Locks idle for more than 7 days are deleted from both _registry and _created."""
    mgr = GuildLockManager()
    mgr.lock(1)  # create entry for guild 1
    # Backdate creation timestamp so it looks 8 days old.
    mgr._created[1] = datetime.now(timezone.utc) - timedelta(days=8)
    mgr._cleanup()
    assert 1 not in mgr._registry
    assert 1 not in mgr._created


def test_cleanup_does_not_remove_recently_created_locks():
    """Locks created recently (within 7 days) are kept."""
    mgr = GuildLockManager()
    mgr.lock(42)
    mgr._cleanup()
    assert 42 in mgr._registry


async def test_cleanup_does_not_remove_held_idle_locks():
    """A lock that is currently held must not be evicted, even if old."""
    mgr = GuildLockManager()
    lock = mgr.lock(99)
    # Backdate it as if it were 10 days old.
    mgr._created[99] = datetime.now(timezone.utc) - timedelta(days=10)

    async with lock:
        # Lock is held — cleanup should leave it alone.
        mgr._cleanup()
        assert 99 in mgr._registry


def test_cleanup_evicts_oldest_25_percent_when_over_cap():
    """When registry exceeds MAX_TRACKED_GUILDS, oldest 25% of idle entries are evicted."""
    import asyncio

    mgr = GuildLockManager()

    # Bypass the per-lock call to _cleanup() inside lock() so we can build
    # the full set first, then trigger a single controlled cleanup.
    total = MAX_TRACKED_GUILDS + 1
    for i in range(total):
        mgr._registry[i] = asyncio.Lock()
        mgr._created[i] = datetime.now(timezone.utc) - timedelta(seconds=i)

    before = len(mgr._registry)
    assert before == total  # sanity

    mgr._cleanup()

    # At least one entry should have been evicted.
    assert len(mgr._registry) < before


def test_cleanup_evicts_at_least_one_entry_over_cap():
    """remove_count = max(1, len(candidates)//4) guarantees at least one eviction."""
    import asyncio

    mgr = GuildLockManager()
    # Create exactly MAX_TRACKED_GUILDS + 1 entries so eviction fires.
    for i in range(MAX_TRACKED_GUILDS + 1):
        mgr._registry[i] = asyncio.Lock()
        mgr._created[i] = datetime.now(timezone.utc) - timedelta(seconds=i)

    mgr._cleanup()
    assert len(mgr._registry) <= MAX_TRACKED_GUILDS
