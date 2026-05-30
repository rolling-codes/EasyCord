# Changelog

## EasyCord v5.43.2 - 2026-05-30

### Release Notice
This release combines features from v5.43.0 (plugin creator) and v5.43.1 (Phase 1 orchestration). See v5.43.0 and v5.43.1 sections below for detailed feature information.

---

## EasyCord v5.42.0 - 2026-05-29

### Added
- **14 new admin configuration commands** for plugin management:
  - **SuggestionsPlugin**: `/set_suggestions_channel` to configure the suggestions channel
  - **ModerationPlugin**: `/set_audit_channel`, `/set_mute_role`, `/clear_warnings` for audit logging and warning management
  - **AIModeratorPlugin**: `/set_mod_review_channel`, `/set_mod_audit_channel` for review channel configuration
  - **LevelsPlugin**: `/remove_level_role`, `/set_levelup_channel` for level role management
  - **RolePersistencePlugin**: `/saved_roles`, `/clear_saved_roles` for role visibility and cleanup
  - **EconomyPlugin**: `/shop_add`, `/shop_remove` for shop population via Discord (previously required direct database edits)
  - **StarboardPlugin**: `/starboard_toggle` to enable/disable archival
- **Event handlers for self-healing configurations:**
  - `on_guild_channel_delete` in MemberLoggingPlugin and InviteTrackerPlugin to clear deleted log channel references
  - `on_member_ban` in RolePersistencePlugin to prevent auto-restore of banned members' roles
  - `on_message_delete` in StarboardPlugin to clean up orphan starboard posts when source messages are deleted
- **Observability improvements:**
  - Full traceback logging in OpenClawPlugin task failures via `logger.exception()`
  - One-time-per-guild permission warnings in InviteTrackerPlugin to prevent log spam
  - Discord native relative timestamp `<t:timestamp:R>` in PollsPlugin footer for live countdown (replaces static "Closes in Xs" string)
  - DM warning logging in AIModeratorPlugin when user has DMs disabled
  - `ctx.conversation_messages(limit=None)` convenience method to expose conversation history as message dicts for AI providers
- **Atomicity fix** in EconomyPlugin `/buy` command: per-guild asyncio.Lock prevents TOCTOU race on concurrent purchases

### Fixed
- **SuggestionsPlugin**: `/suggestion_approve` and `/suggestion_reject` now edit the original Discord embed with green/red color and "Approved/Rejected by X" footer (previously only changed internal status)
- **ModerationPlugin**: Auto-mute in `/warn` command now logs to audit channel (previously skipped logging)
- **ModerationPlugin**: `/warn` auto-mute and other commands now respect configured `mute_role` instead of always searching for "Muted" by name
- **AIModeratorPlugin**: Added `logger.warning()` when unable to DM user (previously silent failure)
- **All plugins with config channels**: Prevent "channel not found" warnings from firing repeatedly when channel is deleted (now clears config on deletion)

### Known Limitations
- EconomyPlugin shop population now supports Discord UI but still lacks transactional guarantees (balance read-check-deduct are now atomic per-guild, but concurrent purchases across guilds still have no global coordination)

### Verification
- All 544 tests pass (no new tests added, existing coverage maintained)
- `python -m compileall -q easycord tests scripts` — passed
- `pytest tests/` — **544 passed** in 2.34s
- All new slash commands decorated with appropriate `@slash(..., permissions=["manage_guild"])`
- All event handlers properly integrated with existing plugin lifecycle

---

## EasyCord v5.41.0 - 2026-05-29

### Added
- Economy plugin shop system: `/shop` to view items and `/buy <item>` to purchase items with currency. New private helpers `_get_shop_items()` and `_set_shop_items()` for shop configuration. Items support "price", "description", and custom keys via ServerConfigStore.
- **11 new admin configuration commands** for previously undocumented plugins:
  - **AutoResponderPlugin** (4 commands): `/responder_add`, `/responder_add_regex`, `/responder_list`, `/responder_remove`
  - **MemberLoggingPlugin** (2 commands): `/member_log_channel`, `/member_log_config`
  - **InviteTrackerPlugin** (2 commands): `/invite_log_channel`, `/invite_tracker_config`
  - **ReactionRolesPlugin** (3 commands): `/reaction_role_set`, `/reaction_role_list`, `/reaction_role_remove`
- LocalizationManager.register() now accepts file paths: `register(locale, Path("locale.json"))` or `register(locale, "locale.json")` in addition to dict-like mappings. Validates file existence, JSON syntax, and that root is a dict; raises clear errors otherwise.

### Fixed
- Economy plugin command collision: renamed `/leaderboard` → `/economy_leaderboard` to avoid conflict with LevelsPlugin.
- Economy plugin shop safety: `/shop` and `/buy` use `.get("price")` to safely handle shop items missing the price key; now display an error instead of raising KeyError.
- Improved error messages for localization path loading: clear distinction between file-not-found, JSON decode errors, and non-object JSON roots.

### Known Limitations
- Concurrent purchases in economy `/buy` are not atomic—balance read, check, and deduct happen in separate transactions. A guild-level application lock would prevent double-spending; deferred for a follow-up release.

### Verification
- **Python versions tested:** 3.14.0rc3, 3.13.x, 3.12.x — all 544 tests pass on all three versions
- `python -m compileall -q easycord tests scripts` — passed on all versions
- `pytest tests/` — **544 passed** (27 new targeted tests for shop, localization, admin commands, and runtime validation)
- **New test files and counts:**
  - `tests/test_plugin_logic.py`: TestEconomyShop (11 tests), TestPluginAdminCommands (6 tests), TestV541RuntimeValidation (4 tests)
  - `tests/test_i18n.py`: TestLocalizationManagerFilePath (6 tests)
- **All 11 new admin commands** decorated with `@slash(guild_only=True, permissions=["manage_guild"])`
- All 4 plugins now have complete admin configuration UIs
- **Runtime validation completed:** Shop persistence verified across reload cycles, guild-only decorator verified, permission enforcement decorator verified, balance deduction behavior documented
=======
## EasyCord v5.43.0 - 2026-05-30

### Added
- Added `easycord.plugin_creator` as a public Python API for generating in-project plugins and reusable package plugins.
- Added plugin manifests with schema version `1`, validation helpers, and entry-point discovery through the `easycord.plugins` group.
- Added CLI wrappers for plugin authoring: `easycord plugin create`, `easycord plugin check`, and `easycord plugin discover`.
- Added `docs/plugin-authoring.md` and refreshed developer toolkit/getting-started docs for plugin manifests, package discovery, and local-safe scaffold defaults.

### Changed
- Default config-driven bots to local SQLite storage when no database backend is configured.
- Keep generated runnable bot scaffolds local-safe with command sync disabled; generated tests continue to use memory storage.

### Verification
- `python scripts/check_release_metadata.py` - passed.
- `pytest -o cache_dir=.pytest_cache_codex tests/` - 534 passed.
- `python -m compileall -q easycord tests scripts` - passed.

---

## EasyCord v5.40.2 - 2026-05-28

### Fixed
- Added `scripts/check_release_metadata.py` to enforce a single `pyproject.toml` version across `easycord.__version__`, README release links, CHANGELOG headings, project URLs, and release asset names.
- Added release metadata tests and wired the checker into GitHub Actions before the pytest run.
- Cleaned `MANIFEST.in` so source distributions keep the public library, docs, examples, and context notes while excluding local caches, release prep folders, workflow files, scripts, tests, and contributor-only development files.

### Verification
- `python scripts/check_release_metadata.py` - passed.
- `pytest -o cache_dir=.pytest_cache_codex tests/` - 517 passed.
- `python -m compileall -q easycord tests scripts` - passed.

---

## EasyCord v5.40.1 - 2026-05-27

### Fixed
- Updated the runtime dependency to `discord.py>=2.7.1,<3` and verified current app-command context and install metadata support.
- Added non-SQL memory database startup paths via `db_backend="memory"`, `database=MemoryDatabase()`, and `EASYCORD_DB_BACKEND=memory`.
- Updated generated starter templates to use the memory database where persistence is unnecessary.
- Closed SQLite test fixtures cleanly to remove delayed `ResourceWarning` noise under strict warning checks.
- Stabilized level-up tests on fresh CI runners by resetting XP cooldowns with an expired sentinel.
- Repaired the i18n performance regression workflow by adding the benchmark script it expects and aligning baseline cache paths.
- Added release-readiness coverage for the real GitHub wheel and source distribution asset names.

### Verification
- Python 3.11.9 via `py -3.11`.
- `discord.py 2.7.1` in `.venv311`.
- `ruff check easycord tests --select E9,F63,F7,F82` - passed.
- `pytest tests/` - 515 passed.
- `scripts/benchmark_i18n.py` - passed under thresholds.
- `python -m build` - passed.
- Earlier environment checks also passed: `pytest tests/ -W error::ResourceWarning`, `python -X tracemalloc=10 -m pytest tests/ -W always::ResourceWarning`, `ruff check .`, `compileall`, `git diff --check`, and CodeRabbit review with 0 issues.

---

## EasyCord v5.4.0 - 2026-05-10

### Added
- Stable JSON output contracts for `easycord doctor --json`, `easycord inspect --json`, and `easycord sync-plan --json`.
- Project scaffold templates via `easycord new --template minimal|plugin|ai|database`; the default `plugin` template preserves v5.3 behavior.
- Actionable doctor diagnostics with machine-readable `code`, `severity`, and `fix` fields while preserving existing `name`, `ok`, and `detail` fields.
- `FakeContextBuilder` for fluent offline command test setup.
- End-to-end developer toolkit docs showing project creation, diagnostics, inspection, sync planning, and offline tests.
- Offline AI tool safety audits via `easycord audit-tools`, `audit_tool_registry()`, and `format_tool_audit()`.
- `easycord doctor` now surfaces an `ai.tools_audit` check for bots with registered AI tools.
- `easycord new --list-templates` for discovering scaffold options.
- `easycord audit-tools --fail-on-warnings` for CI-friendly local AI safety gates.
- `FakeContextBuilder.with_roles()` for offline role-gated command and tool tests.

### Compatibility
- Existing CLI commands, flags, formatter exports, and testing helpers remain available.
- CLI commands remain dependency-free and avoid live Discord side effects by default.
- Runtime dependency floor is `discord.py>=2.7.1,<3`; SQLite remains available,
  while `MemoryDatabase`, `db_backend="memory"`, and `EASYCORD_DB_BACKEND=memory`
  provide non-SQL startup paths for tests and ephemeral bots.

### Verification
- `pytest tests/`
- `python -m compileall -q easycord tests`

---

## EasyCord v5.3.0 - 2026-05-10

### Added
- Dependency-free `easycord` CLI with `new`, `inspect`, `sync-plan`, `doctor`, and `test-template` commands.
- Project scaffolding for a runnable bot, starter plugin, `.env.example`, project metadata, and pytest coverage.
- `easycord doctor [module:bot]` for local setup diagnostics, token checks, dependency checks, and optional bot import validation.
- Developer formatters: `format_interaction_inventory()`, `format_sync_plan()`, and `format_doctor_report()`.
- Offline testing helpers for context menus, components, and modals via `invoke_user_command()`, `invoke_message_command()`, `invoke_component()`, and `invoke_modal()`.
- Developer toolkit documentation.

### Compatibility
- CLI commands avoid live Discord side effects by default. `sync-plan` only compares local state with manually supplied remote names.

### Verification
- `pytest tests/`
- `python -m compileall -q easycord tests`

---

## EasyCord v5.2.1 - 2026-05-10

### Added
- Centralized `InteractionRegistry` for slash commands, context menus, components, modals, and autocomplete callbacks.
- Command sync planning with dry-run support, duplicate detection, and safer destructive-sync handling via `bot.plan_command_sync()` and `bot.sync_commands(dry_run=True)`.
- Dynamic component routing with typed route parameters, e.g., `@component("ticket:close:{ticket_id:int}")`.
- Autocomplete callback registration and testing support via `@autocomplete`.
- `@slash_command` as a compatibility alias for `@slash`.
- Reusable option validators: `Duration`, `URL`, `Snowflake`, `Range`, `Regex`, and `ChoiceSet`.
- **Telemetry**: Global `/health` command now includes real-time telemetry: API latency, event loop latency (congestion monitoring), resident memory usage (via optional `psutil`), active thread counts, and plugin versions.
- **Memory Safety**: Added memory-pruning to `LevelsPlugin` XP cooldown cache and pagination to `TagsPlugin` tag list to prevent resource exhaustion and API limit errors.

### Changed
- Refactored Plugin instance tracking to use unique `_instance_id` values instead of class names, preventing state cross-pollution.
- Updated `InteractionRegistry` to compare structural segments of dynamic component patterns for collision detection.
- Bumped minimum required `discord.py` version to `>=2.7.1,<3` for current app-command context and installation support.
- Standardized all bundled plugins to use `ctx.respond()` instead of deprecated `ctx.send_embed_from_dict()`.

### Fixed
- **Core Stability**: Fixed a critical infinite recursion bug in `LocalizationManager` when reporting missing keys in `STRICT` mode.
- **Command Registration**: Fixed global `/health` command not being registered in the tree.
- **Plugin Resilience**: Resolved `StarboardPlugin` duplicate archival bug and missing configuration slash commands.
- **Config Handling**: Fixed `BotConfig.from_env()` syntax error and logic gap where `log_level` overrides were ignored.
- **Bug Fixes**: Unified error pipeline: exceptions from components, modals, and autocomplete now route through `plugin.on_error` then `bot.on_error`.
- Autocomplete failures now return an empty list instead of bubbling exceptions.
- Task cancellation during plugin unload is now handled as a normal lifecycle event.
- Fixed legacy component-prefix matches bypassing plugin-scoped error handlers.
- Fixed choice validators crashing on mixed-type choice sets.

### Compatibility
- `discord.py >= 2.7.1,<3` is now required.
- `InteractionRegistry` replaces `CommandTree` as the authoritative internal metadata store.

### Migration Notes
- **Interaction Registry**: Access registered metadata via `bot.registry` instead of inspecting `bot.tree` directly for EasyCord-specific logic.
- **Plugin IDs**: Plugins now use `_instance_id` (e.g., `MyPlugin_12345`) for registration. If you relied on the class name for reloading, use the new ID or class name (fallback supported).
- **Dynamic Routes**: Ensure dynamic component patterns do not overlap. The registry now performs strict shape-based collision detection.
- **Autocomplete**: Signatures are now validated at registration. Ensure callbacks accept `(ctx, current, options)` or `(current)`.

### Verification
- `pytest tests/` -> 472 passed.

---

## EasyCord v5.1.2 - 2026-05-07

### Added
- Config-driven startup via `BotConfig.from_env()` and `BotConfig.from_file()`.
- `easycord.testing.FakeContext` and `easycord.testing.invoke()` for unit-testing.
- Command guards: `@cooldown`, `@require_permissions`, `@install_type`, and `@premium_required`.
- `Context.send()` as a compatibility alias for `Context.respond()`.

### Fixed
- `BotConfig.build_bot()` now correctly honors `db_backend="memory"`.
- `BotConfig.from_file()` precedence: Env -> File -> Explicit.
- Guild-scoped command sync via `BotConfig.guild_id`.
- Discord user-install context metadata for current `discord.py` versions.

### Verification
- `pytest tests/` -> 461 passed.

---

## EasyCord v5.1.1 - 2026-05-06

### Fixed
- `LevelsPlugin` XP cooldown sentinel changed from `0.0` to `float("-inf")` to fix first-message blocking on new runners.

---

## EasyCord v5.1.0 - 2026-05-06

### Added
- `OpenClawPlugin` for autonomous AI agent tasks.

### Fixed
- `LevelsPlugin` role reward assignment using `hasattr(author, "add_roles")` for better compatibility.
- Orchestrator handling of empty string responses from AI providers.
- `ToolRegistry` role check crash in DM contexts.

### Verification
- `pytest tests/` -> 411 passed.

---

## EasyCord v5.0.0 - 2026-05-05

### Added
- Production-stable release with Python 3.13 support.
- Lazy-loaded AI providers exposed directly from `easycord`.
- Advanced `@ai_tool` metadata (safety, gates, limits).

### Fixed
- `FallbackStrategy` provider rotation logic.
- `ctx.is_admin` accessed as property instead of method.
- `ToolLimiter` async execution and locking.
- `asyncio.get_event_loop()` deprecation fixes.

### Verification
- `pytest tests/` -> 352 passed.
