# Changelog

## EasyCord v5.50.0 - 2026-06-23

### Added

**EventBus** (`easycord/event_bus.py`) — async pub/sub between plugins:
- `bot.event_bus.subscribe(event, callback)` — register sync or async listeners
- `bot.event_bus.unsubscribe(event, callback)` — remove a listener
- `bot.event_bus.publish(event, **kwargs)` — fire an event; exceptions are isolated per listener

**HookRegistry** (`easycord/hooks.py`) — lifecycle hooks for bot internals:
- Four built-in hooks: `before_command`, `after_command`, `on_plugin_load`, `on_plugin_unload`
- `bot.hooks.register(hook_name, callback)` — register sync or async callbacks
- `bot.hooks.fire(hook_name, **kwargs)` — await all callbacks in registration order

**`@deprecated` / `@version_introduced` decorators** (`easycord/decorators.py`) ([docs](docs/deprecation.md)):
- `@deprecated("5.50.0", replacement="new_name")` emits `DeprecationWarning` at call time with a migration hint
- `@version_introduced("5.50.0")` annotates when a function was added (no runtime cost)
- Both set introspectable `__deprecated__`/`__version_introduced__` attributes on the wrapped function

**PluginTestSuite** (`easycord/testing.py`) ([docs](docs/testing.md)):
- Base class for plugin unit tests — wires up a `Bot` instance with no Discord connection
- `make_plugin(PluginClass)`, `invoke_command`, `invoke_autocomplete`, `invoke_component`, `invoke_modal`, `invoke_user_command`, `invoke_message_command`
- `assert_last_response(ctx, text)` — content assertion helper
- `FakeContextBuilder` — fluent builder for locale, roles, admin, DM, and guild contexts

**Hot-reload with `on_reload()` lifecycle** ([docs](docs/hot-reload-development.md)):
- `Plugin.on_reload()` fires on the **new** instance after a successful hot-reload swap
- Use it to migrate in-memory state that can't be reconstructed from `__init__` alone
- Poll interval: 1 s → 3 s; plugins requiring `__init__` args are skipped gracefully with an error log

**Command registration validation**:
- `ValueError` raised at registration time for: name > 32 chars or not matching `[-_a-z0-9]`, description > 100 chars, > 25 options, > 25 choices per option
- Error messages include the constraint, the actual value, and the command name

**Bot permission validator** ([docs](docs/hooks.md)):
- At `on_ready`, logs a WARNING per command if the bot lacks a required Discord permission in any joined guild
- Includes guild name, guild ID, and command name in the message

**Provider fallback metrics** — AI provider attempts log at DEBUG (try), DEBUG (success), WARNING (provider failure + exception type), ERROR (all exhausted)

**Database backend in `/health`** — embed now shows the configured backend (`sqlite` or `memory`), connection status, and round-trip latency

**`pyrightconfig.json`** — standard-mode Pyright configuration at repo root for plugin authors

### Fixed

- `format_number`: O(n²) `list.insert(0, …)` in thousands-grouping replaced with `list.append` + `"".join(reversed(parts))` → O(n)
- Conversation summarization: silent `except Exception: pass` replaced with `logger.warning(…)` — failures visible in logs
- Hot-reload poll: 1 s → 3 s
- Birthday plugin: untracked `asyncio.create_task` for role removal — tasks now held in `_role_tasks` and cancelled on `on_unload`
- `asyncio.iscoroutinefunction` (deprecated in Python 3.16) replaced with `inspect.iscoroutinefunction` in `EventBus` and `HookRegistry`
- CodeQL "statement has no effect" in `test_hot_reload.py` resolved
- `database.py`: `cast(DatabaseBackend, …)` eliminates Pyright errors on `os.getenv()` return value
- Pyright: `# type: ignore` narrowed to specific error codes; bare `dict` generics replaced with typed equivalents
- Release-drafter workflow: `paths-ignore` for version-bump files prevents redundant draft-release updates on `main`

### Tests

1,169 tests total (up from ~900). New test files: `test_event_bus.py`, `test_hooks.py`, `test_hot_reload.py`, `test_command_registration.py`, `test_cooldown_cleanup.py`, `test_deprecation.py`, `test_health.py`, `test_orchestrator.py`, `test_permission_validator.py`, `test_plugin_test_suite.py`, `test_new_decorators.py`. Patch coverage: 74% → 82%.

### Documentation

Four new guides: [Event Bus](docs/event-bus.md), [Lifecycle Hooks](docs/hooks.md), [Deprecation Helpers](docs/deprecation.md), [Testing Commands](docs/testing.md).

## EasyCord v5.49.0 - 2026-06-20

### Added

**TranslatePlugin** — new `/translate` slash command backed by Google Translate (via `deep-translator`, no API key required):
- `text` — content to translate
- `languages` — `"source to target"` pair (e.g. `"French to English"`, `"auto to Spanish"`); blank to auto-translate into the invoking user's Discord locale
- Translation runs in a thread executor (non-blocking); missing package or network failure returns an ephemeral error

**Google Translate → LocalizationManager** (`easycord/helpers/google_translate.py`):
- `make_google_auto_translator()` — returns a callback for `LocalizationManager(auto_translator=...)` so missing-key lookups are translated on-the-fly instead of falling back to the default locale's English strings
- `GoogleTranslateTranslator(app_commands.Translator)` — discord.py's official translator protocol; translates command names to all supported Discord locales at sync time

**Localized command names** — command names and descriptions now wrapped in `locale_str()` at registration time:
- `bot.use_google_translate()` installs `GoogleTranslateTranslator` on the command tree
- After `sync_commands()`, Discord shows each user the command in their own language (e.g. `/traduire` for French users, `/übersetzen` for German users)
- Interaction payload always carries the canonical name — no routing changes needed

**New optional extra:**
```bash
pip install "easycord[translate]"   # pulls in deep-translator
pip install -e ".[dev]"             # dev installs include it automatically
```

### Fixed

- `_parse_languages`: empty source or target after the `" to "` separator now correctly falls back to the user's Discord locale (was hardcoded to `"english"`)
- `_parse_languages`: padding trick fixes edge cases where `str.strip()` removes the spaces that form the separator (`" to English"` and `"French to "`)
- `asyncio.get_running_loop()` replaces deprecated `asyncio.get_event_loop()` in `TranslatePlugin.translate`

## EasyCord v5.48.0 - 2026-06-20

### Added

**Module splits** — internal modules broken into focused sub-modules for easier navigation:
- `_command_callbacks.py` — `build_slash_callback` / `build_context_menu_callback` with full guild/permission/cooldown/premium guards
- `_command_registration.py` — `register_slash`, `register_context_menu`, `inject_choices`, `autocomplete_options`
- `_plugin_scanner.py` — `scan_plugin_methods` auto-wires `@slash`/`@on` decorated plugin methods
- `_i18n_locale.py` — locale normalisation, OS-locale detection, BCP 47 validation, fallback chain builders
- `_i18n_diagnostics.py` — `DiagnosticMode` enum and `LocalizationDiagnostics` for missing-key and placeholder tracking
- `_i18n_validation.py` — `TranslationValidationReport` for per-locale completeness auditing

**PollsPlugin persistence** — polls now survive bot restarts:
- Vote state and remaining time are stored per-guild via `ServerConfigStore`
- `on_ready` re-registers views and resumes countdown timers for all active polls
- Deterministic `custom_id` values (`poll:vote:{message_id}:{option_index}`) allow views to reconnect after restart

### Fixed

- **Prompt injection** (`ai_moderator.py`): user-controlled `message.content` and `message.author.name` are now delimited with XML tags in the LLM prompt, preventing crafted messages from shifting model instructions
- **12 Pyright type errors** in `ai_moderator.py`: unguarded `ctx.guild` access narrowed with `assert ctx.guild is not None` (guild-only handlers) and `if ctx.guild is None: return False` (`_execute_action`)
- **Poll restore isolation** (`polls.py`): a single malformed poll entry no longer aborts restoration of all polls in a guild — each entry is wrapped in its own `try/except`
- **Cooldown dict growth** (`_command_callbacks.py`): expired bucket keys are pruned after filtering, preventing unbounded accumulation for inactive users
- **Pylance type errors** (`helpers/tools.py`): replaced `all()` truthiness guard with `isinstance` checks so Pylance narrows `name`/`description` to `str` and `safety` to `ToolSafety`

### Changed

- `CLAUDE.md` expanded with architecture quick-reference, testing patterns, channel send safety guide, and key invariants

## EasyCord v5.47.1 - 2026-06-16

### Fixed

- `tests/test_server_stats.py`: explained the bare `except (asyncio.CancelledError, Exception)` around background-task teardown in `test_setup_creates_channels` — it's load-bearing (swallows the `CancelledError` raised by awaiting a just-cancelled task), not dead code.
- `tests/test_word_filter.py`: removed an unused `ctx2` from `test_guilds_isolated` — the test only ever exercises `ctx1`; guild 2's isolation is verified by reading its config store directly.

## EasyCord v5.47.0 - 2026-06-15

### Added

**SecurityLabPlugin** — educational security demonstration tool for Discord bot developers:
- 7 slash commands demonstrating real attack vectors: stored injection, input overflow, ReDoS, prompt injection, phantom permission gates, flood attacks
- Each demo shows the attack in action, explains why it works, and provides a code-based defense
- Requires `manage_guild` permission (admin-only) to prevent misuse

**Security utilities** (`easycord.security`):
- `escape_mentions()` — sanitizes `@everyone`/`@here` to prevent accidental pings
- `truncate()` — hard-caps text length with ellipsis
- `safe_regex()` — runs regex with timeout protection against ReDoS
- `strip_injection_prefixes()` — removes common prompt-injection openers

### Fixed

- `easycord/plugins/tags.py`: Added `super().__init__()` call to `TagsPlugin.__init__` to properly invoke parent class initialization
- `easycord/plugins/word_filter.py`: Added explanatory comments on bare `except` clauses for clarity
- **`allowed_contexts`/`allowed_installs` raised `AttributeError` at runtime** — discord.py 2.7.1 defines two distinct classes named `AppCommandContext`/`AppInstallationType`: the slot-based ones under `discord.app_commands.*` (used by `Interaction.context` and command registration) and an unrelated ArrayFlags-based pair re-exported at top-level `discord.*`. `@slash`, `@user_command`, `@message_command`, `SlashGroup`, and `ctx.app_context` now use the `discord.app_commands` versions.
- `easycord/_bot_guild.py`: `send_webhook` builds its forwarded kwargs explicitly instead of passing `None` into discord.py's MISSING-sentinel API.

### Changed

- Internal: `_bot_commands.py`/`_bot_events.py`/`_bot_guild.py`/`_bot_plugins.py` mixins now declare their composed `Bot` attribute surface via a `TYPE_CHECKING`-only `_bot_base.py` base, eliminating 12 `py/unsafe-cyclic-import` static-analysis false positives. No behavior change.

## EasyCord v5.46.0 - 2026-06-15

### Added

8 new community plugins:

- **BirthdayPlugin** — per-user birthday registry with daily midnight announcements and optional birthday role assignment
- **ReminderPlugin** — personal reminders with flexible duration syntax (`30m`, `2h`) and pending-reminder list
- **VerificationPlugin** — button-based or modal-question member verification that grants a configured role on success
- **ServerStatsPlugin** — live stat voice channels (`📊 Members`, `🟢 Online`, `💎 Boosts`) updated every 10 minutes
- **ScheduledAnnouncementsPlugin** — recurring scheduled announcements posted to any text channel on a configurable interval
- **ReputationPlugin** — community reputation points with 24-hour per-giver cooldown, leaderboard, and admin reset
- **WordFilterPlugin** — configurable word blocklist with delete/warn/both action modes and per-role exemptions
- **AutoRolePlugin** — automatic role assignment on member join with optional delay for bot-verification windows

## EasyCord v5.44.3 - 2026-06-14

### Fixed

- `context_builder.py`: `getattr(cmd, 'description', None)` guards `ContextMenu` commands that lack a `description` attribute, preventing `AttributeError` at runtime.
- `i18n.py`: `_metrics` annotation updated from `dict[str, int]` to `dict[str, Any]` — `locale_frequency` value is a nested `dict`, not an `int`. `_chain_cache` key type corrected from `str` to `tuple` (keys are `(str|None, str|None, bool)` tuples).
- `plugins/invite_tracker.py`: `invite.uses` narrowed with `or 0` in two places (`int | None` → `int`). `channel.send` guarded with `isinstance(channel, (TextChannel, Thread, VoiceChannel, StageChannel))` before calling `.send()` to prevent calls on non-sendable channel types.
- `plugins/member_logging.py`: Same `isinstance` narrowing applied before `channel.send()`.

### Tests
- Added 110 new tests across three new test files:
  - `tests/test_new_stress.py` (19 tests) — concurrency/load stress for `rate_limit`, `ConversationMemory`, and `LocalizationManager`.
  - `tests/test_plugins_new.py` (54 tests) — unit tests for 8 previously-untested plugins: starboard, suggestions, reaction_roles, moderation, polls, tags, invite_tracker, member_logging.
  - `tests/test_core_gaps.py` (38 tests) — unit tests for zero-coverage core modules: `EmbedCard`, formatters, `ContextBuilder`, `SlashGroup`, `SecurityManager`, `FrameworkManager`, `AuditLog`.
- Total test count: 744.

### Assets
- https://github.com/rolling-codes/EasyCord/releases/download/v5.44.3/easycord-5.44.3-py3-none-any.whl
- https://github.com/rolling-codes/EasyCord/releases/download/v5.44.3/easycord-5.44.3.tar.gz

## EasyCord v5.44.2 - 2026-06-14

### Fixed
- `ToolLimiter._cleanup_usage` raised `KeyError` whenever `MAX_TRACKED_ENTRIES` (10 000) was exceeded: the cleanup path deleted `self._usage[key[0]]` (an `int`) instead of `self._usage[key]` (a `(user_id, tool_name)` tuple). Now deletes the correct key.
- `EconomyPlugin._cleanup_old_locks` could evict a lock while it was still acquired: the 7-day age threshold was measured from creation time, never refreshed on subsequent calls, so an active guild's lock could be removed and replaced with a fresh unacquired one — silently bypassing per-guild write serialization. Fixed by refreshing the last-used timestamp on every `_balance_lock()` access and guarding removal candidates with `not lock.locked()`.
- `progress_bar()` in `LevelsPlugin` returned a string longer than `width` when the supplied XP exceeded the next-level ceiling. Added `min(width, max(0, …))` clamp on the `filled` count.
- `Range(min=5, max=3)` constructed silently and only raised a confusing `ValidationError` at call time. Added `__post_init__` to `Range` that raises `ValueError` immediately when `min > max`.
- `BaseContext.respond()` and `BaseContext.dm()` passed `embed=None` and `content` as a positional argument to discord.py overloaded functions, causing Pylance `reportArgumentType` errors. Both methods now build a `msg_kwargs` dict and skip `content`/`embed` keys when `None`.
- `BaseContext.send_embed()` used `**({"timestamp": ts} if ts is not None else {})` which confused Pylance's narrowing. Replaced with `timestamp=ts` directly (`discord.Embed.__init__` accepts `Optional[datetime]`).
- `BaseContext.forward()` passed `discord.abc.Messageable` where discord.py's stub expects `MessageableChannel`. Added `# type: ignore[arg-type]` — the runtime guard already narrows `None` before the call.
- `LevelsPlugin` role-reward path used `hasattr(message.author, "add_roles")` which Pylance cannot narrow. Replaced with `isinstance(message.author, discord.Member)`.

### Tests
- Added 94 new tests in `tests/test_stress.py` covering the four fixed bugs (regression guards), levels-XP math invariants, all validators, and `ConversationMemory` edge cases. Total test count: 634.

### Assets
- https://github.com/rolling-codes/EasyCord/releases/download/v5.44.2/easycord-5.44.2-py3-none-any.whl
- https://github.com/rolling-codes/EasyCord/releases/download/v5.44.2/easycord-5.44.2.tar.gz

## EasyCord v5.44.1 - 2026-06-14

### Fixed
- Economy: transfers now load once, mutate both balances in memory, and persist with a single save under the per-guild lock, so a failed write can never leave a half-applied transfer (no lost currency).
- Economy: `/daily` records its outcome under the lock and replies only after releasing it, so Discord response latency no longer stalls the guild; `_get_config` is now a pure read that cannot clobber a concurrent balance update.
- Plugin type-safety: `guild_only` handlers assert `ctx.guild`/`ctx.user`, `suggestions` narrows the target channel to `TextChannel`/`Thread` before sending, and `reaction_roles` guards `self.bot.user` before reading its id — clearing the outstanding Pylance `reportOptionalMemberAccess`/`reportAttributeAccessIssue` errors.
- Starboard: removed duplicate archived-message helpers and fixed a misplaced slash import.
- Realigned in-repo version metadata (`pyproject.toml`, `easycord.__version__`, README badge/links, and `docs/getting-started.md`) with the published release line, which had drifted while still reporting `5.43.0`.

### Changed
- Public API: `PluginConfigManager` is now exported from `easycord.plugins` so code outside the package no longer imports the private `_config_manager` module.

### Assets
- https://github.com/rolling-codes/EasyCord/releases/download/v5.44.1/easycord-5.44.1-py3-none-any.whl
- https://github.com/rolling-codes/EasyCord/releases/download/v5.44.1/easycord-5.44.1.tar.gz

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
