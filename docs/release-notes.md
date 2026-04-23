# Release notes for 3.1.3

Release date: 2026-04-22

This update adds the framework-owned database service and automatic guild-row
sync, plus a cleaner default path for storing bot data.

## What changed

- Added `bot.db` as an auto-configured SQLite or in-memory database surface.
- Added `DatabaseConfig`, `SQLiteDatabase`, `MemoryDatabase`, and `GuildRecord`.
- Seeded guild rows automatically on startup and when the bot joins a guild.
- Exposed the database API from `easycord.__init__`.
- Updated docs and tests to cover the new backend.

## User impact

- Bots can now store guild-scoped JSON data without wiring their own storage layer.
- Tests can use the in-memory backend to stay isolated.
- Real bots get a default SQLite file at `.easycord/library.db` unless overridden.

## Validation

- `pytest`

---

# Release notes for 3.1.0

Release date: 2026-04-22

This update focuses on two things: making the framework easier to learn, and exposing more of the `discord.py` features that beginners keep reaching for.

## What changed

- Simplified the starter path with smaller example entrypoints and shared runtime helpers.
- Centralized bundled plugin loading so the default plugin set is defined in one place.
- Added bulk helpers like `Bot.add_plugins(...)`, `Composer.add_plugins(...)`, `Bot.add_groups(...)`, and `Composer.add_groups(...)`.
- Added more `discord.py` command metadata support: `nsfw`, `allowed_contexts`, and `allowed_installs` for slash commands and context menus.
- Expanded `SlashGroup` so grouped slash commands can carry their own policy settings.
- Added `examples/group_bot.py` to show grouped commands in a small, copyable example.
- Trimmed repeated file I/O and guild checks in the bundled plugins with shared helpers.
- Tightened the docs so the API reference starts with the shortest beginner-friendly path.

## User impact

- Less boilerplate when wiring plugins and command groups.
- A clearer path from a single-file bot to a modular project.
- Better parity with `discord.py` for newer app command features.

## Validation

- `python -m pytest tests/test_group.py tests/test_bot.py tests/test_composer.py tests/test_server_commands.py tests/test_package_exports.py tests/test_decorators.py`
- `python -m compileall easycord examples docs tests`

Note: On Windows, pytest may emit temp/cache permission warnings that can be safely ignored if the test slice passes.
