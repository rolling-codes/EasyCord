# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
pip install -e ".[dev]"
pytest tests/
pytest tests/test_middleware.py -v
pytest tests/test_middleware.py::test_name -v
python -m build --no-isolation   # plain `python -m build` needs a working venv module
python scripts/check_release_metadata.py   # version consistency across pyproject/__init__/CHANGELOG
```

`pytest-asyncio` with `asyncio_mode = "auto"` — no manual event loop setup needed.

The `easycord` console script (`easycord/cli.py`) is the dev-facing CLI: `easycord new`, `easycord doctor`, `easycord inspect`, `easycord sync-plan`, `easycord plugin create|check|discover`, `easycord test-template`, `easycord audit-tools`.

## Context

- [Architecture](context/architecture.md) — layers, mixins, module map
- [Conventions](context/conventions.md) — naming rules, key invariants

## Architecture quick-reference

**Bot** (`bot.py`) composes `discord.Client` with four mixins — `_bot_commands.py`, `_bot_events.py`, `_bot_guild.py`, `_bot_plugins.py`. Each mixin imports `_BotBase` only under `TYPE_CHECKING` using a per-module `_MixinBase = _BotBase` alias so static checkers see the full `Bot` surface but no runtime import cycle is created. Never instantiate `_BotBase`; it is a phantom type only.

**Context** (`context.py` + `_context_*.py`) — use `ctx.user` / `ctx.member`. `ctx.author` does not exist. `ctx.is_admin` is a property, not a method.

**Plugin** (`plugin.py`) — subclass `Plugin`, decorate methods with `@slash` / `@on`, then call `bot.add_plugin(plugin_instance)`. The plugin scanner (`_plugin_scanner.py`) wires commands automatically. Per-guild state belongs in the database layer, never on `self` (the Plugin instance).

**i18n** — `LocalizationManager` in `i18n.py`, split across `_i18n_locale.py`, `_i18n_diagnostics.py`, `_i18n_validation.py`. Diagnostic modes: `SILENT`, `WARN`, `STRICT`. Never hardcode response strings in plugins; always look them up via `ctx.t(...)`.

**AI orchestration** — `orchestrator.py` routes via `FallbackStrategy` (advances through providers on exhaustion, raises `IndexError` when all fail). AI providers are lazy-imported from `plugins/_ai_providers.py` via `easycord.__getattr__`. `ToolLimiter` methods (`check_limit`, `reset_user`, `reset_tool`) are async — always await them.

**Command registration split** — `_command_callbacks.py` builds the actual callback wrappers; `_command_registration.py` handles option injection, choice population, and context-menu registration. Both are consumed by `_bot_commands.py`.

## Testing

`easycord.testing` provides everything needed to exercise commands without a Discord connection.

**Preferred patterns:**

```python
# Simple invoke — returns FakeContext with .last_response / .responses
ctx = await invoke(bot, "ping")
ctx.assert_content("Pong!")

# Fluent builder — when you need locale, roles, DM context, etc.
ctx = (
    FakeContextBuilder()
    .with_user(42, name="alice")
    .in_guild(100)
    .as_admin()
    .with_roles(999)
    .build()
)

# Plugin construction in tests — use __new__ and set _bot directly
plugin = MyPlugin.__new__(MyPlugin)
plugin._bot = bot   # set _bot, NOT bot (bot is a property that raises if _bot is None)
Plugin.__init__(plugin)
```

Available invoke helpers: `invoke`, `invoke_autocomplete`, `invoke_component`, `invoke_modal`, `invoke_user_command`, `invoke_message_command`.

**Channel send safety** — before calling `.send()` on any channel obtained from `ctx` or Discord, narrow its type first. Use the `SENDABLE_CHANNEL_TYPES` tuple (defined in `easycord/helpers/tools.py` or a local `_utils.py`). Bare `.send()` on unnarrowed channel types will fail at runtime on DM-incompatible channels.

```python
from easycord.helpers.tools import SENDABLE_CHANNEL_TYPES
if isinstance(channel, SENDABLE_CHANNEL_TYPES):
    await channel.send(...)
```

## Key invariants

- `ToolLimiter` methods are async — always `await check_limit(...)`.
- Cooldown sentinels in `LevelsPlugin._cooldowns` default to `float("-inf")`, not `0.0` — ensures first message always passes.
- `ctx.is_admin` is a property — never call `ctx.is_admin()`.
- `ctx.user` / `ctx.member` are correct; `ctx.author` does not exist.
- `@ai_tool` requires an explicit `ToolSafety` annotation to register.
- CI actions are pinned to `actions/checkout@v4` and `actions/setup-python@v5` — v6 does not exist.
- `sync_commands()` raises `RuntimeError` on removals unless `confirm_removals=True` is passed explicitly.
