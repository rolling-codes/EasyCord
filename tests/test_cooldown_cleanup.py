from __future__ import annotations

import time
import warnings

import easycord.bot as bot_module


def _make_bot() -> bot_module.Bot:
    return bot_module.Bot(auto_sync=False, db_backend="memory")


def test_prune_removes_expired_and_keeps_valid() -> None:
    bot = _make_bot()
    now = time.monotonic()
    cooldown_dict: dict[int, list[float]] = {
        1: [now - 100.0],          # expired (window 10s)
        2: [now - 1.0],            # still valid
        3: [now - 100.0, now - 1.0],  # one expired, one valid
    }
    bot._cooldown_registries.append((cooldown_dict, 10.0))

    bot._prune_cooldown_registries(now)

    assert 1 not in cooldown_dict          # fully expired key dropped
    assert cooldown_dict[2] == [now - 1.0]
    assert cooldown_dict[3] == [now - 1.0]  # expired timestamp pruned


def test_prune_tolerates_key_removed_during_iteration() -> None:
    """A command callback may pop a bucket key between the key snapshot and
    the per-key access. The prune pass must not raise KeyError for it."""

    class ConcurrentlyMutatingDict(dict):
        def keys(self):  # type: ignore[override]
            # Report a key that is not actually present, simulating a key that
            # was popped by another coroutine after the snapshot was taken.
            return [*super().keys(), 999]

    bot = _make_bot()
    now = time.monotonic()
    cooldown_dict = ConcurrentlyMutatingDict({1: [now - 100.0]})
    bot._cooldown_registries.append((cooldown_dict, 10.0))

    # Must not raise even though key 999 vanishes between snapshot and access.
    bot._prune_cooldown_registries(now)

    assert 999 not in cooldown_dict
    assert 1 not in cooldown_dict  # the real expired key was still pruned


def test_prune_one_bad_registry_does_not_abort_the_rest() -> None:
    """If one registry raises, later registries must still be pruned so a
    single bad entry can't silently disable all cooldown cleanup."""

    class ExplodingDict(dict):
        def keys(self):  # type: ignore[override]
            raise RuntimeError("boom")

    bot = _make_bot()
    now = time.monotonic()
    good_dict: dict[int, list[float]] = {1: [now - 100.0]}
    bot._cooldown_registries.append((ExplodingDict(), 10.0))
    bot._cooldown_registries.append((good_dict, 10.0))

    # Should not propagate; the healthy registry still gets pruned.
    bot._prune_cooldown_registries(now)

    assert 1 not in good_dict


# ---------------------------------------------------------------------------
# REQ-03: cooldown sweep cleanup (plan 01-03)
# ---------------------------------------------------------------------------


async def test_cooldown_callback_emits_no_deprecation_warning() -> None:
    """BUG (fixed, regression guard): build_slash_callback used the deprecated
    asyncio.get_event_loop() to schedule its sweep task, which raises
    DeprecationWarning under ``-W error::DeprecationWarning`` when called from
    a running event loop. Building a cooldown-decorated slash callback under a
    running loop must be deprecation-clean."""
    bot = _make_bot()
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", DeprecationWarning)

            @bot.slash(description="cooldown deprecation guard", cooldown=5.0)
            async def cooled_cmd(ctx):
                await ctx.respond("ok")
    finally:
        for task in list(bot._background_tasks):
            task.cancel()
        await bot.close()


async def test_cooldown_callback_schedules_no_per_callback_sweep() -> None:
    """BUG: every cooldown-decorated command scheduled its own
    _cooldown_sweep_loop background task, duplicating the bot-level
    _cooldown_cleanup_loop that already prunes the same dict via
    bot._cooldown_registries. Exactly one sweep mechanism must remain:
    registering a cooldown command adds its registry for the bot-level loop
    but must NOT spawn a per-callback background task."""
    bot = _make_bot()
    try:
        tasks_before = set(bot._background_tasks)
        registries_before = len(bot._cooldown_registries)

        @bot.slash(description="no per-callback sweep", cooldown=5.0)
        async def swept_cmd(ctx):
            await ctx.respond("ok")

        new_tasks = set(bot._background_tasks) - tasks_before
        try:
            assert new_tasks == set(), (
                "cooldown registration must not spawn a per-callback sweep task"
            )
            # The bot-level cleanup loop covers this dict instead.
            assert len(bot._cooldown_registries) == registries_before + 1
        finally:
            for task in new_tasks:
                task.cancel()
    finally:
        await bot.close()


def test_cooldown_max_entries_default() -> None:
    """The registry cap constant exists with the agreed default (50k)."""
    assert bot_module._COOLDOWN_MAX_ENTRIES == 50_000


def test_prune_evicts_oldest_buckets_over_cap(monkeypatch) -> None:
    """BUG: _prune_cooldown_registries had no max-entries cap, so a flood of
    distinct bucket keys (user-keyed buckets are attacker-influenceable) could
    grow a registry without bound within the cooldown window. Once a registry
    exceeds _COOLDOWN_MAX_ENTRIES, the oldest buckets — smallest
    max(timestamps) — must be evicted down to the cap."""
    monkeypatch.setattr(bot_module, "_COOLDOWN_MAX_ENTRIES", 3, raising=False)
    bot = _make_bot()
    now = time.monotonic()
    window = 1000.0  # nothing here is expired; only the cap applies
    cooldown_dict: dict[str, list[float]] = {
        "a": [now - 100.0],
        "b": [now - 900.0, now - 10.0],  # ancient ts, but max is newest: survives
        "c": [now - 50.0],
        "d": [now - 200.0],
        "e": [now - 30.0],
    }
    bot._cooldown_registries.append((cooldown_dict, window))

    bot._prune_cooldown_registries(now)

    assert set(cooldown_dict) == {"b", "c", "e"}, (
        "oldest buckets by max(timestamps) must be evicted first"
    )


def test_prune_cap_applies_after_normal_expiry(monkeypatch) -> None:
    """Expiry pruning runs first; the cap only evicts from what remains."""
    monkeypatch.setattr(bot_module, "_COOLDOWN_MAX_ENTRIES", 2, raising=False)
    bot = _make_bot()
    now = time.monotonic()
    window = 10.0
    cooldown_dict: dict[str, list[float]] = {
        "expired": [now - 100.0],  # dropped by normal expiry, not the cap
        "y": [now - 5.0],
        "z": [now - 3.0],
        "w": [now - 1.0],
    }
    bot._cooldown_registries.append((cooldown_dict, window))

    bot._prune_cooldown_registries(now)

    assert set(cooldown_dict) == {"z", "w"}


def test_prune_no_eviction_at_or_below_cap(monkeypatch) -> None:
    """A registry at or below the cap is left untouched by the cap logic."""
    monkeypatch.setattr(bot_module, "_COOLDOWN_MAX_ENTRIES", 2, raising=False)
    bot = _make_bot()
    now = time.monotonic()
    cooldown_dict: dict[str, list[float]] = {
        "y": [now - 5.0],
        "w": [now - 1.0],
    }
    bot._cooldown_registries.append((cooldown_dict, 1000.0))

    bot._prune_cooldown_registries(now)

    assert set(cooldown_dict) == {"y", "w"}


async def test_remove_plugin_prunes_cooldown_registry() -> None:
    """Cooldown registry entry removed from bot._cooldown_registries on plugin unload."""
    from easycord import Plugin
    from easycord.decorators import slash as slash_decorator

    class _CoolPlugin(Plugin):
        @slash_decorator(description="test cooldown cmd", cooldown=5.0)
        async def cool_cmd(self, ctx):
            await ctx.respond("ok")

    bot = _make_bot()
    plugin = _CoolPlugin()
    bot.add_plugin(plugin)
    assert len(bot._cooldown_registries) == 1

    await bot.remove_plugin(plugin)
    assert len(bot._cooldown_registries) == 0

    await bot.close()


async def test_remove_slash_group_prunes_cooldown_registry() -> None:
    """Cooldown registry entries on grouped commands are removed on unload."""
    from easycord import SlashGroup
    from easycord.decorators import slash as slash_decorator

    class _CoolGroup(SlashGroup, name="cool", description="Cool commands"):
        @slash_decorator(description="test group cooldown cmd", cooldown=5.0)
        async def ping(self, ctx):
            await ctx.respond("ok")

    bot = _make_bot()
    group = _CoolGroup()
    bot.add_plugin(group)
    assert len(bot._cooldown_registries) == 1

    await bot.remove_plugin(group)
    assert len(bot._cooldown_registries) == 0

    await bot.close()
