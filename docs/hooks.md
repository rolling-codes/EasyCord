# Lifecycle Hooks

`HookRegistry` lets you attach callbacks to key bot events without subclassing `Bot` or monkey-patching internals. `bot.hooks` is created automatically.

Four hooks are built in:

| Hook | When it fires |
|---|---|
| `before_command` | Before a slash command callback is invoked |
| `after_command` | After a slash command callback returns (even on error) |
| `on_plugin_load` | After a plugin's `on_load()` completes |
| `on_plugin_unload` | After a plugin's `on_unload()` completes |

---

## Registering a hook

```python
async def log_command(ctx, name: str) -> None:
    print(f"/{name} invoked by {ctx.user} in guild {ctx.guild}")

bot.hooks.register("before_command", log_command)
```

Both sync and async callbacks are accepted. Multiple callbacks for the same hook are called in registration order.

---

## Common patterns

### Audit log

```python
async def audit(ctx, name: str) -> None:
    await db.insert_audit_event(
        user_id=ctx.user.id,
        guild_id=ctx.guild.id if ctx.guild else None,
        command=name,
    )

bot.hooks.register("before_command", audit)
```

### Timing

```python
import time

_command_start: dict[int, float] = {}

def start_timer(ctx, name: str) -> None:
    _command_start[ctx.user.id] = time.monotonic()

async def record_duration(ctx, name: str) -> None:
    elapsed = time.monotonic() - _command_start.pop(ctx.user.id, 0)
    await metrics.record(name, elapsed)

bot.hooks.register("before_command", start_timer)
bot.hooks.register("after_command", record_duration)
```

### Plugin lifecycle tracking

```python
async def on_load(plugin_name: str) -> None:
    print(f"[{plugin_name}] loaded")

async def on_unload(plugin_name: str) -> None:
    print(f"[{plugin_name}] unloaded")

bot.hooks.register("on_plugin_load", on_load)
bot.hooks.register("on_plugin_unload", on_unload)
```

---

## Registering from a plugin

Register in `on_load` and always unregister in `on_unload`:

```python
class MonitorPlugin(Plugin):
    async def on_load(self) -> None:
        self.bot.hooks.register("before_command", self._before)
        self.bot.hooks.register("after_command", self._after)

    async def on_unload(self) -> None:
        # HookRegistry does not auto-remove plugin callbacks on unload and
        # has no public unregister() method. Remove via the internal
        # _callbacks dict to avoid stale references.
        self.bot.hooks._callbacks["before_command"].remove(self._before)
        self.bot.hooks._callbacks["after_command"].remove(self._after)

    async def _before(self, ctx, name: str) -> None:
        ...

    async def _after(self, ctx, name: str) -> None:
        ...
```

---

## API

### `register(hook_name, callback)`

Add a callback to the named hook.

Raises `ValueError` if `hook_name` is not one of the four built-in hooks.  
Raises `TypeError` if `callback` is not callable.

### `await fire(hook_name, **kwargs)`

Invoke all callbacks registered for `hook_name` with the given keyword arguments. The framework calls this automatically — you rarely need to call `fire` directly.

Raises `ValueError` for an unknown hook name.

---

## Testing

```python
from easycord.hooks import HookRegistry

async def test_before_hook_receives_command_name():
    registry = HookRegistry()
    received: list[str] = []

    registry.register("before_command", lambda ctx, name: received.append(name))
    await registry.fire("before_command", ctx=None, name="ping")

    assert received == ["ping"]
```
