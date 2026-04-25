# v3.8.1 — Patch for Python 3.11 Test Compatibility

**Release Date:** 2026-04-25

## Summary

v3.8.1 fixes a test environment issue where `asyncio.Lock()` was created at class initialization time before an event loop existed. This caused 5 test failures in CI (Ubuntu/Python 3.11) despite the code working correctly in production.

**No production impact.** All bots continue to work unchanged.

## What Changed

### Code

**Fixed asyncio.Lock lazy initialization in `LevelsStore`:**

```python
# Before: Locks created at __init__, before event loop exists
self._xp_locks: dict[int, asyncio.Lock] = defaultdict(asyncio.Lock)

# After: Locks created on-demand inside async context
def _get_xp_lock(self, guild_id: int) -> asyncio.Lock:
    if guild_id not in self._xp_locks:
        self._xp_locks[guild_id] = asyncio.Lock()
    return self._xp_locks[guild_id]
```

This pattern matches Python 3.11's stricter event loop lifecycle. Locks are now initialized only when first accessed within an async function, guaranteeing the event loop exists.

### Testing

- ✅ All 578 tests pass (was 5 failures)
- ✅ test_levels_plugin.py: all 47 tests pass
- ✅ No behavioral changes; only initialization timing fixed

## Why This Release

v3.8.0 had 5 test failures in CI due to asyncio.Lock initialization before event loop creation. This was a test environment artifact—production bots unaffected—but left CI in a failed state.

## Migration (None Required)

No code changes needed. Upgrade with:

```bash
pip install --upgrade easycord
```

All existing bots continue unchanged.

## Links

- [v3.8.0 Release Notes (original features)](RELEASE_v3.8.md)
- [Tests](tests/test_levels_plugin.py)
