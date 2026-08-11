# CLAUDE.md

# Hard Rule — Graph First, Always

For **any** question about this codebase — what exists, how it connects, what a module does, bug history, test patterns, what changed — query the knowledge graph **before** opening any source file, doc file, or context file.

Graph location: `C:\Users\Tom\Code projects\EasyCord\graphify-out\graph.json`  
Interactive: `C:\Users\Tom\Code projects\EasyCord\graphify-out\graph.html` (open in browser)

```bash
# Run from C:\Users\Tom\Code projects\EasyCord
graphify query "<question>"          # BFS traversal — broad context
graphify path "NodeA" "NodeB"        # shortest path between two concepts
graphify explain "NodeName"          # plain-language node summary
```

The graph (4,837 nodes, 10,488 edges, 225 communities, last updated 2026-07-11) covers code relationships, bugs B-001–B-021, Phase 1 completion state, CI changes, and planning artifacts. It is more accurate than the documentation files.

**Documentation files are potentially stale.** The `## Context` links below and files under `docs/` and `context/` are secondary/fallback references. Do not treat them as authoritative; prefer graph query results. Do not rebuild the graph unless explicitly asked. Do not read vault files at `C:\Users\Tom\Desktop\Wiki` — that system is deprecated.

---

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

The `easycord` console script (`easycord/cli.py`) is the dev-facing CLI: `easycord new`, `easycord doctor`, `easycord inspect`, `easycord sync-plan`, `easycord plugin create|check|discover`, `easycord doc serve`.

## Troubleshooting

**Graph not found or stale?**
- Ensure you're running graphify from the correct directory: `cd /path/to/EasyCord && graphify query ...`.
- If graphify is not installed, install it with `pip install graphify-python`.
- To check the last graph update: look at the `last updated` field in CLAUDE.md or inspect the graph metadata in `graphify-out/graph.json`.
- Graph freshness target: updated within 7 days of each release. If stale, check `.planning/STATE.md` for active work.

**Type-checking gaps in discord.py?**
- discord.py has incomplete or incorrectly-typed stubs in some areas (e.g., optional attributes, union return types). See `context/type-checking.md` for known issues and workarounds. Most gaps are resolved by narrowing with `assert` or `if isinstance` before use.

**CI actions failing?**
- GitHub Actions are pinned to `actions/checkout@v7` and `actions/setup-python@v5`. Dependabot manages major version bumps. If a workflow fails unexpectedly, check `.github/workflows/` for any manual overrides.

## Context

> **Note:** these links may not reflect the current codebase. Prefer `graphify query` over opening them directly.

- [Documentation index](docs/README.md) — goal-based entry to all 30+ user-facing guides; start here when a topic isn't listed below
- [Architecture](context/architecture.md) — layers, mixins, module map
- [Conventions](context/conventions.md) — naming rules, key invariants
- [Hot-Reload Development](docs/hot-reload-development.md) — `bot.run(reload=True)`, `on_reload()` hook
- [Middleware Patterns](docs/middleware-patterns.md) — composition, ordering, built-ins, testing
- [Error Handling](docs/error-handling.md) — command error waterfall, per-command/plugin/global handlers
- [Type Checking](docs/type-checking.md) — pyright config, discord.py gaps, plugin typing patterns
- [AGENTS.md](AGENTS.md) — Codex-facing twin of this file; keep both in sync when changing shared guidance

## Documentation Freshness & Confidence

Documentation files are marked with a `<!-- Last verified: YYYY-MM-DD -->` comment to signal how recent a review was.

- **Last verified < 7 days**: confidence high, safe to use as reference
- **Last verified > 30 days**: mark as potentially stale; prefer graph query or source inspection
- **No verification date**: treat as secondary; verify with graphify or code audit before trusting

This file (CLAUDE.md) and AGENTS.md are manually maintained and verified continuously as part of active work.

## Architecture quick-reference

**Public API boundary** — `easycord/__init__.py` is the stable public surface; every `_`-prefixed module (`_bot_*.py`, `_context_*.py`, `_i18n_*.py`, `_command_*.py`, `_plugin_scanner.py`, plugins with leading `_`) is internal and may change without notice.

**Bot** (`bot.py`) composes `discord.Client` with four mixins — `_bot_commands.py`, `_bot_events.py`, `_bot_guild.py`, `_bot_plugins.py`. Each mixin imports `_BotBase` only under `TYPE_CHECKING` to avoid circular dependencies and runtime overhead. See `_bot_base.py` for the shared interface.

**Context** (`context.py` + `_context_*.py`) — use `ctx.user` / `ctx.member`. `ctx.author` does not exist. `ctx.is_admin` is a property, not a method. When narrowing `ctx.guild`, use `assert ctx.guild is not None` for guild-only slash commands to satisfy Pyright; for event handlers that may run in DMs, use `if ctx.guild is None: return`.

**Plugin** (`plugin.py`) — subclass `Plugin`, decorate methods with `@slash` / `@on`, then call `bot.add_plugin(plugin_instance)`. The plugin scanner (`_plugin_scanner.py`) wires commands automatically on add.

**i18n** — `LocalizationManager` in `i18n.py`, split across `_i18n_locale.py`, `_i18n_diagnostics.py`, `_i18n_validation.py`. Diagnostic modes: `SILENT`, `WARN`, `STRICT`. Never hardcode response strings for user-facing commands — always use `ctx.localize(...)` to support multi-language deployments.

**AI orchestration** — `orchestrator.py` routes via `FallbackStrategy` (advances through providers on exhaustion, raises `IndexError` when all fail). AI providers are lazy-imported from `plugins/ai_*` and must implement `AIProvider` protocol. See `docs/ai-orchestration.md` for patterns.

**Interaction registry** — `registry.py` is EasyCord's authoritative inventory of slash commands, context menus, components, modals, and autocomplete callbacks (and route-pattern matching for component/modal IDs). Sync with `sync_commands()`.

**Middleware** — `middleware.py` provides the `MiddlewareFn` chain (`Callable[[Context, next], Awaitable[None]]`) wrapped around command dispatch for cross-cutting concerns (logging, auth, rate limiting). Execution order: outer middleware runs first, inner last.

**Command registration split** — `_command_callbacks.py` builds the actual callback wrappers; `_command_registration.py` handles option injection, choice population, and context-menu registration. Cooldown buckets are managed per-callback and pruned by the bot-level `_cooldown_cleanup_loop` (every 30 seconds by default).

**Extensibility** — `event_bus.py` exposes `EventBus` for async pub/sub between plugins (`.subscribe(event, callback)` / `.publish(event, **kwargs)`). Listeners fire in registration order; subscriber failures are logged with handler identity via `getattr(callback, "__qualname__", repr(callback))`. `hooks.py` exposes `HookRegistry` with four built-in hooks: `before_invoke`, `after_invoke`, `on_error`, `on_command_not_found`.

**Deprecation** — `@deprecated(version, replacement)` and `@version_introduced(version)` in `easycord/decorators.py`. `@deprecated` emits `DeprecationWarning` at call time with a migration hint; enforcement is configurable via the bot's `deprecation_warnings` flag.

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

**Channel send safety** — before calling `.send()` on any channel obtained from `ctx` or Discord, narrow its type first. Use the `SENDABLE_CHANNEL_TYPES` tuple (defined in `easycord/helpers/tools.py`):

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
- `_MixinBase` pattern — every `_bot_*.py` mixin uses `if TYPE_CHECKING: from ._bot_base import _BotBase; _MixinBase = _BotBase` so Pylance sees the full `Bot` surface without a runtime import cycle.
- Event-path plugins (`@on("message")` and friends) must route every destructive action through one governed method that owns rate limiting, channel narrowing, and Discord error handling, and must catch at least `discord.Forbidden`, `discord.NotFound`, and `discord.HTTPException` (the latter subsumes the first two).
- `ServerConfigStore`'s per-guild lock makes a single `load()` or `save()` atomic, **not** a `load → modify → save` sequence. Any config read-modify-write must go through `ServerConfigStore.mutate(guild_id, fn)` where `fn` is synchronous and does no Discord I/O (the lock is held while `fn` runs).
