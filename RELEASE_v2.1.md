# EasyCord Framework v2.1 Release Notes

**Release Date:** 2026-04-30

> Historical backfill: these notes document a legacy EasyCord framework package snapshot that was provided separately from the current 4.x repository line. This PR records the release information without force-merging the older framework layout over `main`.

This release delivers a number of important improvements over the previous transitional build of the EasyCord framework. The goals of this update are to solidify the runtime contracts, close gaps identified in code review, and make the framework ready for deployment on hosted environments such as Replit.

## Highlights

### Context Binding Fixes

- **EasyCord bot exposure** — Context objects created from Discord interactions now correctly reference the EasyCord `Bot` instance rather than the underlying `discord.Client`. The raw client is preserved on `ctx.discord_client` for low-level use. This fixes issues where helpers like rate limiting and database access would silently receive the wrong object.
- **Guilds property** — The `Bot.guilds` attribute is now a proper `@property` on the class. It returns an actual list of guild objects when the bot is connected and an empty list otherwise. In earlier versions this was injected as a property on the instance which caused it to behave incorrectly.

### Plugin Lifecycle Enhancements

- **Event wiring** — Plugins can now implement private hooks `_on_ready`, `_on_guild_join`, and `_on_member_join` (or their public counterparts) and have them automatically invoked when the Discord client emits these events. This brings the invite tracker and other event-driven plugins to life without manual wiring.
- **Reload support** — A new `Bot.reload_plugin` method unloads a plugin by invoking its `on_unload` hook, removes its commands from the registry, and then re-adds it via `add_plugin`. This enables live updates without restarting the bot.

### Command Synchronisation

- **Robust auto-sync** — The bot now attempts to synchronise application commands using whichever API is available on the underlying client (`application_commands` or `tree`). It gracefully handles missing methods and logs failures rather than crashing.

### Intent Resolution Improvements

- **Dynamic plugin intents** — The composer now calls `get_intents()` on plugins and groups when collecting required gateway intents. This allows plugins to compute their needs at runtime instead of relying solely on a class attribute.

### Localization Helper

- **`get_localized_text`** — The bot exposes a new helper that forwards translation requests to the configured localization manager. If no manager is set, the key is returned unchanged.

### Documentation and Example

- **Updated invite tracker docs** — The invite tracker plugin docs now note that its event handlers are automatically wired when running under EasyCord.
- **Replit support** — Included a sample `main.py`, `.replit` configuration, `replit.nix`, and `requirements.txt` to make deploying the bot on Replit straightforward. The example script demonstrates loading the built-in plugins and running the bot using a `DISCORD_TOKEN` environment variable.

## Migration Notes

Existing plugins may need to adopt the new private hook names to benefit from automatic event wiring. When implementing event handlers, use `_on_guild_join` and `_on_member_join` (or their public equivalents) for guild and member join events. Commands registered via decorators now appear under their primary alias; if you previously relied on `guilds` being a property object, update your code to treat it as a list.

We recommend re-running tests and reviewing the updated `AGENT_INSTRUCTIONS.md` for guidance on extending the framework.
