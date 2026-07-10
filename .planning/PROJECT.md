# EasyCord Framework Hardening (v5.53)

## What This Is

A whole-framework hardening milestone for EasyCord, a production Python Discord bot framework (slash commands, plugins, middleware, i18n, AI orchestration). This milestone closes verified-open defects, backfills unit tests for 31 untested modules, adds stress/concurrency/resilience suites, and consolidates duplicated locking patterns — all landing as one reviewable PR.

## Core Value

Every verified-open defect is fixed with a regression test, and the framework's untested surface gains real coverage without destabilizing the 1403-test baseline.

## Requirements

### Active

- [ ] REQ-01: Privileged built-in plugins validate the bot's own permissions via `bot_permissions` before acting
- [ ] REQ-02: CLI scaffolding can never generate pytest-colliding module names, and generated projects scope pytest to `tests/`
- [ ] REQ-03: Cooldown registries are bounded and use non-deprecated asyncio APIs
- [ ] REQ-04: EventBus/unload failures are observable (handler identity in logs, no silent `pass`)
- [ ] REQ-05: Deferred bugs.md items B-007, B-013, B-015, B-016 are closed with regression tests
- [ ] REQ-06: Every zero-coverage core module, builder, helper, and untested plugin has a dedicated test file (plugins ≥20 tests each)
- [ ] REQ-07: Stress/concurrency/resilience suites cover storage RMW, dispatch, clock/TTL behavior, and scale scenarios — with mocked clocks only
- [ ] REQ-08: Per-guild locking is consolidated onto a canonical helper (`ServerConfigStore.mutate` or shared `GuildLockMap`)
- [ ] REQ-09: CI enforces a coverage floor and pytest collection excludes non-test directories

### Out of Scope

- PostgreSQL backend, plugin dependency resolver, web dashboard — future milestones per EASYCORD_IMPROVEMENT_PLAN.md Part G
- Plugin i18n string migration — explicitly aspirational per project.md critical decisions
- Plugin ecosystem tiering / docs restructure — separate docs-focused effort

## Context

- Root-level `project.md`, `CLAUDE.md`, and `context/architecture.md` are the framework's own docs — read them for architecture rules (mixin composition, per-guild state in DB, TYPE_CHECKING `_MixinBase` pattern).
- The approved execution plan with full task breakdown lives at `.planning/IMPORTED-PLAN.md`. It supersedes the stale audit docs (`bugs.md`, `EasyCord_Improvement_Plan/AUDIT_FINDINGS.md`) — several items listed there were already fixed in v5.50–v5.52.
- Test harness to reuse: `easycord/testing.py` (`PluginTestSuite`, `FakeContextBuilder`, `invoke*` helpers). Conventions: `tests/test_starboard.py`, `tests/test_tags.py`. Stress patterns: `tests/test_new_stress.py`, `tests/test_pr71_concurrency.py`.
- CI floor: `scripts/verify_plugin_tests.py` AST-counts ≥20 `test_` functions per plugin.

## Constraints

- **Baseline**: 1403 tests must stay green at every phase gate (`pytest -q`)
- **Platform**: Windows dev machine — no wall-clock timing assertions in tests (15ms ticks); mock `time.monotonic`/`time.time`, sync with `asyncio.Event`
- **Git**: all work on `feature/framework-hardening-v5.53`; conventional commit prefixes (`fix:`/`test:`/`refactor:`/`ci:`/`docs:`); PR produced at the end via /gsd-pr-branch with `.planning/` filtered
- **File ownership**: parallel tasks never share files — ownership map in IMPORTED-PLAN.md Risks §3

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Fixes before tests (Phase 1 first) | 1403 existing tests already characterize behavior; testing the 8 untested plugins first would lock in bugs | — Pending |
| Lock consolidation deferred to Phase 4 | Refactoring 11 plugins' locking needs the Phase 2–3 test net first | — Pending |
| Research/pattern-mapper agents disabled | Exploration already done; findings embedded in IMPORTED-PLAN.md | — Pending |
| Coverage gate = measured baseline − 2 | Never guess a threshold; raise later | — Pending |

---
*Last updated: 2026-07-08 after milestone bootstrap*
