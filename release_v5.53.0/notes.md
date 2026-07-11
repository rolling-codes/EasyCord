# EasyCord v5.53.0 — Framework Hardening Phase 1

## Overview

Phase 1 of the v5.53 Framework Hardening roadmap. Five tasks landed:
verified-open bug fixes with full regression coverage, cooldown architecture
cleanup, and EventBus observability improvements.

## What's in this release

### Bug fixes

- **B-007** — Invite cache leaked memory across guild removals; now pruned in
  `_on_guild_remove`.
- **B-015** — `_grant_level_reward` caught `Forbidden` only; `HTTPException`
  parent class now caught so all Discord errors are handled.
- **B-016** — `auto_role` post-sleep `add_roles` failed silently on `NotFound`
  and generic `HTTPException`; both now absorbed.

### Architecture improvements

- Single bot-level `_cooldown_cleanup_loop` replaces per-callback sweep tasks
  (which were unreliable at import time). A `_COOLDOWN_MAX_ENTRIES=50_000` hard
  cap with oldest-bucket eviction prevents unbounded growth.
- Cooldown registry entry is now stored on the built callback and removed from
  `bot._cooldown_registries` when the owning plugin is unloaded via
  `remove_plugin` — previously these entries were permanent zombies.

### Regression net (new tests)

1513 tests total (+75 from v5.52.0):
- `test_bot_permissions_adoption.py` — 16 tests (B-021 structural guard)
- `test_cli_scaffold.py` — scaffold collision regression
- `test_cooldown_cleanup.py` — 10 tests (expiry, cap eviction, lifecycle)
- `test_event_bus.py` extensions — EventBus observability
- `test_p1_bug_sweep.py` — B-007/B-015/B-016 regressions

## Upgrade notes

No breaking changes. Drop-in upgrade from v5.52.0.

## Install

```
pip install easycord==5.53.0
```

## Artifacts

- `easycord-5.53.0-py3-none-any.whl`
- `easycord-5.53.0.tar.gz`
