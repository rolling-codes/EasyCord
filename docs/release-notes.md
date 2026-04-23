# Release notes for 3.1.3

Release date: 2026-04-22

This release focuses on lowering the amount of boilerplate you need to write at the start of a bot project while also making the framework easier to extend safely.

## Highlights

- Added auto-configured database support through `Bot.db`.
- Added bundled first-party plugin loading with `bot.load_builtin_plugins()`.
- Added reusable embed-card helpers for prebuilt embeds with buttons and select menus.
- Added a lightweight localization manager plus `ctx.locale`, `ctx.guild_locale`, and `ctx.t(...)`.
- Switched built-in command guard text to localized lookup when translations are provided.

## What changed

- Simplified the starter path with smaller example entrypoints and shared runtime helpers.
- Centralized bundled plugin loading so the default plugin set is defined in one place.
- Added bulk helpers like `Bot.add_plugins(...)`, `Composer.add_plugins(...)`, `Bot.add_groups(...)`, and `Composer.add_groups(...)`.
- Added more `discord.py` command metadata support: `nsfw`, `allowed_contexts`, and `allowed_installs` for slash commands and context menus.
- Expanded `SlashGroup` so grouped slash commands can carry their own policy settings.
- Added `examples/group_bot.py` to show grouped commands in a small, copyable example.
- Trimmed repeated file I/O and guild checks in the bundled plugins with shared helpers.
- Tightened the docs so the API reference starts with the shortest beginner-friendly path.

## Why it helps

- You can get a bot running faster with fewer one-off helper classes.
- Plugin and command-group wiring stays more consistent as a project grows.
- Locale-aware strings make it easier to tailor responses without hardcoding every message in one language.
- The new embed helpers make it simpler to reuse polished message layouts.

## How to use the new pieces

- Use `bot.load_builtin_plugins()` when you want the bundled welcome, tags, polls, and leveling plugins.
- Use `Bot.db` for framework-owned storage instead of opening SQLite files directly.
- Use `EmbedCard` and the themed embed wrappers when you want an existing embed plus buttons or select menus.
- Use `LocalizationManager` and `ctx.t(...)` for translated strings, especially framework-facing error text or reusable command copy.

## Upgrade notes

- Existing bots can adopt the new features incrementally.
- Nothing in this release requires a code migration for existing slash commands or plugins.
- If you only want the new localization helpers, you can start by wrapping a single response string and expand from there.

## Validation

- `python -m pytest tests/test_group.py tests/test_bot.py tests/test_composer.py tests/test_server_commands.py tests/test_package_exports.py tests/test_decorators.py tests/test_context.py tests/test_i18n.py`
- `python -m compileall easycord examples docs tests`

Note: On Windows, pytest may emit temp/cache permission warnings that can be safely ignored if the test slice passes.
