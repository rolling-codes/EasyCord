# EasyCord v5.51.0 Release Notes

**Date:** July 1, 2026

## Overview

Stability release focusing on CRITICAL bug fixes in core plugins and framework Optional member access patterns.

## Critical Fixes

1. **OpenClaw Optional narrowing** — 7 sites where `ctx.guild` and `self.orchestrator` were accessed without guards in guild-only commands.
2. **Scheduled announcements resilience** — Loop now survives permission errors on `ch.send()` instead of terminating.
3. **Context channel access** — Added guards in giveaway, polls, reminder before accessing `ctx.channel.id`.
4. **Tickets button view** — Handle DM interactions gracefully in persistent view button.
5. **Three live plugin bugs** — Fixed Feb 29 crash (birthday), reversed transcript (tickets), missing role rewards (levels).
6. **Starboard dead-on-arrival config** (B-018) — `cfg.get("enabled")` without a default treated a missing key as disabled; a guild that only ran `/starboard_channel` never got a working starboard. Fixed with `cfg.get("enabled", True)`.

## Test Coverage

- 1335 tests total (up from 1301); flat >=20-test-per-plugin CI floor
- All CI gates passing: ruff, pytest, plugin coverage, release metadata

## Known Deferred Issues (v5.52.0)

- Auto-responder TOCTOU refactor (requires mutate contract rework)
- LocalizationManager thread-safety (metrics atomicity with threading.Lock)
- Hot-reload command dispatch race (architectural: requires dispatch-side lock)
- on_ready exception logging (4 plugins: exception swallowing silently)

## Installation

```bash
pip install --upgrade easycord==5.51.0
```

Distributed as:
- `releases/download/v5.51.0/easycord-5.51.0-py3-none-any.whl`
- `releases/download/v5.51.0/easycord-5.51.0.tar.gz`

## Upgrade Notes

No breaking changes. Drop-in update from v5.50.2.
