# Implementation Plan — v5.51.0 Critical Bug Fixes

Durable record of the "Stability" round driven by the forensic audit in
`EasyCord_Improvement_Plan/` (`AUDIT_FINDINGS.md`, `EASYCORD_IMPROVEMENT_PLAN.md`).
Baseline audited at v5.50.2.

## The four "critical" bugs — verified against source before fixing

| # | Bug | Verified status | Action taken |
|---|-----|-----------------|--------------|
| 1 | `LocalizationManager` metrics not thread-safe | Real — non-atomic `+=` on `_metrics`; docstring admitted "NOT thread-safe" | Fixed with an internal `threading.Lock` |
| 2 | Hot-reload ↔ command-dispatch race | Real — `remove_plugin → add_plugin → on_reload` ran unlocked | Fixed with a bot-wide `asyncio` reload lock |
| 3 | Dispatch validates user perms only, not the bot's | Real — destructive moderation commands didn't even declare perms | Fixed with opt-in `bot_permissions=` checked at dispatch |
| 4 | Component regex compiled on-demand (jitter) | **Already fixed in v5.50.2** — regex is compiled at registration | Regression test only; no code change |

## Two corrections to the audit's suggested fixes

- **Bug #1 — use `threading.Lock`, not `asyncio.Lock`.** `LocalizationManager.get()`
  is synchronous, so it can't `await`. The real failure mode is OS-thread
  concurrency (sharded bots running shards on separate threads), which a
  `threading.Lock` addresses; an `asyncio.Lock` would not even be usable here.
- **Bug #3 — separate `bot_permissions=`, not reuse of `permissions=`.** Reusing the
  user-permission list for the bot would force the bot to be **administrator** for
  every `require_admin=True` command (a regression). A distinct, opt-in
  `bot_permissions=` declaration avoids that and changes nothing for existing
  commands.

## What changed

**Fix 1 — `easycord/i18n.py`**
- Added `self._metrics_lock = threading.Lock()` and a `_record_metric(field, locale=None)`
  helper that performs the locked read-modify-write. All inline `_metrics[...] += 1`
  sites in `get()` now go through it; `get_metrics()` / `reset_metrics()` take the lock
  for consistent snapshots/resets. Lock is only taken when `track_metrics=True`.

**Fix 2 — `easycord/_bot_plugins.py` + `easycord/_command_callbacks.py`**
- Bot-wide `_reload_lock` (lazily created via `_get_reload_lock()`). `_hot_reload_plugin`
  holds it across the whole swap. `_hot_reload_loop` sets `_hot_reload_active = True`.
- `build_slash_callback` acquires the lock around dispatch **only when**
  `_hot_reload_active` — production (no dev watcher) keeps a lock-free fast path.

**Fix 3 — `bot_permissions=`** (decorator → registration chain → dispatch)
- `easycord/decorators.py` `@slash(bot_permissions=[...])` → `func._slash_bot_permissions`.
- Threaded through `_plugin_scanner.py`, `_bot_commands.py` (`slash`, `_register_slash`,
  `_build_slash_callback`), and `_command_registration.py` into `build_slash_callback`.
- `build_slash_callback` checks `ctx.bot_permissions` after the user-permission block and
  replies ephemerally with `errors.bot_permissions_missing` ("I'm missing …") when the bot
  lacks a perm. Existing commands (no `bot_permissions`) are untouched.
- `_validate_plugin_permissions` folds `_slash_bot_permissions` into its startup warning.
- Retrofitted the destructive built-ins in `easycord/plugins/moderation.py`:
  `kick`/`ban`/`unban` → `ban`/`kick_members`, `timeout` → `moderate_members`,
  `mute`/`unmute` → `manage_roles`.

**Incidental** — `pyproject.toml` had an invalid bare-`*` TOML key under
`[tool.setuptools.exclude-package-data]` that broke every TOML reader (pytest could not
start). Quoted to `"*"`. Pre-existing, unrelated to the audit.

**Type-checking cleanup** (follow-up pass)
- `_command_registration.py` and `_plugin_scanner.py` typed their `bot`/`plugin` params as
  `object`, producing ~40 spurious `reportAttributeAccessIssue` errors (`.tree`, `.registry`,
  `.event_bus`, `plugin.id()`, …). Retyped them as `_BotBase` / `Plugin` under `TYPE_CHECKING`
  (the pattern `_bot_base.py` documents), and added the missing `event_bus` to `_BotBase`.
  TYPE_CHECKING-only — zero runtime change; suite stays at 1213 passed.
- `reportFunctionMemberAccess` set to `"warning"` in `pyrightconfig.json` — the decorator
  system stamps attributes onto functions by design, so these were never real errors.
- Net: `pyright easycord` went from 85+ errors to 40 (all pre-existing, in untouched files;
  5 are optional AI-provider SDKs); every file changed in this round reports 0 pyright errors.
- Note: the IDE "`Import \"easycord\" could not be resolved`" errors are a VS Code
  workspace-root issue (the open workspace is a different project), not a repo defect —
  `pyright`/imports resolve cleanly from the EasyCord-main root.

## Tests added
- `tests/test_i18n.py::TestMetricsThreadSafety` — concurrent metric updates lose nothing.
- `tests/test_hot_reload.py` — reload lock is idempotent, held across the swap, and the
  dev loop activates the dispatch gate.
- `tests/test_permission_validator.py::TestBotPermissionsDispatch` — bot-perm missing
  blocks the command (ephemeral) and runs it when present; no-`bot_permissions` unchanged.
- `tests/test_registry_component.py` — regex is eagerly compiled at registration (bug #4
  guard) and resolution doesn't recompile; strict TTL boundary with a mocked clock.

## Verification

- `python -m pytest tests/ -q` → 1307 passed.
- `ruff check` clean on all changed files.
- `pyright` introduces no new error categories (the lone `_slash_bot_permissions`
  `reportFunctionMemberAccess` matches the existing `_slash_*` stamping pattern).

## Release v5.51.0

Version bump and CHANGELOG.md updated. Release tagged and published to PyPI.
Additional bug fixes from forensic audit (B-008 through B-017) included with test coverage.

## Out of scope (deferred — see EASYCORD_IMPROVEMENT_PLAN.md later phases)

Medium-risk gaps: `auto_sync_guilds` startup timeout, cooldown-pruning memory growth,
ConversationMemory eviction policy, database schema validation.
