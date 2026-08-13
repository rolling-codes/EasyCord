# Request Lifecycle

Every slash command you run passes through a journey: it arrives as a Discord interaction, flows through middleware (guards, logging, rate limiting), reaches your command handler, then either succeeds or hits an error handler. This guide explains that flow and how to hook into it.

---

## How a Request Flows

```
Discord interaction arrives
    ↓
1. Middleware 1: before proceed()
2. Middleware 2: before proceed()
   ...
   → Command Handler runs
   ...
2. Middleware 2: after proceed()
1. Middleware 1: after proceed()
    ↓
Response sent back to Discord
```

If **any** middleware skips `proceed()`, the command never runs. If the handler **raises an exception**, it's caught by error handlers (explained below).

---

## Middleware: Guards, Logging, Rate Limiting

Middleware is a function that wraps every command. It can:
- **Block** the command (skip `proceed()`)
- **Log** the invocation
- **Rate limit** the user
- **Transform** the context

### Built-in Middleware

All built-ins live in `easycord.middleware`:

```python
from easycord.middleware import (
    guild_only,
    dm_only,
    admin_only,
    allowed_roles,
    has_permission,
    channel_only,
    boost_only,
    rate_limit,
    log_middleware,
    catch_errors,
)
```

#### `guild_only()`
Block commands invoked in DMs:

```python
bot.use(guild_only())
```

#### `dm_only()`
Block commands invoked in guilds — only DMs allowed:

```python
bot.use(dm_only())
```

#### `admin_only(message=None)`
Block unless the invoking member has the `administrator` permission:

```python
bot.use(admin_only())
bot.use(admin_only(message="Admins only."))
```

#### `allowed_roles(*role_ids, message=None)`
Block unless the invoking member holds at least one of the given role IDs:

```python
STAFF_ROLE = 123456789
MOD_ROLE = 987654321
bot.use(allowed_roles(STAFF_ROLE, MOD_ROLE))
bot.use(allowed_roles(STAFF_ROLE, message="Staff only."))
```

#### `has_permission(*permissions, message=None)`
Block unless the invoking member holds **all** of the named `discord.Permissions`:

```python
bot.use(has_permission("kick_members", "ban_members"))
```

#### `channel_only(*channel_ids, message=None)`
Block commands invoked outside the specified channel(s):

```python
COMMANDS_CHANNEL = 111111111
bot.use(channel_only(COMMANDS_CHANNEL))
```

#### `boost_only(message=None)`
Block unless the invoking member is boosting the server:

```python
bot.use(boost_only())
```

#### `rate_limit(limit=5, window=10.0)`
Per-user sliding-window rate limiter. Allow at most `limit` commands per user within `window` seconds:

```python
bot.use(rate_limit(limit=5, window=10.0))  # 5 commands per 10 seconds
```

#### `log_middleware(level=logging.INFO, fmt="/{command} invoked by {user} in {guild}")`
Log every slash command invocation:

```python
bot.use(log_middleware())
bot.use(log_middleware(level=logging.DEBUG, fmt="cmd={command} user={user}"))
```

#### `catch_errors(message=None)`
Wrap the downstream chain in a broad `except`. Logs unhandled exceptions and sends an ephemeral error reply. **Place this first** so it catches errors from all other middleware:

```python
bot.use(catch_errors())
bot.use(catch_errors(message="Something went wrong. Try again."))
```

### Writing Custom Middleware

Middleware is a function with this signature:

```python
async def my_middleware(ctx: Context, proceed: Callable[[], Awaitable[None]]) -> None:
    # Code here runs BEFORE the next middleware and command
    await proceed()
    # Code here runs AFTER the command finishes
```

Await `proceed()` to continue to the next layer. Skip it to block the command.

#### Function Pattern

For stateless middleware, return the handler from a factory:

```python
from easycord.middleware import MiddlewareFn
from easycord.context import Context

def require_prefix(prefix: str) -> MiddlewareFn:
    """Block commands unless the username starts with *prefix*."""
    
    async def handler(ctx: Context, proceed):
        if not ctx.user.name.startswith(prefix):
            await ctx.respond(f"Only users starting with '{prefix}' allowed.", ephemeral=True)
            return
        await proceed()
    
    return handler

bot.use(require_prefix("admin_"))
```

#### Class Pattern

For middleware that accumulates state, use a class with `__call__`:

```python
import time
from collections import defaultdict

class AuditLog:
    """Record every command invocation with a running counter per user."""
    
    def __init__(self):
        self._counts = defaultdict(int)
    
    async def __call__(self, ctx, proceed):
        self._counts[ctx.user.id] += 1
        print(f"[audit] user={ctx.user.id} cmd={ctx.command_name} total={self._counts[ctx.user.id]}")
        await proceed()

audit = AuditLog()
bot.use(audit)
```

The same instance is retained for the lifetime of the bot, so state persists.

### Ordering Matters

Middleware runs in **registration order**. The first registered runs outermost:

```
registered: [A, B, C]
runs:       A → B → C → handler → C → B → A
```

Code **before** `await proceed()` in A runs before B and C.
Code **after** `await proceed()` in A runs after B and C finish.

**Good order:**
```python
bot.use(catch_errors())      # Outermost: catches all errors
bot.use(guild_only())        # Auth first
bot.use(admin_only())        # More specific auth
bot.use(rate_limit(...))     # After auth: only authed users hit the limit
bot.use(log_middleware())    # After rate limit: log successful invocations
```

**Common mistakes:**
- `catch_errors` not first → errors from earlier middleware escape
- Logging before auth → blocked requests still logged (noise)
- Rate limiting before auth → blocklist fills even for unauthorized users

---

## Error Handling: The Waterfall

When a command raises an exception, EasyCord checks this chain in order. The **first match wins**:

```
1. Per-command @command_error handler
2. Plugin on_error() hook
3. Global @bot.on_error handler
4. Framework fallback (re-raise or log)
```

### Per-Command Error Handler

Use `@command_error` when one command has known failure modes:

```python
from easycord import Plugin, slash, command_error

class MathPlugin(Plugin):
    
    @slash(description="Divide two numbers")
    async def divide(self, ctx, a: int, b: int):
        await ctx.respond(str(a // b))
    
    @command_error("divide")  # Name must match the command
    async def divide_error(self, ctx, exc: Exception):
        if isinstance(exc, ZeroDivisionError):
            await ctx.respond("Cannot divide by zero.", ephemeral=True)
        else:
            await ctx.respond("Math failed. Try again.", ephemeral=True)
```

The `exc` parameter is whatever exception the command raised.

### Plugin-Scoped Error Handler

Override `on_error(self, ctx, exc)` to handle errors from all commands in a plugin:

```python
import logging
from easycord import Plugin, slash

logger = logging.getLogger(__name__)

class ShopPlugin(Plugin):
    
    @slash(description="Buy an item")
    async def buy(self, ctx, item: str):
        ...
    
    @slash(description="Sell an item")
    async def sell(self, ctx, item: str):
        ...
    
    async def on_error(self, ctx, exc: Exception) -> None:
        if isinstance(exc, ValidationError):
            await ctx.respond(exc.user_message(ctx), ephemeral=True)
        else:
            logger.exception("ShopPlugin error", exc_info=exc)
            await ctx.respond("Something went wrong. Try again.", ephemeral=True)
```

### Global Bot Error Handler

Register a fallback for any exception that reaches the bot level:

```python
import logging
from easycord import Bot

logger = logging.getLogger(__name__)
bot = Bot(token="...", auto_sync=False)

@bot.on_error
async def handle_error(ctx, exc: Exception) -> None:
    logger.exception("Unhandled error", exc_info=exc)
    if ctx is not None:  # ctx can be None for background tasks
        await ctx.respond("An unexpected error occurred.", ephemeral=True)
```

### Best Practices

- **Always respond to the user** — Discord interactions expire after 15 minutes. If you don't respond, the user sees a generic "interaction failed" with no context.
- **Use `ephemeral=True` for errors** — Error messages shouldn't clutter the channel.
- **Don't leak internal state** — Stack traces, SQL, file paths must not appear in user messages. Log details; show generic messages.
- **Distinguish user errors from system errors**:
  - `ValidationError` = user mistake → respond with the validation message
  - `discord.HTTPException` = system failure → log it, send generic retry message
- **Handle `ctx is None`** — Background tasks call handlers with `ctx=None`. Guard before calling any `ctx.*` method.
- **Log unexpected errors** — Use `logger.exception("msg", exc_info=exc)` to capture the full traceback.

### Common Exceptions

| Exception | When | What to do |
|-----------|------|-----------|
| `discord.NotFound` | Interaction expired (>15 min); channel/message deleted | Log and skip — can't respond |
| `discord.Forbidden` | Bot lacks permission | Respond that bot needs a permission |
| `discord.HTTPException` | API failure (rate limit, server error) | Respond with retry prompt; log status |
| `ValidationError` | Input validation failed | Respond with `exc.user_message(ctx)` |
| `IndexError` (from orchestrator) | All AI providers exhausted | Respond that AI service unavailable |

---

## Lifecycle Hooks

Hooks let you attach callbacks to key bot events without subclassing or monkey-patching. `bot.hooks` is created automatically.

Four hooks are built in:

| Hook | When it fires | Callback signature |
|---|---|---|
| `before_command` | Before command handler runs | `async def (ctx, name: str)` |
| `after_command` | After command handler returns | `async def (ctx, name: str)` |
| `on_plugin_load` | After plugin's `on_load()` completes | `async def (plugin_name: str)` |
| `on_plugin_unload` | After plugin's `on_unload()` completes | `async def (plugin_name: str)` |

### Registering a Hook

```python
async def log_command(ctx, name: str) -> None:
    print(f"/{name} invoked by {ctx.user} in guild {ctx.guild}")

bot.hooks.register("before_command", log_command)
```

Both sync and async callbacks are accepted. Multiple callbacks fire in registration order.

### Practical Examples

#### Audit Log

```python
async def audit(ctx, name: str) -> None:
    await db.insert_audit_event(
        user_id=ctx.user.id,
        guild_id=ctx.guild.id if ctx.guild else None,
        command=name,
    )

bot.hooks.register("before_command", audit)
```

#### Timing Commands

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

#### Plugin Lifecycle Tracking

```python
async def on_load(plugin_name: str) -> None:
    print(f"[{plugin_name}] loaded")

async def on_unload(plugin_name: str) -> None:
    print(f"[{plugin_name}] unloaded")

bot.hooks.register("on_plugin_load", on_load)
bot.hooks.register("on_plugin_unload", on_unload)
```

### Registering from a Plugin

Always unregister in `on_unload` to avoid stale references:

```python
class MonitorPlugin(Plugin):
    async def on_load(self) -> None:
        self.bot.hooks.register("before_command", self._before)
    
    async def on_unload(self) -> None:
        self.bot.hooks.unregister("before_command", self._before)
    
    async def _before(self, ctx, name: str) -> None:
        print(f"Command: {name}")
```

---

## Testing

### Middleware Testing

```python
import pytest
from easycord import Bot, Plugin, slash
from easycord.testing import invoke

@pytest.mark.asyncio
async def test_rate_limit_blocks_after_limit():
    from easycord.middleware import rate_limit
    
    bot = Bot(auto_sync=False, db_backend="memory")
    bot.use(rate_limit(limit=2, window=10.0))
    
    class PingPlugin(Plugin):
        @slash(description="Ping")
        async def ping(self, ctx):
            await ctx.respond("Pong!")
    
    try:
        bot.add_plugin(PingPlugin())
        
        ctx1 = await invoke(bot, "ping")
        assert ctx1.last_response == "Pong!"
        
        ctx2 = await invoke(bot, "ping")
        assert ctx2.last_response == "Pong!"
        
        ctx3 = await invoke(bot, "ping")
        assert "rate limit" in ctx3.last_response.lower()  # Should be blocked
    finally:
        await bot.close()
```

### Error Handler Testing

```python
@pytest.mark.asyncio
async def test_command_error_handler():
    from easycord import command_error
    
    class MathPlugin(Plugin):
        @slash(description="Divide")
        async def divide(self, ctx, a: int, b: int):
            await ctx.respond(str(a // b))
        
        @command_error("divide")
        async def divide_error(self, ctx, exc):
            await ctx.respond("Cannot divide!", ephemeral=True)
    
    bot = Bot(auto_sync=False, db_backend="memory")
    try:
        bot.add_plugin(MathPlugin())
        
        ctx = await invoke(bot, "divide", a=10, b=0)  # ZeroDivisionError
        assert ctx.last_response == "Cannot divide!"
    finally:
        await bot.close()
```

### Hook Testing

```python
from easycord.hooks import HookRegistry

@pytest.mark.asyncio
async def test_before_command_hook():
    registry = HookRegistry()
    received = []
    
    registry.register("before_command", lambda ctx, name: received.append(name))
    await registry.fire("before_command", ctx=None, name="ping")
    
    assert received == ["ping"]
```

---

## Summary

1. **Middleware** controls who can run commands and logs/transforms them
2. **Error handlers** catch exceptions and respond appropriately
3. **Hooks** attach callbacks to command and plugin lifecycle events

Order matters: register middleware from outermost (error catching) to innermost (logging).

---

## Next Steps

- Need to store data? → [Storage & State](database-guide.md)
- Building complex features? → [Organizing Code](organizing-code.md)
- Testing commands? → [Testing Commands](testing.md)
