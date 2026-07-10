# Requirements: EasyCord Framework Hardening (v5.53)

Requirement IDs referenced by ROADMAP.md phases. Full context in PROJECT.md; task-level detail in IMPORTED-PLAN.md.

## v5.53 Requirements

### Bug fixes (Phase 1)

- [ ] **REQ-01**: Privileged built-in plugins validate the bot's own permissions via `bot_permissions` (mechanism at `easycord/_command_callbacks.py:179-206`; reference adopter `plugins/moderation.py`)
- [ ] **REQ-02**: CLI scaffolding rejects/renames pytest-colliding module names (`test_*`); generated pyproject scopes pytest with `testpaths=["tests"]`
- [ ] **REQ-03**: Cooldown scheduling uses `asyncio.get_running_loop()`; redundant per-callback sweeps removed; registries capped
- [ ] **REQ-04**: EventBus exception logs include handler identity; plugin unload paths debug-log instead of silent `pass`
- [ ] **REQ-05**: bugs.md B-007 (invite_tracker pruning), B-013 (auto_responder TOCTOU), B-015 (levels exception narrowing), B-016 (auto_role post-sleep exceptions) closed with regression tests

### Test coverage (Phases 2–3)

- [ ] **REQ-06**: Dedicated test files for all zero/thin-coverage modules (validators, sanitizers, audit, builders, embed_cards, channel helper, conversation_memory, tool_limits, builtin_tools, cli, managers, group, composer, formatters) and 8 untested plugins (≥20 tests each: moderation, economy, polls, welcome, reaction_roles, auto_responder, invite_tracker, member_logging)
- [ ] **REQ-07**: Deterministic stress suites — storage RMW concurrency, dispatch/hot-reload concurrency, mocked-clock TTL behavior, scale/resilience scenarios

### Structural improvements (Phase 4)

- [ ] **REQ-08**: Per-guild locking consolidated (shared `GuildLockMap` helper or `ServerConfigStore.mutate`); 11 duplicating plugins migrated
- [ ] **REQ-09**: CI coverage floor enforced (`--cov-fail-under`, measured baseline − 2); pytest collection hygiene (`testpaths`, `norecursedirs`); mixin-pattern lint; verify_plugin_tests.py list updated

## Traceability

| Requirement | Phase | Plans |
|-------------|-------|-------|
| REQ-01 | 1 | 01-01, 01-05 (auto_role) |
| REQ-02 | 1 | 01-02 |
| REQ-03 | 1 | 01-03 |
| REQ-04 | 1 | 01-04 |
| REQ-05 | 1 | 01-05 |
| REQ-06 | 2 | 02-01 … 02-07 |
| REQ-07 | 3 | 03-01 … 03-04 |
| REQ-08 | 4 | 04-01, 04-03, 04-04 |
| REQ-09 | 4 | 04-02 |
