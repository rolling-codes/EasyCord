---
phase: 01-verified-bug-fixes
plan: 04
subsystem: extensibility
tags: [event-bus, observability, plugin-unload, regression-tests]
requires: []
provides:
  - EventBus listener-order contract documented in subscribe/publish docstrings
  - Regression tests locking handler-identity error logs (sync + async)
  - Regression test locking registration-order invocation
  - Regression test locking context-menu unload debug logs
affects: []
tech-stack:
  added: []
  patterns: [caplog-based log assertions, TestBugs-style regression docstrings]
key-files:
  created: []
  modified:
    - easycord/event_bus.py
    - tests/test_event_bus.py
    - tests/test_hot_reload.py
decisions:
  - "Re-scoped to regression-test-only for handler identity and unload debug logs — PR #77 had already landed both code fixes (verify-first rule)"
  - "easycord/_bot_plugins.py left untouched: both context-menu branches already logger.debug"
metrics:
  duration: ~10 minutes
  completed: 2026-07-11
status: complete
---

# Phase 1 Plan 04: EventBus / Unload Observability Summary

**One-liner:** Documented EventBus registration-order invocation in subscribe/publish docstrings and locked the already-landed PR #77 observability fixes (handler `__qualname__` in error logs, context-menu unload debug logs) with four caplog-based regression tests.

## What Was Done

### Task 1: Verify the finding
Per the locked verify-first rule, confirmed against HEAD (58a021c):
- `event_bus.py:75` ALREADY logs `getattr(callback, "__qualname__", repr(callback))` — publish() was also simplified from gather() to sequential await, so the (callback, coro) pairing described in the plan no longer applies.
- `_bot_plugins.py` user-command branch (~156) and message-command branch (~165) ALREADY `logger.debug("Could not remove user/message command %r during unload", ...)` — no bare `except: pass` remains.
- Docstrings did NOT document listener invocation order — still open.

Both code sub-findings degraded to regression-test-only per the phase context rule.

### Task 2: Docstrings + regression tests
- `easycord/event_bus.py` (commit 012f9b2): `subscribe` docstring now states same-event callbacks fire in registration order; `publish` docstring states listeners run sequentially in registration order and that a raising callback is logged with its `__qualname__` without stopping later callbacks.
- `tests/test_event_bus.py` (commit 2928787): three new tests —
  - `test_publish_sync_failure_log_names_handler` — raising sync subscriber's `__qualname__` appears in the ERROR log (caplog).
  - `test_publish_async_failure_log_names_handler` — same for an async subscriber.
  - `test_listeners_fire_in_registration_order` — four mixed sync/async handlers record call order into a shared list; asserted equal to subscribe order.
- `tests/test_hot_reload.py` (commit 2928787): `test_unload_context_menu_removal_failure_emits_debug_log` — plugin with `@user_command` + `@message_command`, `tree.remove_command` patched to raise; asserts DEBUG records naming both commands and that `remove_plugin` completes without raising.

No wall-clock assertions. All regression tests carry TestBugs-style docstrings naming REQ-04 and the guarded bug.

## Deviations from Plan

**1. [Re-scope — verify-first] Handler identity + unload debug logs already fixed by PR #77**
- **Found during:** Task 1
- **Issue:** Plan assumed both code fixes were open; live verification showed both landed.
- **Fix:** Degraded to regression-test-only (as the plan's own Task 1 instructs). `easycord/_bot_plugins.py` intentionally untouched.
- **Commit:** 2928787 (tests only)

**2. [TDD RED skipped by design]** The four new tests pass against HEAD on first run — expected, since the behaviors under test already exist. Verified in Task 1 that each behavior is genuinely present in current code, so passing RED is the correct regression-lock outcome, not an unvalidated test.

**3. [State files not updated]** STATE.md/ROADMAP.md/REQUIREMENTS.md updates skipped: five executors share one working tree this wave and the orchestrator instructed staging only owned files. Orchestrator should reconcile REQ-04 traceability after the wave.

## Verification

- `python -m pytest tests/test_event_bus.py tests/test_hot_reload.py -q` — **37 passed** (33 baseline + 4 new).
- `ruff check <owned files> --select E9,F63,F7,F82` — clean.
- `grep -c "__qualname__" easycord/event_bus.py` = 2 (code + docstring) >= 1.
- No bare `pass` remains on the two context-menu removal branches (pre-existing via PR #77).
- Ownership check: only `easycord/event_bus.py`, `tests/test_event_bus.py`, `tests/test_hot_reload.py` modified; bot.py untouched.

## Commits

| Commit | Type | Content |
|--------|------|---------|
| 012f9b2 | docs | Listener-order notes in subscribe/publish docstrings |
| 2928787 | test | 4 regression tests (handler identity x2, order, unload debug logs) |

## Self-Check: PASSED

- easycord/event_bus.py modified: FOUND
- tests/test_event_bus.py extended: FOUND
- tests/test_hot_reload.py extended: FOUND
- Commit 012f9b2: FOUND
- Commit 2928787: FOUND
