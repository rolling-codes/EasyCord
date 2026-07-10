# Roadmap: EasyCord Framework Hardening (v5.53)

## Overview

Four phases on one feature branch: close every verified-open defect with regression tests, backfill unit coverage for the untested surface, codify stress/concurrency/resilience behavior, then perform protected structural cleanups (lock consolidation, CI gates). Full task specs: `.planning/IMPORTED-PLAN.md`.

## Phases

- [ ] **Phase 1: Verified bug fixes** - Close A–F findings, each fix TDD-atomic with regression tests
- [ ] **Phase 2: Unit test backfill** - Dedicated tests for zero-coverage modules and 8 untested plugins
- [ ] **Phase 3: Stress & resilience suites** - Storage/dispatch concurrency, clock/TTL, scale scenarios
- [ ] **Phase 4: Framework improvements** - Lock consolidation, CI coverage gate, docs truth-up

## Phase Details

### Phase 1: Verified bug fixes
**Goal**: Every verified-open defect (bot_permissions adoption gap, CLI scaffold collision, cooldown sweep nits, observability gaps, bugs.md B-007/B-013/B-015/B-016) is fixed with a named regression test. Every task re-verifies its finding at the cited lines first; if already fixed, it degrades to regression-test-only.
**Depends on**: Nothing (first phase)
**Requirements**: REQ-01, REQ-02, REQ-03, REQ-04, REQ-05
**Success Criteria** (what must be TRUE):
  1. Privileged commands in tickets, reaction_roles, verification, word_filter, welcome, giveaway, polls, starboard, member_logging, auto_role declare `bot_permissions` and deny gracefully when the bot lacks them
  2. `easycord new test-bot --template plugin` produces a project whose plugin module is not collected by pytest, and generated pyproject has `testpaths`
  3. No `DeprecationWarning` from cooldown scheduling under `-W error::DeprecationWarning`; cooldown registries capped
  4. EventBus subscriber failures log handler `__qualname__`; plugin unload paths debug-log instead of silent `pass`
  5. B-007, B-013, B-015, B-016 each have a regression test in the repo's TestBugs style
**Plans**: 5 plans (1 wave — exclusive file ownership: auto_role.py→01-05; bot.py+_command_callbacks.py→01-03)

Plans:
- [ ] 01-01: bot_permissions adoption across 9 privileged plugins + tests/test_bot_permissions_adoption.py
- [ ] 01-02: CLI scaffold collision fix (cli.py) + tests/test_cli_scaffold.py
- [ ] 01-03: Cooldown sweep cleanup + bounded registries (_command_callbacks.py, bot.py)
- [ ] 01-04: EventBus handler identity + unload debug logs (event_bus.py, _bot_plugins.py:156-163)
- [ ] 01-05: bugs.md sweep B-013/B-015/B-016/B-007 + auto_role bot_permissions + tests/test_p1_bug_sweep.py

### Phase 2: Unit test backfill
**Goal**: Dedicated, convention-following test files for every zero/thin-coverage module and the 8 untested plugins (≥20 tests per plugin file). New files only — zero merge-conflict surface.
**Depends on**: Phase 1
**Requirements**: REQ-06
**Success Criteria** (what must be TRUE):
  1. tests exist: test_validators, test_sanitizers, test_audit, test_builders, test_embed_cards, test_channel_helper, test_conversation_memory, test_tool_limits_full, test_builtin_tools, test_cli, test_managers_group, test_formatting_gaps
  2. Plugin tests exist with ≥20 tests each: moderation, economy, polls, welcome, reaction_roles, auto_responder, invite_tracker, member_logging
  3. Existing gap-fill only — no duplication of scenarios already in test_core_gaps.py / test_utils_and_helpers.py
  4. Full suite green
**Plans**: 7 plans (wave 2a: 02-01..02-04 core; wave 2b: 02-05..02-07 plugins)

Plans:
- [ ] 02-01: validators + sanitizers + audit tests
- [ ] 02-02: builders + embed_cards + channel helper tests
- [ ] 02-03: conversation_memory + tool_limits gap-fill + builtin_tools tests
- [ ] 02-04: cli + managers/group + composer/formatters tests
- [ ] 02-05: moderation + economy plugin tests
- [ ] 02-06: polls + welcome + reaction_roles plugin tests
- [ ] 02-07: auto_responder + invite_tracker + member_logging plugin tests

### Phase 3: Stress & resilience suites
**Goal**: Concurrency, clock/TTL, and scale behavior codified as deterministic tests. Hard rule: no wall-clock assertions — mocked `time.monotonic`/`time.time`, frozen datetime, `asyncio.Event` sync only.
**Depends on**: Phase 2
**Requirements**: REQ-07
**Success Criteria** (what must be TRUE):
  1. tests/test_stress_storage.py: 100–200 concurrent ServerConfigStore.mutate RMW with no lost updates; SQLite/Memory parity; schema-drift check
  2. tests/test_stress_dispatch.py: hot-reload under 50 concurrent invokes with no vanished-command window; registry + EventBus storm behavior
  3. tests/test_time_behavior.py: cooldown expiry/cap-eviction, ConversationMemory max_age, ToolLimiter rollover, threaded i18n t() — all with mocked clocks
  4. tests/test_resilience_scenarios.py: 1,000-guild sync timeout, 30-plugin load/unload storm, multi-instance sync overlap
  5. Each new stress file passes 3 consecutive runs
**Plans**: 4 plans (1 wave — new files only)

Plans:
- [ ] 03-01: storage concurrency suite
- [ ] 03-02: dispatch concurrency suite
- [ ] 03-03: clock/TTL behavior suite
- [ ] 03-04: scale/resilience scenarios suite

### Phase 4: Framework improvements
**Goal**: Structural cleanups protected by the Phase 2–3 net: canonical guild-lock helper adopted by all 11 duplicating plugins, CI coverage gate + collection hygiene, audit-ledger truth-up.
**Depends on**: Phase 3
**Requirements**: REQ-08, REQ-09
**Success Criteria** (what must be TRUE):
  1. `GuildLockMap` (or direct `ServerConfigStore.mutate` migration) in easycord/plugins/_shared.py; tickets, birthday, giveaway, word_filter, reminder, verification, scheduled_announcements, polls, auto_role, server_stats, reputation all migrated off private `_guild_lock` dicts
  2. Repo pyproject has `testpaths`/`norecursedirs`; `pytest --collect-only -q` collects nothing from release_v*/scratch dirs
  3. codecov workflow enforces `--cov-fail-under=<measured baseline − 2>`; scripts/check_mixin_pattern.py lint runs in tests.yml; verify_plugin_tests.py covers the 8 new plugin test files
  4. bugs.md/AUDIT_FINDINGS.md statuses match reality; EventBus ordering, cooldown eviction, and bot_permissions documented in docs/; CHANGELOG entry added
**Plans**: 5 plans (wave 4a: 04-01 helper+pattern-proof, 04-02 CI hygiene; wave 4b: 04-03/04-04 lock migrations, 04-05 docs)

Plans:
- [ ] 04-01: GuildLockMap helper + migrate tickets/birthday/giveaway + tests/test_guild_lock_map.py
- [ ] 04-02: CI + collection hygiene (pyproject, codecov gate, mixin lint, verify_plugin_tests list)
- [ ] 04-03: lock migration set A (word_filter, reminder, verification, scheduled_announcements)
- [ ] 04-04: lock migration set B (polls, auto_role, server_stats, reputation)
- [ ] 04-05: docs truth-up + CHANGELOG + orchestrator tools_schema verify-and-fix-if-confirmed

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Verified bug fixes | 0/5 | Not started | - |
| 2. Unit test backfill | 0/7 | Not started | - |
| 3. Stress & resilience suites | 0/4 | Not started | - |
| 4. Framework improvements | 0/5 | Not started | - |
