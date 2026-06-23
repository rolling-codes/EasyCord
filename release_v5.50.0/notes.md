# EasyCord v5.50.0 Release Notes

Architecture and testing release. New cross-plugin communication primitives, full lifecycle hook coverage, a dedicated testing layer, hot-reload with on_reload() lifecycle, command validation, AI provider observability, bot permission auditing, and a near-doubling of the test suite.

---

## New features

### EventBus — async pub/sub between plugins

Plugins can now communicate without importing each other. One plugin publishes a named event; any subscriber receives it — with full exception isolation so one bad handler never silences others.

```python
# levels_plugin.py
await self.bot.event_bus.publish(
    "user_leveled_up",
    user_id=ctx.user.id,
    guild_id=ctx.guild.id,
    level=new_level,
)

# rewards_plugin.py
async def on_load(self) -> None:
    self.bot.event_bus.subscribe("user_leveled_up", self._grant_reward)

async def _grant_reward(self, user_id: int, guild_id: int, level: int) -> None:
    if level % 10 == 0:
        await self._assign_milestone_role(guild_id, user_id, level)
```

`bot.event_bus` is initialized automatically. See [docs/event-bus.md](https://github.com/rolling-codes/EasyCord/blob/main/docs/event-bus.md).

---

### HookRegistry — lifecycle hooks

Attach callbacks to four built-in bot lifecycle events without subclassing `Bot`:

```python
async def audit_command(ctx, name: str) -> None:
    await db.log(user_id=ctx.user.id, command=name)

bot.hooks.register("before_command", audit_command)
bot.hooks.register("after_command", record_timing)
bot.hooks.register("on_plugin_load", lambda plugin_name: print(f"{plugin_name} loaded"))
bot.hooks.register("on_plugin_unload", lambda plugin_name: ...)
```

Both sync and async callbacks accepted. `bot.hooks` is initialized automatically. See [docs/hooks.md](https://github.com/rolling-codes/EasyCord/blob/main/docs/hooks.md).

---

### `@deprecated` and `@version_introduced`

```python
from easycord import deprecated, version_introduced

@deprecated("5.50.0", replacement="bot.event_bus.subscribe")
def on_user_join(self, callback):
    ...
# → DeprecationWarning at call time with migration hint

@version_introduced("5.50.0")
def new_event_api(self, event: str, callback) -> None:
    ...
```

See [docs/deprecation.md](https://github.com/rolling-codes/EasyCord/blob/main/docs/deprecation.md).

---

### PluginTestSuite — test plugins without Discord

Write plugin tests with zero boilerplate. No Discord connection required.

```python
from easycord.testing import PluginTestSuite

class TestCounterPlugin(PluginTestSuite):
    def setup_method(self):
        super().setup_method()
        self.plugin = self.make_plugin(CounterPlugin)

    async def test_first_increment(self):
        ctx = await self.invoke_command("increment")
        self.assert_last_response(ctx, "Count: 1")
```

Available helpers: `invoke`, `invoke_autocomplete`, `invoke_component`, `invoke_modal`, `invoke_user_command`, `invoke_message_command`, `FakeContextBuilder`.

```python
ctx = (
    FakeContextBuilder()
    .with_user(42, name="alice")
    .in_guild(100)
    .as_admin()
    .with_roles(999)
    .with_locale("fr")
    .build()
)
```

See [docs/testing.md](https://github.com/rolling-codes/EasyCord/blob/main/docs/testing.md).

---

### Hot-reload with `on_reload()` lifecycle

`bot.run(reload=True)` watches plugin files for changes and hot-swaps them at runtime. The new `on_reload()` lifecycle method fires on the **new** instance after a successful swap, giving plugins a chance to migrate in-memory state.

```python
class StatefulPlugin(Plugin):
    def __init__(self):
        super().__init__()
        self._cache: dict[int, str] = {}

    async def on_reload(self) -> None:
        # self._cache is empty on the new instance; restore from your DB if needed
        self._cache = await db.load_cache()
```

The watcher polls every 3 seconds (down from 1 s), skips plugins whose `__init__` requires arguments, and logs a clear error if reload fails — the original instance is kept running.

See [docs/hot-reload-development.md](https://github.com/rolling-codes/EasyCord/blob/main/docs/hot-reload-development.md).

---

### Command registration validation

Discord API constraints are now enforced at registration time rather than at sync, with clear error messages:

```
ValueError: Command name 'My_Command' contains invalid characters.
  Names must match [-_a-z0-9] and be 1–32 characters.
  Got: 'My_Command'

ValueError: Description for command 'ping' is 107 characters (max 100).
```

Constraints validated: name ≤ 32 chars matching `[-_a-z0-9]`, description ≤ 100 chars, ≤ 25 options per command, ≤ 25 choices per option.

---

### Bot permission validator

At `on_ready`, EasyCord now checks every loaded plugin's commands against the bot's actual guild permissions and logs a WARNING for each gap:

```
WARNING easycord: Plugin 'ModerationPlugin' requires 'ban_members' permission but bot
lacks it in guild 'My Server' (ID: 123456789) — command /ban may not work as expected
```

No code changes needed — the validator runs automatically for every loaded plugin.

---

### AI provider fallback metrics

Each provider attempt is now logged so you can see exactly which provider handled a request and why fallback occurred:

```
DEBUG  easycord.orchestrator: AI request: trying provider ClaudeProvider (attempt 1/2)
WARNING easycord.orchestrator: AI provider ClaudeProvider failed (RateLimitError: …), falling back to next
DEBUG  easycord.orchestrator: AI request handled by provider OpenAIProvider
ERROR  easycord.orchestrator: All AI providers exhausted after 2 attempt(s)
```

---

### Database backend in `/health`

The `/health` command embed now shows which database backend is active (`sqlite` or `memory`), its connection status, and round-trip latency.

---

### `pyrightconfig.json` for plugin authors

A standard-mode Pyright configuration is included at the repo root. It enforces the typing patterns documented in [docs/type-checking.md](https://github.com/rolling-codes/EasyCord/blob/main/docs/type-checking.md) and is pre-configured for EasyCord's `_MixinBase` and `TYPE_CHECKING` conventions.

---

## Fixes

- **`format_number` O(n²) → O(n)**: `list.insert(0, …)` in the thousands-grouping loop replaced with `list.append` + `"".join(reversed(parts))`.
- **Conversation summarization**: silent `except Exception: pass` replaced with `logger.warning(…)` — failures are now visible in logs.
- **Birthday plugin task leak**: role-removal tasks created with `asyncio.create_task` were untracked. They are now held in `_role_tasks` and cancelled during `on_unload`.
- **`asyncio.iscoroutinefunction` deprecation**: replaced with `inspect.iscoroutinefunction` in `EventBus` and `HookRegistry` (deprecated in Python 3.16).
- **Release-drafter**: added `paths-ignore` for version-bump files so pushing a `chore: release vX.Y.Z` commit to `main` no longer triggers a redundant draft-release update.
- **CodeQL findings**: `test_hot_reload.py` "statement has no effect" on `await in_flight` resolved.
- **Pyright**: narrowed `# type: ignore` to specific error codes throughout; `dict` bare generic in `_format_messages` and `get_tool_info` replaced with typed equivalents.

---

## Tests

1,169 tests total (up from ~900). New test files in this release:

| File | What it covers |
|---|---|
| `tests/test_event_bus.py` | EventBus subscribe/unsubscribe/publish, exception isolation, async gathering |
| `tests/test_hooks.py` | HookRegistry all four hooks, sync+async callbacks, error cases |
| `tests/test_hot_reload.py` | `_hot_reload_plugin`, `_hot_reload_loop`, `on_reload()`, logging levels |
| `tests/test_command_registration.py` | Constraint validation for name/description/options/choices |
| `tests/test_cooldown_cleanup.py` | TTL sweep loop, concurrent deletion safety |
| `tests/test_deprecation.py` | `@deprecated` warning emission, `@version_introduced` attributes |
| `tests/test_health.py` | `/health` embed, DB backend field, SQLite + memory paths |
| `tests/test_orchestrator.py` | Provider fallback, metrics logging, tool loop |
| `tests/test_permission_validator.py` | `_validate_plugin_permissions` per guild |
| `tests/test_plugin_test_suite.py` | `PluginTestSuite` helpers |
| `tests/test_new_decorators.py` | `@deprecated`, `@version_introduced`, `@cooldown` |

Patch coverage: 74% → 82% (above the 80% floor).

---

## Documentation

Ten new guides:

- [Event Bus](https://github.com/rolling-codes/EasyCord/blob/main/docs/event-bus.md) — subscribe, publish, exception isolation, testing patterns
- [Lifecycle Hooks](https://github.com/rolling-codes/EasyCord/blob/main/docs/hooks.md) — all four hooks, registering from plugins, testing
- [Deprecation Helpers](https://github.com/rolling-codes/EasyCord/blob/main/docs/deprecation.md) — `@deprecated`, `@version_introduced`, suppressing warnings
- [Testing Commands](https://github.com/rolling-codes/EasyCord/blob/main/docs/testing.md) — `PluginTestSuite`, `FakeContextBuilder`, `invoke_*` helpers
- [Task Scheduling](https://github.com/rolling-codes/EasyCord/blob/main/docs/task-scheduling.md) — `@task` decorator, intervals, error restart, lifecycle
- [Subcommand Groups](https://github.com/rolling-codes/EasyCord/blob/main/docs/subcommand-groups.md) — `SlashGroup`, permission inheritance, guild restrictions
- [Interactive UI](https://github.com/rolling-codes/EasyCord/blob/main/docs/context-interactive-ui.md) — `ctx.confirm()`, `ctx.paginate()`, `ctx.ask_form()`, `ctx.choose()`, `ctx.prompt()`
- [Conversation Memory](https://github.com/rolling-codes/EasyCord/blob/main/docs/conversation-memory.md) — multi-turn AI context, eviction, `ctx.ai()` vs `Orchestrator`
- [Built-in Plugins](https://github.com/rolling-codes/EasyCord/blob/main/docs/builtin-plugins.md) — all 28 bundled plugins with setup and storage notes
- [Context Reference](https://github.com/rolling-codes/EasyCord/blob/main/docs/context-reference.md) — full `Context` API: responses, DMs, moderation, channels, members

---

## Install

```bash
# Wheel
pip install "https://github.com/rolling-codes/EasyCord/releases/download/v5.50.0/easycord-5.50.0-py3-none-any.whl"

# Source distribution
pip install "https://github.com/rolling-codes/EasyCord/releases/download/v5.50.0/easycord-5.50.0.tar.gz"
```
