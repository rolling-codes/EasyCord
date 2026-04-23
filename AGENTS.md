# AGENTS.md

## Purpose
This file is the quick-start operating guide for work in `EasyCord-main`.
Read this before diving into source so you stay aligned with the framework design and avoid wasting tokens.

## Commands

```bash
pip install -e ".[dev]"        # install editable package with dev deps
pytest                          # run the full test suite
pytest tests/test_foo.py        # run one test file
python -m build                 # build distribution artifacts
```

Notes:
- `asyncio_mode = "auto"` is set in `pyproject.toml`, so `@pytest.mark.asyncio` is usually unnecessary.
- Use the smallest useful pytest slice first, then expand only if needed.

## Where To Look First

| Task | File(s) |
| --- | --- |
| Project overview and beginner path | `README.md` |
| Repo-specific AI guidance | `CLAUDE.md` |
| Architecture map and extension points | `model.md` |
| Full API reference | `docs/api.md` |
| Getting started flow | `docs/getting-started.md` |
| Concepts and mechanics | `docs/concepts.md` |
| Examples | `docs/examples.md` |
| Framework core | `easycord/bot.py` |
| Context helpers | `easycord/context.py` and `easycord/_context_*.py` |
| Middleware | `easycord/middleware.py` |
| Plugin base and decorators | `easycord/plugin.py`, `easycord/decorators.py` |
| Per-guild config | `easycord/server_config.py` |
| Bundled plugins | `easycord/plugins/` |
| Example bot-specific plugins | `server_commands/` |
| Tests | `tests/` |

## Architecture Snapshot

- `Bot` wires slash commands, events, middleware, plugins, and groups.
- `Context` is assembled from the `_context_*.py` mixins.
- Middleware wraps slash commands only, not events.
- Plugins group related commands and handlers into classes.
- `ServerConfigStore` owns per-guild JSON persistence and writes atomically.
- `AuditLog` handles embed-based logging to a Discord channel.
- `SlashGroup` provides grouped slash commands.

## Non-Obvious Patterns

- Context logic is split across mixins. Edit the relevant `_context_*.py` file instead of stuffing logic into `context.py`.
- Middleware short-circuits by skipping `await next()`.
- Multiple handlers for the same event are allowed and are scheduled independently.
- Plugin lifecycle differs depending on whether the bot is already running when the plugin is added.
- `server_commands/` is for bot-specific examples and app behavior, while `easycord/plugins/` is for bundled reusable features.
- Keep secrets in environment variables.
- Use async I/O only; do not block the event loop.

## Extension Conventions

- New bot features belong in `server_commands/<feature>.py`.
- New reusable framework plugins belong in `easycord/plugins/<feature>.py`.
- Add tests alongside behavior changes in `tests/`.
- Prefer the existing public API over creating parallel abstractions.
- Keep changes small and localized unless a refactor is explicitly needed.

## Token-Saving Practices

- Read only the files needed for the current task.
- Prefer `CLAUDE.md` and `model.md` before source spelunking.
- Check `docs/api.md` for signatures before inspecting implementation details.
- Use `rg` to find symbols before opening many files.
- Read one `_context_*.py` file at a time instead of all of them.
- Summarize long docs instead of re-reading them repeatedly.
- Reuse existing names, helpers, and patterns whenever possible.
- Make the smallest possible edit that solves the problem.
- Run the narrowest useful test slice first.
- Avoid reloading this file unless the task touches architecture, tests, or project direction.

## Roadmap Note

The `EasyCord_v3.1.3_Brainstorm.pdf` notes are a future-looking roadmap, not a finished spec.
They point toward:

- a more unified database layer
- locale-aware translations and fallback behavior
- lighter DX helpers such as paginators and confirm dialogs
- better internal analytics and logging hooks

Treat those ideas as guidance until the source code implements them.

## Working Assumptions

- The docs and source are the source of truth.
- `README.md` is the beginner-facing overview.
- `model.md` is the best compact architecture map.
- When in doubt, verify in code before changing behavior.

## Current State

- `bot.db` is now a framework-owned database surface with SQLite and memory backends.
- `Bot.load_builtin_plugins()` exists for the bundled plugin pack.
- `Composer()` forwards builtin-plugin and database settings.
- `EmbedCard` plus `InfoEmbed`, `SuccessEmbed`, `WarningEmbed`, and `ErrorEmbed` are available for embed-first layouts with buttons or selects.
- Full test suite status at save time: `448 passed`.
- Latest working area: bundled plugins, database auto-configuration, and embed-card helpers.
