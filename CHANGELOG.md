# Changelog

## EasyCord v5.57.0 — 2026-07-18

### Added

- **Server setup templates** (`ServerSetupPlugin`) — new opt-in plugin with a
  `/setup-server` command that previews and applies preset server layouts:
  categories, text/voice channels, roles, role-level permissions, and per-channel
  permission overwrites. Four templates ship: `gaming`, `community`, `study`,
  `creator`. Application is additive only (existing items are skipped by
  Discord-normalized name, never modified or deleted) and gated behind an
  ephemeral preview with Apply/Cancel confirmation. Role permissions are clamped
  to what the bot can grant; per-item Discord failures are reported in the
  summary without aborting the run. Each successful run is recorded per guild
  (template, timestamp, invoker, created IDs). New guide: `docs/server-setup.md`.

### Changed

- **Release metadata** — GitHub Release `v5.57.0` tracks the expected artifacts:
  `easycord-5.57.0-py3-none-any.whl` and `releases/download/v5.57.0/easycord-5.57.0.tar.gz`.

## EasyCord v5.56.0 — 2026-07-16

### Added

- **`ServerConfigStore` in-memory cache** — per-guild config is cached after the
  first disk read. Subsequent `load()` calls return the cached copy without touching
  disk. `save()`, `mutate()`, and `delete()` keep the cache coherent. Negative caching
  (`None`) prevents repeated disk misses for guilds with no config file.
- **`LevelsPlugin` — leaderboard caching** — `/leaderboard` results are cached for
  5 minutes per guild. Invalidated by `/give_xp` and `/reset_xp`.
- **`LevelsPlugin` — XP multipliers** — new `/set_xp_multiplier <multiplier> [duration_minutes]`
  command. Multiplier applies to all organic XP gains for the duration (persisted to config).
- **`LevelsPlugin` — level-up DM toggle** — new `/toggle_level_dm` command. When enabled,
  the bot DMs the user on level-up in addition to the channel announcement. DM failures
  (Forbidden) are logged but do not crash the event handler.
- **`LevelsPlugin` — bulk XP reset** — new `/reset_xp <member>` command. Zeroes a
  member's XP and level atomically and invalidates the leaderboard cache.

### Changed

- **`decorators.py` internal cleanup** — `component()` and `modal()` now share a
  private `_dual_api_decorator()` helper; `user_command()` and `message_command()` share
  `_context_menu_decorator()`. No public API changes.
- **`EconomyPlugin` lock eviction** — per-guild balance locks are now tracked with a
  creation timestamp and evicted after 7 days of idleness (or when the pool exceeds
  5 000 guilds). Prevents unbounded memory growth on high-guild bots.
- **`EconomyPlugin` atomic transfer** — `/transfer` now uses a single `_transfer()`
  helper that reads and writes both balances under one lock acquisition, making the
  operation all-or-nothing.
- **Release metadata** — GitHub Release `v5.56.0` tracks the expected artifacts:
  `easycord-5.56.0-py3-none-any.whl` and `releases/download/v5.56.0/easycord-5.56.0.tar.gz`.

## EasyCord v5.55.0 — 2026-07-16

### Added

- **JuiceWRLD Plugin** (`JuiceWRLDPlugin`) — new built-in plugin integrating the former
  `juice-wrld-finder` project. Slash commands: `/jw_search`, `/jw_song`, `/jw_era`,
  `/jw_random`, `/jw_add_song`, `/jw_reindex`. AI tools: `search_juicewrld`,
  `get_song_details`. Event bus publishing on every command. Background 6-hour API sync task.
- Optional `use_external_api=True` mode queries `juicewrldapi.com` via the official
  `juicewrld-api-wrapper` PyPI package (no API key required):
  - `/jw_search` — parallel local + API search with three-bucket comparison embed
    (✅ both sources, 🗄️ local-only, 🌐 API-only)
  - `/jw_random` — falls back to API when local catalog is empty
  - `/jw_song` — API fallback embed (orange) when local ID not found; event still published
  - `/jw_era` — supplements local era results with API category results; API-only orange embed
    when era not in local catalog
  - `search_juicewrld` AI tool — merges local + API-only results in one text response
  - `get_song_details` AI tool — API fallback when local ID not found
- MEGA folder URL fallback (`mega_folder_url` constructor param) as last-resort song link.
- Three-level URL resolution per song: official URL → MEGA file → MEGA folder.
- `expose_mega_links` flag redacts MEGA URLs in public servers (default: `False`).
- `expose_api_download_links` flag shows `api_download_url` field in `/jw_song` (default: `False`).
- Event bus integration: publishes 7 events (`juicewrld.searched`, `.song_viewed`,
  `.era_browsed`, `.random_played`, `.song_added`, `.reindexed`, `.api_synced`);
  subscribes to 3 for internal logging and stale-index detection.

## EasyCord v5.54.0 - 2026-07-14

### Added

- Config-schema phase 2 (PR #88): Edge-case guards and migration repair
  - `ConfigSchema.apply()` now resets non-integer `_v` stamps and records the correction
  - Forward-version sections (`_v > schema.version`) pass through unchanged with warning
  - Missing migration steps logged as warnings; sections still stamp to target version
  - `_v` edge-case test coverage: 3 new unit tests for non-int, forward version, and gap detection

### Fixed

- **BUG-A (CRITICAL):** Vacuous `ok` flag in `_doctor_report` — was always `True` when
  `--fix-configs` used, masking failure-to-heal scenarios. Now correctly reflects healing success.
- **BUG-C (HIGH):** Missing migration step no longer silently stamps `_v` as fully migrated.
  Now logs warning and allows manual plugin author correction before next upgrade.
- **BUG-D (MEDIUM):** `--fix-configs` without bot target now exits with error instead of silent no-op.
- **BUG-F (MEDIUM):** Added help text warning that bot must be stopped before `--fix-configs`
  to avoid concurrent write loss.
- **BUG-J,K (MEDIUM):** `PluginConfigManager` falsy-check bugs fixed with `is None` guards
  (`update()` and `set_default()` now preserve falsy-but-valid values like `{}`, `[]`, `False`, `0`).
- Hygiene: Removed unnecessary lambda wrappers in `_bot_commands.py` (3 locations, 2 fewer lines per site).
- Hygiene: Hoisted inline `import logging` to module-level in `test_config_schema.py`.

### Tests

- New tests for `ConfigSchema.apply()` edge cases:
  - `test_apply_resets_non_int_v_and_migrates` — validates non-int `_v` reset and migration chain
  - `test_apply_warns_on_missing_migration_step` — confirms warning logged + `_v` still stamped
  - `test_apply_ignores_forward_version` — verifies forward-version section passthrough
- Codecov: 85.71% patch coverage; 2 missing lines in CLI error paths (acceptable).

### CodeQL / Security

Verified 12 CodeQL alerts:
- ALERT-141: FALSE POSITIVE (`except ValueError: pass` correctly typed)
- ALERT-72–80,104,142: FALSE POSITIVES (cyclic imports with TYPE_CHECKING guards; architectural pattern)
- ALERT-134: FALSE POSITIVE (Protocol `...` stub idiom)
- ALERT-82–86: FIXED (unnecessary lambda wrappers removed)
- ALERT-67–71,101–103,135–138: No new violations in this diff

## EasyCord v5.53.0 - 2026-07-11

### Added

- `tests/test_bot_permissions_adoption.py` — 16 regression tests pinning
  `bot_permissions` denial/allow behaviour and B-021 structural guard
  (config-setter commands must not declare `bot_permissions`)
- `tests/test_cli_scaffold.py` — CLI scaffold collision regression tests
- `tests/test_cooldown_cleanup.py` — 10 tests for bot-level cooldown sweep
  (expiry, `_COOLDOWN_MAX_ENTRIES` overflow eviction, plugin lifecycle cleanup)
- `tests/test_event_bus.py` extensions — EventBus observability tests
- `tests/test_p1_bug_sweep.py` — regression net for B-007 / B-015 / B-016

### Fixed

- B-007: `InviteTrackerPlugin._invite_cache` now pruned on `guild_remove`
- B-015: `LevelsPlugin._grant_level_reward` exception narrowed to
  `discord.HTTPException` (was `Forbidden`-only)
- B-016: `auto_role._on_member_join` post-sleep `add_roles` now catches
  full `discord.HTTPException` hierarchy
- Cooldown sweep consolidated to single bot-level `_cooldown_cleanup_loop`;
  per-callback sweep task removed; hard size cap (`_COOLDOWN_MAX_ENTRIES=50_000`)
  added with oldest-bucket eviction; cooldown registry entry now cleaned up
  on plugin unload via `remove_plugin`
- CLI scaffold collision when plugin slug matched an existing directory

### Tests

Total: 1513 (was 1438 in v5.52.0)

## EasyCord v5.52.0 - 2026-07-03

### Added

**Plugin dependency declarations** (`easycord/plugin.py`, `easycord/_bot_plugins.py`):
- `Plugin.requires: tuple[str, ...]` class attribute — declare plugin load-order requirements.
- `bot.add_plugin()` raises `PluginDependencyError(RuntimeError)` with `.missing` and `.plugin_class` attrs when a required plugin isn't loaded yet.
- `PluginDependencyError` is exported from `easycord`.

**Analytics middleware** (`easycord/middleware.py`):
- `AnalyticsStore` dataclass tracks invocation counts per `(command_name, guild_id)`.
- `analytics_middleware(store=None)` factory — attach to `bot.use()` to start collecting.
- Auto-wires the store to `bot._analytics_store` when `bot.use()` detects the `_analytics_store` attribute on the returned middleware.
- `bot.command_stats(guild_id=None)` queries aggregate or per-guild command counts.
- `AnalyticsStore` and `analytics_middleware` are exported from `easycord`.

**Per-guild plugin feature flags** (`easycord/_bot_plugins.py`, `easycord/_command_callbacks.py`):
- `bot.disable_plugin(name, guild_id)` — silently blocks all commands from a plugin in a specific guild.
- `bot.enable_plugin(name, guild_id)` — re-enables a plugin for a guild.
- `bot.is_plugin_enabled(name, guild_id)` — query current state (default `True`).
- Disabled commands return an ephemeral "This feature is disabled in this server." response; DM invocations are unaffected.

### Tests

- `tests/test_plugin_power_pack.py` — 24 tests covering dependency declarations, flag methods, `PluginDependencyError` attributes, and end-to-end dispatch guard (integration tests using real `Bot` + `invoke()`).
- `tests/test_middleware.py` — 11 new tests for `AnalyticsStore` and `analytics_middleware`.
- 1438 tests total.

## EasyCord v5.51.0 - 2026-07-01

### Fixed

**OpenClaw Optional member access** (`easycord/plugins/openclaw.py`):
- Added `assert ctx.guild is not None` guards in guild-only commands (lines 91, 119, 153, 164, 187) to narrow `Optional[Guild]` access.
- Added `assert self.orchestrator is not None` before accessing `strategy` (line 225).
- Added early return when `source` registry is `None` (line 284) before accessing `_tools`.

**Scheduled announcements loop resilience** (`easycord/plugins/scheduled_announcements.py`):
- Wrapped `ch.send()` in try/except to catch `discord.Forbidden` and `discord.HTTPException`.
- Loop now logs the error and continues on send failure instead of terminating permanently.

**Context channel Optional access** (`giveaway.py:300`, `polls.py:304`, `reminder.py:209`):
- Added guards: `if ctx.channel is None: return` before accessing `ctx.channel.id` in slash commands.

**Tickets button view guild guard** (`easycord/plugins/tickets.py`):
- Added early return if `interaction.guild is None` in the button callback (line 95).
- Persistent views can receive DM interactions; now handled gracefully.

**Three live plugin bugs** (cherry-pick c60c8b6):
- **birthday.py**: Fixed `_days_until` year-advance logic (Feb 29 crash on year boundary).
- **tickets.py**: Fixed `oldest_first=False` in transcript history to show messages in chronological order.
- **levels.py**: Extracted `_grant_level_reward` method; `/give_xp` now uses it for role rewards.

**Suggestions plugin cleanup** (`easycord/plugins/suggestions.py`):
- Removed unused `self.suggestion_counter = {}` field (dead code, real counter lives in persistent config).

**Starboard disabled by missing config key** (`easycord/plugins/starboard.py`, B-018):
- `cfg.get("enabled")` without a default treated a missing key as disabled — a guild that only ran `/starboard_channel` had a starboard that never fired. Now `cfg.get("enabled", True)` in both reaction handlers and the config display. The same pattern in five sibling plugins was audited and verified benign (B-019, closed).

### Added

- Public API exports: `SENDABLE_CHANNEL_TYPES`, `EventBus`, and `HookRegistry` are now importable from `easycord`.

### Tests

- Extended test coverage for plugin fixes; flat >=20-test-per-plugin CI floor (was complex >=20 / simple >=8); 1335 tests total (up from 1301).

## EasyCord v5.50.2 - 2026-06-24

### Fixed

**Interaction component TTL boundary** (`easycord/registry.py`):
- `InteractionRegistry._entry_active` treated an entry as active while `expires_at >= now`, so a component registered with `ttl=0` (whose `expires_at` equals its registration time) still resolved as active when looked up within the same clock tick. The check is now strict — `expires_at > now` — so a component is inactive at and after its expiry instant. This makes `resolve_component` deterministic across platforms: the off-by-one was latent on fine-grained clocks (Linux CI) but surfaced on coarse-resolution clocks (Windows `time.time()`, ~15 ms), where registration and resolution land in the same tick and a just-expired component was wrongly returned.

## EasyCord v5.50.1 - 2026-06-23

### Fixed

**AIModeratorPlugin governance** (`easycord/plugins/ai_moderator.py`):
- The live `on_message` moderation path now routes destructive actions through the governed `_execute_action` helper. Previously that helper — which holds the per-user rate limiters and Discord error handling — was defined but never called; the live path used inline calls instead.
- `auto_delete` no longer performs an unguarded `message.delete()`; a failed delete (race / missing permission) is caught rather than escaping into the event dispatcher.
- Warnings now go through the per-user rate limiter that was previously bypassed.
- Removed the unreachable `timeout`/`mute` branches from `_execute_action` (dead code — `mute` created a role with no permission overwrites and would not have muted anyone).
- Behavior change: a warning is now posted in-channel (rate-limited) instead of a best-effort DM, matching the governed action path.

**Documentation drift**:
- `docs/builtin-plugins.md`: removed `/purge` from `ModerationPlugin` — the command is not implemented.
- `context/architecture.md`: corrected the OpenClaw slash command names to the registered `/openclaw`, `/openclaw-task`, `/openclaw-status`, `/openclaw-stop`, `/openclaw-history` (previously listed as `/openclaw_task` / `/openclaw_stop`).

### Tests

- Added `tests/test_ai_moderator.py` (12 tests): auto-delete guarding (success + `Forbidden`/`HTTPException`), warn rate-limiting, dispatch guards (bot author, disabled guild, below-threshold), the notify-only review embed, and malformed/invalid model-output resilience.

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
