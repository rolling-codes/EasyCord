# Phase 1: Verified bug fixes - Context

**Gathered:** 2026-07-08
**Status:** Ready for planning
**Source:** PRD Express Path (.planning/IMPORTED-PLAN.md — user-approved hardening plan)

<domain>
## Phase Boundary

Close every verified-open defect in the EasyCord framework, each fix landing with its own named regression test in the same task (TDD-atomic). Findings come from live-code verification done 2026-07-08 — NOT from the stale audit docs. Anything discovered already-fixed degrades to regression-test-only. No structural refactors (lock consolidation is Phase 4), no test backfill for untested modules (Phase 2), no stress suites (Phase 3).

</domain>

<decisions>
## Implementation Decisions

### Task/plan decomposition (locked — 5 plans, 1 wave, exclusive file ownership)
- Plan 01-01: `bot_permissions` adoption across 9 privileged plugins — tickets, reaction_roles, verification, word_filter, welcome, giveaway, polls, starboard, member_logging (NOT auto_role — that belongs to 01-05). Mirror the existing pattern in `easycord/plugins/moderation.py:127-350`. Mechanism already exists at `easycord/_command_callbacks.py:179-206` (`bot_permissions` param, `ctx.bot_permissions`, localized error). Permission mapping: tickets→manage_channels; reaction_roles/verification→manage_roles; word_filter→manage_messages; giveaway/polls/starboard→send_messages/add_reactions where applicable; member_logging/welcome→channel-send paths. New test file: `tests/test_bot_permissions_adoption.py` using `FakeContextBuilder.with_permissions()` driving `ctx.bot_permissions`.
- Plan 01-02: CLI scaffold collision fix in `easycord/cli.py` — (a) generated pyproject at cli.py:101-102 gains `testpaths = ["tests"]`; (b) `_module_name` rejects or renames modules matching `test_*`/`*_test` with a clear warning (e.g. prefix `bot_`). New test file: `tests/test_cli_scaffold.py`; also keep `tests/test_plugin_creator.py` green.
- Plan 01-03: Cooldown sweep cleanup — owns BOTH `easycord/_command_callbacks.py` AND `easycord/bot.py`. (a) Replace deprecated `asyncio.get_event_loop()` at `_command_callbacks.py:87` with `asyncio.get_running_loop()` in try/except; (b) drop the redundant per-callback sweep task in favor of the bot-level `_cooldown_cleanup_loop` (registries already appended to `bot._cooldown_registries` at line ~74) — or dedupe if drop is unsafe; (c) add a max-entries cap with oldest-bucket eviction (e.g. 50k) to `_prune_cooldown_registries` in bot.py. Extend `tests/test_cooldown_cleanup.py`. Verify runs with `-W error::DeprecationWarning`.
- Plan 01-04: Observability — `easycord/event_bus.py` publish logs gain handler identity (`getattr(callback, "__qualname__", repr(callback))`; keep (callback, coro) pairs so gather results map back to handlers); `easycord/_bot_plugins.py:156-163` — replace the two silent `except Exception: pass` context-menu removals with `logger.debug(...)` matching the slash branch at lines 142-146. Document listener invocation order (registration order) in both docstrings. Extend `tests/test_event_bus.py` and `tests/test_hot_reload.py`.
- Plan 01-05: bugs.md deferred sweep — owns `easycord/plugins/auto_responder.py`, `easycord/plugins/levels.py`, `easycord/plugins/auto_role.py`, `easycord/plugins/invite_tracker.py`. B-013: auto_responder raw `self.config.update(...)` at ~line 59 → `ServerConfigStore.mutate` (canonical RMW, `easycord/server_config.py:217`). B-015: levels — narrow to `except discord.HTTPException` (VERIFY FIRST at levels.py:191 — may already be done; if so, regression-test only). B-016: auto_role — after `asyncio.sleep` window at auto_role.py:68-73 only `Forbidden` is caught; role can vanish during sleep → also catch `NotFound`/`HTTPException`. B-007: invite_tracker — add `on_guild_remove` cache pruning for `_invite_cache`. Also add `bot_permissions` to auto_role commands here (exclusive owner of that file). New test file: `tests/test_p1_bug_sweep.py`.

### Cross-cutting rules (locked)
- Every plan starts with a mandatory verify-the-finding step at the cited file:line before changing anything; already-fixed findings degrade that item to regression-test-only.
- Regression tests document the bug in the repo's `TestBugs` docstring style (see `tests/test_stress.py::TestBugs`).
- Reuse `easycord/testing.py` harness (`PluginTestSuite`, `FakeContextBuilder`, `invoke`, `invoke_component`) — no ad-hoc Discord mocking where the harness covers it.
- Conventional commits: `fix:` for fixes, `test:` for test-only work.
- One wave — all 5 plans are parallel-safe via the exclusive file ownership above. No plan may touch a file owned by another plan.
- Full suite must stay green: baseline 1403 tests, `pytest -q` gate after the wave.
- No wall-clock timing assertions in any new test (Windows 15ms ticks) — mock clocks, use `asyncio.Event`.

### Claude's Discretion
- Exact permission set per command where the mapping above says "where applicable" — derive from what Discord API calls the handler actually makes.
- Whether 01-03 drops or dedupes the per-callback sweep — executor judges from code, preferring drop if `bot._cooldown_registries` coverage is confirmed.
- Cap value for cooldown registries (default suggestion 50k entries) and eviction detail (evict oldest bucket first).
- Test count per new file (no floor for Phase 1 — floors apply to Phase 2 plugin files).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Mechanism / reference implementations
- `easycord/_command_callbacks.py` — bot_permissions machinery (lines ~179-206), cooldown sweep (lines ~20-90)
- `easycord/plugins/moderation.py` — the reference bot_permissions adopter (lines ~127-350)
- `easycord/server_config.py` — `ServerConfigStore.mutate()` canonical RMW (line ~217)
- `easycord/testing.py` — test harness (PluginTestSuite ~line 532, FakeContextBuilder ~line 211, invoke helpers ~lines 325-451)

### Findings provenance
- `.planning/IMPORTED-PLAN.md` — approved plan; live-verification results section supersedes audit docs
- `bugs.md` — B-007/B-013/B-015/B-016 definitions (root)
- `tests/test_stress.py` — TestBugs regression-guard convention

</canonical_refs>

<specifics>
## Specific Ideas

- Verify commands per plan (from approved plan): 01-01 `pytest tests/test_bot_permissions_adoption.py tests/test_tickets.py tests/test_verification.py tests/test_word_filter.py -q`; 01-02 `pytest tests/test_cli_scaffold.py tests/test_plugin_creator.py -q`; 01-03 `pytest tests/test_cooldown_cleanup.py tests/test_memory_safety.py -q -W error::DeprecationWarning`; 01-04 `pytest tests/test_event_bus.py tests/test_hot_reload.py -q`; 01-05 `pytest tests/test_p1_bug_sweep.py tests/test_levels_plugin.py tests/test_auto_role.py -q`.

</specifics>

<deferred>
## Deferred Ideas

- Lock-pattern consolidation (11 plugins' `_guild_lock` dicts) → Phase 4
- Coverage gate / pytest collection hygiene → Phase 4
- bugs.md/AUDIT_FINDINGS.md status truth-up → Phase 4 (plan 04-05)
- Unit-test backfill for untested modules/plugins → Phase 2

</deferred>

---

*Phase: 01-verified-bug-fixes*
*Context gathered: 2026-07-08 via PRD Express Path (.planning/IMPORTED-PLAN.md)*
