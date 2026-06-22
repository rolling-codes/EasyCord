# Middleware Patterns

Middleware intercepts every slash command before it reaches the handler. Each
layer receives the `Context` and a `proceed` coroutine; calling `proceed()` passes
control to the next layer (or, at the end of the chain, to the command itself).
Skipping `proceed()` short-circuits execution — the command never runs.

```python
bot.use(my_middleware())
```

---

## Built-in Middleware

All built-ins live in `easycord.middleware` and return a `MiddlewareFn`.

```python
from easycord.middleware import (
    admin_only,
    allowed_roles,
    boost_only,
    catch_errors,
    channel_only,
    dm_only,
    guild_only,
    has_permission,
    log_middleware,
    rate_limit,
)
```

### `guild_only()`

Blocks commands invoked in DMs. No arguments.

```python
bot.use(guild_only())
```

### `dm_only()`

Blocks commands invoked inside a guild — only DMs allowed. No arguments.

```python
bot.use(dm_only())
```

### `admin_only(message=None)`

Blocks unless the invoking member has the `administrator` permission. Passes
silently in DMs.

```python
bot.use(admin_only())
bot.use(admin_only(message="Admins only."))
```

### `allowed_roles(*role_ids, message=None)`

Blocks unless the invoking member holds at least one of the given role IDs.
Passes silently in DMs.

```python
bot.use(allowed_roles(STAFF_ROLE, MOD_ROLE))
bot.use(allowed_roles(VIP_ROLE, message="VIPs only."))
```

### `channel_only(*channel_ids, message=None)`

Blocks commands invoked outside the specified channel(s). Passes silently in DMs.

```python
bot.use(channel_only(COMMANDS_CHANNEL, BOT_CHANNEL))
```

### `has_permission(*permissions, message=None)`

Blocks unless the invoking member holds **all** of the named `discord.Permissions`
attributes. Passes silently in DMs.

```python
bot.use(has_permission("kick_members", "ban_members"))
```

### `rate_limit(limit=5, window=10.0)`

Per-user sliding-window rate limiter. Raises `ValueError` if `limit < 1` or
`window <= 0`.

```python
bot.use(rate_limit(limit=5, window=10.0))   # 5 commands per 10 s
```

### `boost_only(message=None)`

Blocks unless the invoking member is currently boosting the server. Passes
silently in DMs.

```python
bot.use(boost_only())
```

### `log_middleware(level=logging.INFO, fmt="/{command} invoked by {user} in {guild}")`

Logs every slash command invocation to the `easycord` logger. Always calls
`proceed()`.

```python
bot.use(log_middleware())
bot.use(log_middleware(level=logging.DEBUG, fmt="cmd={command} user={user}"))
```

### `catch_errors(message=None)`

Wraps the downstream chain in a broad `except`. Logs unhandled exceptions and
sends an ephemeral error reply to the user. Place this **first** so it catches
errors from all other middleware.

```python
bot.use(catch_errors())
bot.use(catch_errors(message="Something went wrong. Try again."))
```

---

## Writing Custom Middleware

`MiddlewareFn` is:

```python
Callable[[Context, Callable[[], Awaitable[None]]], Awaitable[None]]
```

The second argument is always a zero-arg coroutine. Await it to continue, skip
it to block.

### Function pattern

For stateless middleware, return the handler directly from a factory function:

```python
from easycord.middleware import MiddlewareFn
from easycord.context import Context
from typing import Callable, Awaitable

def require_prefix(prefix: str) -> MiddlewareFn:
    """Block commands unless the username starts with *prefix*."""

    async def handler(
        ctx: Context,
        proceed: Callable[[], Awaitable[None]],
    ) -> None:
        if not ctx.user.name.startswith(prefix):
            await ctx.respond(f"Only users whose name starts with '{prefix}' can use this.", ephemeral=True)
            return
        await proceed()

    return handler

bot.use(require_prefix("dev_"))
```

### Class pattern

For middleware that accumulates state between invocations, use a class with
`__call__`:

```python
import time
from collections import defaultdict
from easycord.middleware import MiddlewareFn
from easycord.context import Context
from typing import Callable, Awaitable

class AuditLog:
    """Record every command invocation with a running counter per user."""

    def __init__(self) -> None:
        self._counts: dict[int, int] = defaultdict(int)

    async def __call__(
        self,
        ctx: Context,
        proceed: Callable[[], Awaitable[None]],
    ) -> None:
        uid = ctx.user.id
        self._counts[uid] += 1
        print(f"[audit] user={uid} cmd={ctx.command_name} total={self._counts[uid]}")
        await proceed()

audit = AuditLog()
bot.use(audit)
```

The same `AuditLog` instance is retained for the lifetime of the bot, so
`_counts` persists across commands.

---

## Ordering

`bot.use()` appends middleware to a list. Execution order matches registration
order — the first middleware registered runs first (outermost wrap). The last
one registered is the final gate before the command handler.

```
registered:  [A, B, C]  →  A → B → C → handler → C → B → A
```

This means:
- Code **before** `await proceed()` in A runs before B and C.
- Code **after** `await proceed()` in A runs after B and C have finished.

### Common ordering mistakes

**Auth after logging** — if logging runs before auth, every blocked request
is still logged. That may be acceptable, but it can also fill logs with
noise from bad actors. Put logging after auth if you only want successful
invocations logged.

**`catch_errors` not first** — if an error middleware isn't the outermost
layer, exceptions thrown by earlier middleware escape uncaught.

**`rate_limit` after permission checks** — rate limit buckets fill even for
users who would be blocked anyway. Usually you want rate limiting to happen
after authentication, not before.

### Good vs. bad order — auth + logging + rate limit

```python
# BAD: rate limit counts blocked users; errors from rate_limit escape catch_errors
bot.use(log_middleware())
bot.use(rate_limit(limit=5, window=10.0))
bot.use(admin_only())
bot.use(catch_errors())

# GOOD: errors caught outermost; auth blocks early; rate limit only hits authed users;
#        logging records only commands that made it through auth
bot.use(catch_errors())
bot.use(guild_only())
bot.use(admin_only())
bot.use(rate_limit(limit=5, window=10.0))
bot.use(log_middleware())
```

---

## Practical Examples

### Rate Limiting Middleware

The built-in `rate_limit` covers most cases, but here is a full implementation
showing the pattern if you need per-command buckets or custom storage:

```python
import time
from collections import defaultdict
from easycord.middleware import MiddlewareFn
from easycord.context import Context
from typing import Callable, Awaitable

def per_user_rate_limit(limit: int, window: float) -> MiddlewareFn:
    """Allow at most *limit* commands per user within *window* seconds."""
    _history: dict[int, list[float]] = defaultdict(list)

    async def handler(
        ctx: Context,
        proceed: Callable[[], Awaitable[None]],
    ) -> None:
        uid = ctx.user.id
        now = time.monotonic()
        cutoff = now - window

        # Trim expired timestamps
        _history[uid] = [t for t in _history[uid] if t > cutoff]

        if len(_history[uid]) >= limit:
            wait = window - (now - _history[uid][0])
            await ctx.respond(
                f"You're rate limited. Try again in {wait:.1f}s.",
                ephemeral=True,
            )
            return

        _history[uid].append(now)
        await proceed()

    return handler

bot.use(per_user_rate_limit(limit=3, window=30.0))
```

### Permission Gate Middleware

```python
from easycord.middleware import MiddlewareFn
from easycord.context import Context
from typing import Callable, Awaitable

MODERATOR_ROLE_ID = 123456789

def mod_only() -> MiddlewareFn:
    """Require the moderator role or administrator permission."""

    async def handler(
        ctx: Context,
        proceed: Callable[[], Awaitable[None]],
    ) -> None:
        # DMs bypass guild checks
        if ctx.guild is None:
            await proceed()
            return

        member = ctx.guild.get_member(ctx.user.id)
        if member is None:
            await ctx.respond("Could not verify your permissions.", ephemeral=True)
            return

        is_admin = member.guild_permissions.administrator
        has_mod_role = any(r.id == MODERATOR_ROLE_ID for r in member.roles)

        if not (is_admin or has_mod_role):
            await ctx.respond("This command is for moderators only.", ephemeral=True)
            return

        await proceed()

    return handler

bot.use(guild_only())
bot.use(mod_only())
```

### Request Logging Middleware

```python
import logging
import time
from easycord.middleware import MiddlewareFn
from easycord.context import Context
from typing import Callable, Awaitable

logger = logging.getLogger("easycord")

def timed_log() -> MiddlewareFn:
    """Log each command with elapsed time."""

    async def handler(
        ctx: Context,
        proceed: Callable[[], Awaitable[None]],
    ) -> None:
        start = time.perf_counter()
        logger.info("%s: /%s", ctx.user, ctx.command_name)
        await proceed()
        elapsed = (time.perf_counter() - start) * 1000
        logger.info("/%s elapsed=%.1fms", ctx.command_name, elapsed)

    return handler

bot.use(timed_log())
```

---

## Testing Middleware

Use `unittest.mock.MagicMock` and `AsyncMock` to build a fake context — no
Discord connection required.

```python
from unittest.mock import AsyncMock, MagicMock
import pytest

def _ctx(*, guild=None, user_id: int = 1) -> MagicMock:
    ctx = MagicMock()
    ctx.guild = guild
    ctx.user = MagicMock()
    ctx.user.id = user_id
    ctx.respond = AsyncMock()
    ctx.t = lambda key, default="", **kw: default.format(**kw) if kw else default
    return ctx
```

### Assert that `proceed` was called

```python
@pytest.mark.asyncio
async def test_guild_only_allows_guild_context():
    from easycord.middleware import guild_only

    ctx = _ctx(guild=MagicMock())
    called = []

    async def proceed():
        called.append(True)

    await guild_only()(ctx, proceed)
    assert called  # proceed was reached
```

### Assert that `proceed` was NOT called

```python
@pytest.mark.asyncio
async def test_guild_only_blocks_dm():
    from easycord.middleware import guild_only

    ctx = _ctx(guild=None)
    called = []

    async def proceed():
        called.append(True)

    await guild_only()(ctx, proceed)
    assert not called
    ctx.respond.assert_called_once()
```

### Assert that middleware modified behavior

```python
@pytest.mark.asyncio
async def test_rate_limit_blocks_on_third_call():
    from easycord.middleware import rate_limit

    ctx = _ctx(user_id=42)
    called = []
    mw = rate_limit(limit=2, window=60.0)

    async def proceed():
        called.append(True)

    await mw(ctx, proceed)
    await mw(ctx, proceed)
    await mw(ctx, proceed)  # should be blocked

    assert len(called) == 2
    ctx.respond.assert_called_once()
```

### Testing a full chain with `build_chain`

```python
@pytest.mark.asyncio
async def test_chain_order():
    from easycord.middleware import build_chain

    ctx = _ctx()
    order = []

    async def mw_a(ctx, proceed):
        order.append("a_before")
        await proceed()
        order.append("a_after")

    async def mw_b(ctx, proceed):
        order.append("b_before")
        await proceed()
        order.append("b_after")

    async def invoke():
        order.append("invoke")

    chain = build_chain(ctx, invoke, [mw_a, mw_b])
    await chain()

    assert order == ["a_before", "b_before", "invoke", "b_after", "a_after"]
```
