# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
pip install -e ".[dev]"
pytest tests/
pytest tests/test_middleware.py -v
pytest tests/test_middleware.py::test_name -v
ruff check easycord tests --select E9,F63,F7,F82   # the blocking lint gate (syntax/undefined-name errors)
ruff check .                                        # full advisory lint (non-blocking in CI)
python scripts/verify_plugin_tests.py      # per-plugin test-count thresholds (all plugins ≥20)
python -m build --no-isolation   # plain `python -m build` needs a working venv module
python scripts/check_release_metadata.py   # version consistency across pyproject/__init__/CHANGELOG
python scripts/bump_version.py 5.50.0      # bump version across all tracked files
pyright                                    # static type checking (pyrightconfig.json at root)
```

`pytest-asyncio` with `asyncio_mode = "auto"` — no manual event loop setup needed.

**CI PR gate** (`.github/workflows/tests.yml`, Python 3.10/3.11/3.12) runs, in order:
1. critical-error ruff (`--select E9,F63,F7,F82`, blocking)
2. full ruff (advisory)
3. `check_release_metadata.py` (version consistency)
4. `verify_plugin_tests.py` (per-plugin test thresholds)
5. `pytest` (all tests)

Reproduce a green run locally with: `ruff check --select E9,F63,F7,F82`, `ruff check .`, `python scripts/check_release_metadata.py`, `python scripts/verify_plugin_tests.py`, `pytest`. There is no ruff config file — only the explicit `--select` rule set is enforced as a gate.

The `easycord` console script (`easycord/cli.py`) is the dev-facing CLI: `easycord new`, `easycord doctor`, `easycord inspect`, `easycord sync-plan`, `easycord plugin create|check|discover`, `easycord test-template`, `easycord audit-tools`.

## Context

- [Documentation index](docs/README.md) — goal-based entry to all 23 user-facing guides; start here when a topic isn't listed below
- [Architecture](context/architecture.md) — layers, mixins, module map
- [Conventions](context/conventions.md) — naming rules, key invariants
- [Hot-Reload Development](docs/hot-reload-development.md) — `bot.run(reload=True)`, `on_reload()` hook
- [Middleware Patterns](docs/middleware-patterns.md) — composition, ordering, built-ins, testing
- [Error Handling](docs/error-handling.md) — command error waterfall, per-command/plugin/global handlers
- [Type Checking](docs/type-checking.md) — pyright config, discord.py gaps, plugin typing patterns

A root `AGENTS.md` is the Codex-facing twin of this file, maintained by hand — keep the two in sync when changing shared guidance.

## Architecture quick-reference

**Public API boundary** — `easycord/__init__.py` is the stable public surface; every `_`-prefixed module (`_bot_*.py`, `_context_*.py`, `_i18n_*.py`, `_command_*.py`, `_plugin_scanner.py`, plugin `_*.py` helpers) is internal and may change without notice. Import from `easycord`, never from `easycord._*`. AI provider classes are re-exported lazily from the top level via `easycord.__getattr__`. Targets Python 3.10+ / `discord.py>=2.7.1,<3`.

**Bot** (`bot.py`) composes `discord.Client` with four mixins — `_bot_commands.py`, `_bot_events.py`, `_bot_guild.py`, `_bot_plugins.py`. Each mixin imports `_BotBase` only under `TYPE_CHECKING` using a per-module `_MixinBase = _BotBase` alias so static checkers see the full `Bot` surface but no runtime import cycle is created. Never instantiate `_BotBase`; it is a phantom type only.

**Context** (`context.py` + `_context_*.py`) — use `ctx.user` / `ctx.member`. `ctx.author` does not exist. `ctx.is_admin` is a property, not a method.

**Plugin** (`plugin.py`) — subclass `Plugin`, decorate methods with `@slash` / `@on`, then call `bot.add_plugin(plugin_instance)`. The plugin scanner (`_plugin_scanner.py`) wires commands automatically. Per-guild state belongs in the database layer (`database.py` — `SQLiteDatabase` / `MemoryDatabase`, per-guild namespaced, typed `GuildRecord` rows), never on `self` (the Plugin instance). Authoring decorators live in `decorators.py`: `@slash`/`@slash_command`, `@on`, `@autocomplete`, `@component`, `@modal`, `@message_command`, `@user_command`, `@task`, `@ai_tool`, `@cooldown`, `@require_permissions`, `@install_type`, `@premium_required`. `bot.load_builtin_plugins()` loads the starter set (welcome, tags, polls, levels) from `builtin_plugins.py`.

**i18n** — `LocalizationManager` in `i18n.py`, split across `_i18n_locale.py`, `_i18n_diagnostics.py`, `_i18n_validation.py`. Diagnostic modes: `SILENT`, `WARN`, `STRICT`. Never hardcode response strings in plugins; always look them up via `ctx.t(...)`.

**AI orchestration** — `orchestrator.py` routes via `FallbackStrategy` (advances through providers on exhaustion, raises `IndexError` when all fail). AI providers are lazy-imported from `plugins/_ai_providers.py` via `easycord.__getattr__`. Tools register into the `ToolRegistry` in `tools.py` and are gated by `ToolSafety` — `SAFE` (read-only), `CONTROLLED` (validated), `RESTRICTED` (never exposed). Per-tool rate limiting lives in `tool_limits.py`; `ToolLimiter` methods (`check_limit`, `reset_user`, `reset_tool`) are async — always await them.

**Interaction registry** — `registry.py` is EasyCord's authoritative inventory of slash commands, context menus, components, modals, and autocomplete callbacks (and route-pattern matching for component custom_ids). `discord.app_commands.CommandTree` stays the Discord-side sync backend; the registry is the framework's own source of truth that the command-registration layer feeds.

**Middleware** — `middleware.py` provides the `MiddlewareFn` chain (`Callable[[Context, next], Awaitable[None]]`) wrapped around command dispatch for cross-cutting concerns (logging, auth, rate limiting). See [Middleware Patterns](docs/middleware-patterns.md) for composition/ordering.

**Command registration split** — `_command_callbacks.py` builds the actual callback wrappers; `_command_registration.py` handles option injection, choice population, and context-menu registration. Both are consumed by `_bot_commands.py`. Registration validates Discord constraints upfront: name ≤ 32 chars matching `[-_a-z0-9]`, description ≤ 100 chars, ≤ 25 options, ≤ 25 choices per option — violations raise `ValueError` before hitting the tree.

**Extensibility** — `event_bus.py` exposes `EventBus` for async pub/sub between plugins (`.subscribe(event, callback)` / `.publish(event, **kwargs)`). `hooks.py` exposes `HookRegistry` with four built-in hooks: `before_command`, `after_command`, `on_plugin_load`, `on_plugin_unload`.

**Deprecation** — `@deprecated(version, replacement)` and `@version_introduced(version)` in `easycord/decorators.py`. `@deprecated` emits `DeprecationWarning` at call time with a migration hint; both are exported from `easycord`.

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

# PluginTestSuite — base class that wires up bot + helpers automatically
class TestMyPlugin(PluginTestSuite):
    def setup_method(self):
        super().setup_method()
        self.plugin = self.make_plugin(MyPlugin)

    async def test_something(self):
        ctx = await self.invoke_command("mycommand")
        self.assert_last_response(ctx, "expected text")
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
- CI actions are pinned to `actions/checkout@v7` and `actions/setup-python@v5` — dependabot manages major bumps; keep this line in sync with `.github/workflows/`.
- `sync_commands()` raises `RuntimeError` on removals unless `confirm_removals=True` is passed explicitly.
- `Plugin.on_reload()` fires on the **new** instance after a hot-reload swap, not the old one; `self.bot` is available when it fires. Only fires on success — never on failure.
- `bot.run(reload=True)` is dev-only — the mtime watcher runs as a background task in `_background_tasks` and is cancelled by `close()`.
- `_MixinBase` pattern — every `_bot_*.py` mixin uses `if TYPE_CHECKING: from ._bot_base import _BotBase; _MixinBase = _BotBase` so Pylance sees the full `Bot` surface without a runtime import cycle. Never set `_MixinBase = object` without the `TYPE_CHECKING` guard.
- Event-path plugins (`@on("message")` and friends) must route every destructive action through one governed method that owns rate limiting, channel narrowing, and Discord error handling, and must never let a Discord exception escape into the dispatcher — see `AIModeratorPlugin._execute_action`. The broad `except Exception` there is intentional (`# noqa: BLE001`); only non-destructive branches (e.g. `notify_only`) stay inline.
- `ServerConfigStore`'s per-guild lock makes a single `load()` or `save()` atomic, **not** a `load → modify → save` sequence. Any config read-modify-write must go through `ServerConfigStore.mutate(guild_id, fn)` (holds the per-guild lock across the whole load/modify/save). `fn` must be synchronous and local — no Discord/network I/O while the lock is held (do `channel.send` / `add_roles` outside `mutate`). `PluginConfigManager.update` / `set_default` already route through it; `get()` stays a pure read except on first-time default creation. Plugins that instead keep their own per-guild lock and hold it across the entire RMW (economy `_balance_lock`, auto_role/birthday/giveaway/polls `_guild_lock`) are the equivalent correct pattern — never load/modify/save unguarded.
