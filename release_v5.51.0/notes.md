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

## Test Coverage

- 1307 tests total (up from 1301)
- All CI gates passing: ruff, pytest, plugin coverage, release metadata

## Known Deferred Issues

- Tags concurrent write safety (v5.52.0)
- Auto-responder TOCTOU fix (v5.52.0)
- LocalizationManager thread-safety (v5.52.0)
- Hot-reload command dispatch race (v5.52.0)

## Installation

```bash
pip install --upgrade easycord==5.51.0
```

Distributed as:
- `releases/download/v5.51.0/easycord-5.51.0-py3-none-any.whl`
- `releases/download/v5.51.0/easycord-5.51.0.tar.gz`

## Upgrade Notes

No breaking changes. Drop-in update from v5.50.2.
