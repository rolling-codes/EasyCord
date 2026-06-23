from __future__ import annotations

import time

from easycord.bot import Bot


def _make_bot() -> Bot:
    return Bot(auto_sync=False, db_backend="memory")


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
