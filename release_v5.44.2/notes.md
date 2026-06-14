## EasyCord v5.44.2 - 2026-06-14

Patch release: four bug fixes uncovered by a new stress-test suite, plus type-safety improvements across `BaseContext` and `LevelsPlugin`.

### Fixed

- **`ToolLimiter._cleanup_usage` `KeyError`** — cleanup path called `del self._usage[key[0]]` (an `int`) instead of `del self._usage[key]` (the `(user_id, tool_name)` tuple key). Raised unconditionally once `MAX_TRACKED_ENTRIES` (10 000) was exceeded.
- **`EconomyPlugin` lock eviction race** — `_cleanup_old_locks` measured lock age from creation time, never refreshed on subsequent accesses. On a long-running bot an active guild's lock was evicted and replaced with a fresh unacquired lock while a coroutine still held the original, silently bypassing per-guild write serialization and opening a concurrent-save race on balances. Fixed by refreshing `_lock_created[guild_id]` on every `_balance_lock()` call and skipping acquired locks in cleanup.
- **`progress_bar()` overflow** — `filled` was unclamped, so XP values above the next-level ceiling produced strings longer than `width`. Added `min(width, max(0, …))` clamp.
- **`Range` inverted bounds** — `Range(min=5, max=3)` constructed silently. Added `__post_init__` that raises `ValueError` immediately when `min > max`.
- **`BaseContext` Pylance errors** — `respond()` and `dm()` passed `embed=None`/positional `content` to discord.py overloaded functions. Both now build a `msg_kwargs` dict and omit keys when `None`. `send_embed()` passes `timestamp=ts` directly instead of using a conditional dict-unpack. `forward()` annotates the `Messageable` / `MessageableChannel` mismatch with `type: ignore[arg-type]`.
- **`LevelsPlugin` type narrowing** — replaced `hasattr(message.author, "add_roles")` with `isinstance(message.author, discord.Member)` so Pylance correctly narrows `User | Member` to `Member`.

### Tests

- 94 new tests in `tests/test_stress.py` (regression guards for all four bugs, levels-XP math invariants, full validator coverage, `ConversationMemory` edge cases). Total: 634 tests.

### Assets
- https://github.com/rolling-codes/EasyCord/releases/download/v5.44.2/easycord-5.44.2-py3-none-any.whl
- https://github.com/rolling-codes/EasyCord/releases/download/v5.44.2/easycord-5.44.2.tar.gz

### Verification
- `python scripts/check_release_metadata.py` - passed.
- `pytest tests/` - 634 passed.
- `ruff check easycord tests --select E9,F63,F7,F82` - passed.
