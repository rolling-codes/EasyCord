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
