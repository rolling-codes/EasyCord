# EasyCord Framework Bug-Fix & Improvement Plan

## Context

EasyCord (`C:\Users\Tom\Code projects\EasyCord`, Python Discord bot framework, `main` @ b1f0840, clean tree, 1403 tests passing) carries a documented backlog in `bugs.md`, `EasyCord_Improvement_Plan/AUDIT_FINDINGS.md`, and `EasyCord_Critiques_and_Solutions.md`. The user wants a whole-framework hardening pass — bug fixes, unit tests, stress tests, general improvements — executed via the **GSD pipeline** (wave-based parallel executors), landing on a **feature branch with one PR**.

Live-code verification (2026-07-08) found the audit docs substantially stale: i18n thread-safety, hot-reload race, regex pre-compilation, guild-sync timeout, cooldown pruning loop, ConversationMemory eviction, ToolLimiter await, and the bot-permission *mechanism* are all already fixed/implemented on main. What's genuinely open:

- **A. `bot_permissions` adoption gap** — mechanism exists (`_command_callbacks.py:179-206`) but only `plugins/moderation.py` uses it; 10 privileged plugins don't.
- **B. CLI scaffold pytest collision** — `cli.py:159-160` allows `test_*` module names; generated pyproject lacks `testpaths`.
- **C. Cooldown sweep nits** — deprecated `asyncio.get_event_loop()` at `_command_callbacks.py:87`; redundant per-callback sweeps; no max-size cap.
- **D/E. Observability** — EventBus exception logs lack handler identity (`event_bus.py:73-80`); silent `except: pass` on context-menu removal (`_bot_plugins.py:156-163`).
- **F. Deferred bugs.md items** — B-013 auto_responder TOCTOU, B-015 levels HTTPException narrowing, B-016 auto_role post-sleep exceptions, B-007 invite_tracker cache pruning.
- **G. Lock duplication** — 11 plugins keep private `_guild_lock` dicts; `ServerConfigStore.mutate()` (`server_config.py:217`) is canonical.
- **H. No coverage gate** — codecov workflow has no `--cov-fail-under`; repo pyproject lacks `testpaths`/`norecursedirs` (13 `release_v*` dirs are a collection hazard).
- **I. Coverage gaps** — zero/thin: `security/sanitizers.py`, `helpers/channel.py`, `validators.py`, `formatters.py`, `composer.py`, `embed_cards.py`, `managers.py`, `builtin_tools.py`, `builders/*`, `utils/easy_embed.py`, `utils/paginator.py`, `audit.py`, `cli.py`; no dedicated plugin tests: auto_responder, economy, invite_tracker, member_logging, moderation, polls, reaction_roles, welcome.

**Ordering rationale:** fixes before tests — the 1403 existing tests already characterize behavior; writing tests for the 8 untested plugins first would lock in bugs. Each fix task is TDD-atomic (regression test + fix together). Exception: lock consolidation is deferred to Phase 4, after Phases 2–3 build the safety net.

## Orchestration (user-confirmed)

- **GSD pipeline** in the EasyCord repo: bootstrap `.planning/`, then `/gsd-plan-phase` → `/gsd-execute-phase` per phase, parallel executor waves.
- **Branch/PR:** single `feature/framework-hardening-v5.53` off `main`; per-task atomic commits (`fix:`/`test:`/`refactor:`/`ci:`/`docs:`); at the end `/gsd-pr-branch` produces a clean PR branch with `.planning/` commits filtered; one PR to `main`.
- Reuse throughout: `easycord/testing.py` (`PluginTestSuite`, `FakeContextBuilder`, `invoke`/`invoke_component`/`invoke_modal`/`invoke_autocomplete`); conventions from `tests/test_starboard.py`, `tests/test_tags.py`; stress patterns from `tests/test_new_stress.py`, `tests/test_pr71_concurrency.py`. New plugin test files need ≥20 tests (`scripts/verify_plugin_tests.py` CI floor).

## Phase 1 — Verified bug fixes (5 tasks, 1 wave; exclusive file ownership)

Every task re-verifies its finding at the cited lines first; if already fixed, degrade to regression-test-only.

| Task | Work | Files | Verify |
|------|------|-------|--------|
| 1.1 | Adopt `bot_permissions` in privileged plugins (mirror `moderation.py:127-350`): tickets→manage_channels, reaction_roles/verification→manage_roles, word_filter→manage_messages, giveaway/polls/starboard→send/react perms, member_logging/welcome→channel-send | 9 plugin files + new `tests/test_bot_permissions_adoption.py` | `pytest tests/test_bot_permissions_adoption.py tests/test_tickets.py tests/test_verification.py tests/test_word_filter.py -q` |
| 1.2 | CLI scaffold: generated pyproject gets `testpaths=["tests"]` (cli.py:101); `_module_name` rejects/renames `test_*` | `easycord/cli.py` + new `tests/test_cli_scaffold.py` | `pytest tests/test_cli_scaffold.py tests/test_plugin_creator.py -q` |
| 1.3 | Cooldown sweep: `get_running_loop()` swap (line 87), drop redundant per-callback sweep (bot-level `_cooldown_cleanup_loop` covers it via `bot._cooldown_registries`), add max-entries cap to `_prune_cooldown_registries` | `easycord/_command_callbacks.py`, `easycord/bot.py` (this task owns both) | `pytest tests/test_cooldown_cleanup.py tests/test_memory_safety.py -q -W error::DeprecationWarning` |
| 1.4 | EventBus logs gain handler `__qualname__` + plugin identity; replace silent context-menu-removal `pass` with debug logs (match slash branch at `_bot_plugins.py:142-146`); document listener order | `easycord/event_bus.py`, `easycord/_bot_plugins.py:156-163` | `pytest tests/test_event_bus.py tests/test_hot_reload.py -q` |
| 1.5 | bugs.md sweep: B-013 auto_responder→`ServerConfigStore.mutate`; B-015 levels HTTPException narrowing (verify first); B-016 auto_role catch `NotFound`/`HTTPException` post-sleep; B-007 invite_tracker `on_guild_remove` pruning; auto_role `bot_permissions` (this task owns auto_role.py) | 4 plugin files + new `tests/test_p1_bug_sweep.py` | `pytest tests/test_p1_bug_sweep.py tests/test_levels_plugin.py tests/test_auto_role.py -q` |

Gate: full `pytest -q` green.

## Phase 2 — Unit tests for untested modules (7 tasks, 2 waves; new files only)

Wave 2a (core):
- **2.1** `tests/test_validators.py`, `tests/test_sanitizers.py`, `tests/test_audit.py`
- **2.2** `tests/test_builders.py` (button/embed/modal/select), `tests/test_embed_cards.py`, `tests/test_channel_helper.py`
- **2.3** `tests/test_conversation_memory.py` (eviction/summary/expiry), `tests/test_tool_limits_full.py` (gap-fill only), `tests/test_builtin_tools.py`
- **2.4** `tests/test_cli.py` (template rendering to tmp_path, name mangling), `tests/test_managers_group.py`, `tests/test_formatting_gaps.py` (composer/formatters; don't edit `test_core_gaps.py`)

Wave 2b (plugins, ≥20 tests each):
- **2.5** `tests/test_moderation.py` (incl. bot_permissions denial paths) + `tests/test_economy.py`
- **2.6** `tests/test_polls.py`, `tests/test_welcome.py`, `tests/test_reaction_roles.py`
- **2.7** `tests/test_auto_responder.py`, `tests/test_invite_tracker.py`, `tests/test_member_logging.py` (anchor Phase 1 fixes as regressions)

Verify: each task runs its own file selectors; wave gate `pytest -q`.

## Phase 3 — Stress/concurrency/resilience tests (4 tasks, 1 wave; new files only)

Hard rule: **no wall-clock assertions** — monkeypatch `time.monotonic`/`time.time`, freeze datetime, synchronize with `asyncio.Event` (Windows 15ms ticks).

- **3.1** `tests/test_stress_storage.py` — 100–200 concurrent `ServerConfigStore.mutate` RMW (no lost updates), SQLite vs Memory DB parity, schema-drift check (`database.py:144` vs `:254`)
- **3.2** `tests/test_stress_dispatch.py` — hot-reload lock under 50 concurrent invokes (no vanished-command window), registry resolve under concurrent register/unregister, EventBus publish storm with a raising subscriber
- **3.3** `tests/test_time_behavior.py` — cooldown expiry + cap eviction with mocked clock, ConversationMemory max_age, ToolLimiter window rollover, i18n threaded `t()` with `track_metrics=True`
- **3.4** `tests/test_resilience_scenarios.py` — 1,000-guild sync-timeout behavior (mocked db), 30-plugin load/unload storm (registry ends empty), multi-instance guild-sync overlap

## Phase 4 — Framework improvements (5 tasks, 2 waves)

Wave 4a:
- **4.1** `GuildLockMap` helper in `easycord/plugins/_shared.py` (or straight migration to `ServerConfigStore.mutate` where lock only guards config RMW); migrate tickets, birthday, giveaway as pattern-proof; new `tests/test_guild_lock_map.py`
- **4.2** CI/collection hygiene: repo `pyproject.toml` `testpaths`/`norecursedirs` + coverage config; codecov `--cov-fail-under=<measured baseline − 2>` (measure first, never guess); `scripts/check_mixin_pattern.py` AST lint for TYPE_CHECKING `_MixinBase` + tests.yml step; extend `scripts/verify_plugin_tests.py` list with the 8 new plugin test files

Wave 4b:
- **4.3** Lock migration set A: word_filter, reminder, verification, scheduled_announcements
- **4.4** Lock migration set B: polls, auto_role, server_stats, reputation
- **4.5** Docs truth-up: mark fixed items in `bugs.md`/`AUDIT_FINDINGS.md`, document EventBus ordering + cooldown eviction + `bot_permissions` guide in `docs/`, CHANGELOG entry (only this task touches CHANGELOG.md); verify-and-fix orchestrator `tools_schema` staleness only if confirmed

Final gate: `pytest -q` + `pytest --cov=easycord --cov-report=term-missing` meets the new gate; `ruff check`; `pytest --collect-only -q` shows no `release_v*` collection.

## Risks

1. Stale findings → verify-first step in every fix task.
2. Windows timing flakiness → mocked clocks only; run new stress files 3× before commit.
3. Merge conflicts → Phases 2–3 new-files-only; Phases 1/4 exclusive file ownership (auto_role→1.5, bot.py+_command_callbacks.py→1.3, CHANGELOG→4.5, pyproject+workflows→4.2).
4. verify_plugin_tests.py floor (20/plugin) → stated in task specs.
5. Coverage gate set from measured baseline − 2, raised later.

## Execution steps (post-approval)

1. `git switch -c feature/framework-hardening-v5.53` in the EasyCord repo.
2. Bootstrap GSD: `.planning/` with config (branching off, since we manage the branch; `commit_docs` on — `/gsd-pr-branch` filters them later), ROADMAP with the 4 phases above.
3. Per phase: `/gsd-plan-phase` (seeded from this plan) → `/gsd-execute-phase` (parallel waves) → phase gate (`pytest -q`).
4. After Phase 4: `/gsd-pr-branch` → clean `pr/framework-hardening-v5.53` → open PR to `main` titled "Framework hardening: bot_permissions adoption, test coverage, stress suite, lock consolidation".

## Verification (end-to-end)

- `pytest -q` full suite green at every phase gate (baseline 1403 tests; expect ~+400).
- `pytest --cov=easycord --cov-report=term-missing` — coverage ≥ baseline, gate enforced in CI.
- `ruff check` + `pyright` clean (CI parity).
- Every Phase 1 fix has a named regression test documenting the bug (repo's `TestBugs` convention).
