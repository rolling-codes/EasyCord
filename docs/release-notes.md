# Release notes for 4.3.0

Release date: 2026-04-29

This release re-cuts the current EasyCord package line around the helper
utilities added in 4.2 while tightening runtime reliability and repository
release governance.

## What changed

- Re-cut the current package line with the EasyCord helper utilities from `easycord/`.
- Fixed webhook retry and stale webhook recovery behavior.
- Tightened emoji upload validation.
- Improved SQLite decoding safety.
- Fixed limiter and middleware bucket cleanup behavior.
- Added automatic release-label handling for pull requests.
- PR governance now creates missing release labels and normalizes duplicates.
- Updated package metadata and docs for the 4.3 release line.

## User impact

- Bots built on EasyCord get a more stable runtime with fewer cleanup and retry edge cases.
- Maintainers get cleaner release workflow automation and less manual label management.
- The helper utility surfaces introduced recently remain available on the current package line.

## Validation

- `pytest tests -q` -> `612 passed`
- `python -m build`

---

# Release notes for 4.2.0

Release date: 2026-04-29

This release adds a set of helper utilities for common bot UX and framework
bootstrap tasks, while also hardening several runtime and workflow edges.

## What changed

- Added `Paginator` for paginated command output and embed navigation.
- Added `EasyEmbed` for quick success, error, info, and warning responses.
- Added `SecurityManager` for safer middleware and AI guard setup.
- Added `FrameworkManager` for faster bot bootstrap with stronger defaults.
- Added convenience composer presets for secure defaults and easier setup.
- Improved stale webhook recovery and recreation.
- Hardened emoji file validation.
- Expanded workflow coverage for tests, auto-fix, release publishing, issue triage, and PR governance.

## User impact

- Bots can ship richer UX patterns with less boilerplate.
- New projects can start from safer defaults with less manual wiring.
- Maintainers get more reliable automation around quality and releases.

## Validation

- `pytest tests -q` -> `612 passed`
- `python -m build`

---

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
