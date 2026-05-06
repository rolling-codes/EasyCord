# AGENTS.md

This file provides guidance to Codex when working with code in this repository.

## Commands

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run all tests
pytest tests/

# Run a single test
pytest tests/test_memory_safety.py::test_conversation_memory_evicts_oldest_over_cap -v

# Build distribution package
python -m build
```

Tests use `pytest-asyncio` with `asyncio_mode = "auto"` — async tests need no manual event loop setup.

## Architecture

EasyCord is a Discord bot framework layered as follows:

**Bot core** — `bot.py` defines the `Bot` class via multiple inheritance: `discord.Client` + four mixins (`_bot_commands.py`, `_bot_events.py`, `_bot_guild.py`, `_bot_plugins.py`). Adding bot-level behavior means adding to one of these mixin files.

**Context** — `context.py` + `_context_channels.py`, `_context_moderation.py`, `_context_ui.py`. This is the user-facing API inside command handlers (`ctx.respond()`, `ctx.send_embed()`, etc.).

**Decorators** — `decorators.py` provides `@slash`, `@on`, `@component`, `@modal`, `@message_command`, `@user_command`, `@task`, `@ai_tool`. These are the primary extension points for bot authors.

**Plugin system** — `plugin.py` defines `Plugin`. Bundled plugins live in `plugins/` (moderation, leveling, tags, welcome, logging, etc.). Plugins register their own commands/events and are loaded via `bot.load_builtin_plugins()` or `bot.load_plugin()`.

**Database** — `database.py` provides `SQLiteDatabase` and `MemoryDatabase` with per-guild namespacing. `GuildRecord` is the typed row abstraction.

**AI orchestration** — `orchestrator.py` routes across 9 LLM providers with `FallbackStrategy`. `_ai_providers.py` holds provider adapters. Tools are registered via `ToolRegistry` and gated by `ToolSafety` permission checks.

**Localization** — `i18n.py` (`LocalizationManager`) handles locale auto-detection with fallback chains (user → guild → system → default). Three diagnostic modes: `SILENT` (production), `WARN` (dev), `STRICT` (CI).

**Middleware** — `middleware.py` provides cross-cutting concerns (logging, auth, rate limiting) applied around command dispatch.

**Public API** — everything re-exported from `easycord/__init__.py` is the stable surface. Internal modules prefixed with `_` are not part of the public contract.

## Key conventions

- Bot mixins follow the `_bot_<area>.py` naming pattern; context mixins follow `_context_<area>.py`.
- The `@ai_tool` decorator registers a function into `ToolRegistry` and requires explicit `ToolSafety` permission annotation.
- Per-guild state always goes through the database layer — never stored on the `Bot` instance directly.
- Localization keys are looked up via `LocalizationManager`; strings must not be hardcoded in plugin responses.
