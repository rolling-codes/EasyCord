# Error Handling

This guide covers the full command error pipeline — how exceptions propagate, where to intercept them, and how to test that your handlers fire correctly.

## The Error Waterfall

When a slash command raises an exception, EasyCord walks this chain and stops at the first registered handler:

```
1. Per-command @command_error handler   (registered on the plugin, keyed to command name)
2. Plugin on_error() hook               (override on your Plugin subclass)
3. Global @bot.on_error handler         (registered on the bot instance)
4. Framework fallback                   (re-raises in command callbacks; logs via logger.exception in tasks/components)
```

The check is exclusive — the first match wins and the rest are skipped. If none are registered, the exception is either re-raised (for slash commands) or logged as `"Unhandled exception in framework interaction or task"` (for background tasks, components, and modals).

The same waterfall applies to **components** (`@component`), **modals** (`@modal`), and **background tasks** (`@task`). For tasks, `ctx` is `None` when passed to `on_error` — your handler must account for that if it uses `ctx`.

---

## Per-Command Error Handler

Use `@command_error` when one command has known failure modes that need specific messaging.

```python
from easycord import Plugin, slash, command_error

class MathPlugin(Plugin):

    @slash(description="Divide two numbers")
    async def divide(self, ctx, a: int, b: int):
        await ctx.respond(str(a // b))

    @command_error("divide")
    async def divide_error(self, ctx, exc: Exception):
        if isinstance(exc, ZeroDivisionError):
            await ctx.respond("Cannot divide by zero.", ephemeral=True)
        else:
            await ctx.respond("Math failed. Try again.", ephemeral=True)
```

`exc` is whatever exception the command raised — `Exception` is the base type. `ctx` is the same `Context` passed to the command; you can call `ctx.respond()`, `ctx.t()`, etc.

The handler is registered by name — `"divide"` must match the command name (the `name=` argument to `@slash`, or the function name if omitted).

---

## Plugin-Scoped Error Handler

Override `on_error(self, ctx, exc)` on your `Plugin` subclass to handle errors from any command in that plugin with shared formatting logic.

```python
import logging
from easycord import Plugin, slash
from easycord.validators import ValidationError

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
        elif isinstance(exc, Exception):
            logger.exception("ShopPlugin error", exc_info=exc)
            await ctx.respond(
                "Something went wrong on our end. Please try again.",
                ephemeral=True,
            )
```

Use plugin-scoped handling when multiple commands share the same error format — centralizes the logic instead of repeating it with `@command_error` on every command.

`on_error` only fires if the plugin overrides the base `Plugin.on_error`. EasyCord detects this by identity-comparing the method to `Plugin.on_error` at runtime — defining the method at all is sufficient.

---

## Global Bot Error Handler

Register a fallback for any exception that reaches the bot level — commands without a per-command or plugin handler, and errors from commands not attached to a plugin.

```python
import logging
from easycord import Bot

logger = logging.getLogger(__name__)

bot = Bot(token="...", auto_sync=False)

@bot.on_error
async def handle_error(ctx, exc: Exception) -> None:
    logger.exception("Unhandled command error", exc_info=exc)
    if ctx is not None:
        await ctx.respond(
            "An unexpected error occurred. The team has been notified.",
            ephemeral=True,
        )
```

Only one global handler can be registered. A second call to `bot.on_error` overwrites the first.

`ctx` can be `None` here — task-originated errors reach this handler with no interaction context.

---

## Common Exceptions

| Exception | When it happens | Recommended response |
|-----------|-----------------|----------------------|
| `discord.NotFound` | Interaction token expired (>15 min); channel/message deleted mid-command | Log and skip — the user is gone or the resource is gone; responding will 404 |
| `discord.Forbidden` | Bot lacks permission (send messages, manage roles, etc.) | Respond ephemerally that the bot is missing a required permission |
| `discord.HTTPException` | Generic Discord API failure (rate limit, server error) | Respond with a retry prompt; log the status code for triage |
| `easycord.ValidationError` | A validator (`Range`, `Regex`, `ChoiceSet`, etc.) rejected user input | Call `exc.user_message(ctx)` for the localized message, respond ephemerally |
| `RuntimeError` (from `ctx.is_admin`) | Called `ctx.is_admin()` as a method instead of a property | Fix the call site — do not catch this at runtime |
| `IndexError` (from orchestrator) | All AI providers exhausted (`FallbackStrategy`) | Respond that the AI service is temporarily unavailable |

`ValidationError` is a subclass of `ValueError`. Its `.user_message(ctx)` method returns the localized string via `ctx.t()` if a key is set, or falls back to the raw message.

---

## Best Practices

- **Always respond to the user** — even on unexpected exceptions. Discord interactions expire; if you don't respond, the user sees a generic "interaction failed" from Discord with no context. Use `ephemeral=True` for error responses.
- **Don't leak internal state** — stack traces, SQL queries, and file paths should never appear in user-facing messages. Log the details, show a generic message.
- **Log with `exc_info=True` for unexpected errors** — `logger.exception("msg", exc_info=exc)` captures the full traceback. For known user errors (like `ValidationError`), logging at DEBUG or skipping is fine.
- **Distinguish user errors from system errors** — `ValidationError` is a user mistake; respond directly with the validation message. `discord.HTTPException` or an unhandled `RuntimeError` is a system failure; log it and send a generic retry message.
- **Handle `ctx is None` in `on_error` and global handlers** — background tasks call these handlers with `ctx=None`. Guard before calling any `ctx.*` method.
- **Don't swallow exceptions silently** — if your handler can't form a response, re-raise or log. Silent swallowing makes failures invisible.
- **Use `ErrorEmbed` for consistent error styling** — `from easycord.embed_cards import ErrorEmbed` gives you a pre-styled embed card for failure responses.

---

## Testing Error Handlers

Use `easycord.testing.invoke` to trigger a command and verify the handler fires.

```python
import pytest
from easycord import Bot, Plugin, slash, command_error
from easycord.testing import invoke

@pytest.mark.asyncio
async def test_divide_error_handler():
    events = []

    class MathPlugin(Plugin):
        @slash(description="Divide")
        async def divide(self, ctx, a: int, b: int):
            await ctx.respond(str(a // b))

        @command_error("divide")
        async def divide_error(self, ctx, exc):
            events.append(type(exc).__name__)
            await ctx.respond("Math error.", ephemeral=True)

    bot = Bot(auto_sync=False, db_backend="memory")
    try:
        bot.add_plugin(MathPlugin())
        ctx = await invoke(bot, "divide", a=10, b=0)

        assert ctx.last_response == "Math error."
        assert events == ["ZeroDivisionError"]
    finally:
        await bot.close()
```

To test `on_error` priority over a global handler:

```python
@pytest.mark.asyncio
async def test_plugin_on_error_wins_over_global():
    events = []

    class BrokenPlugin(Plugin):
        @slash(description="Broken")
        async def broken(self, ctx):
            raise RuntimeError("boom")

        async def on_error(self, ctx, exc):
            events.append("plugin")
            await ctx.respond("plugin caught it", ephemeral=True)

    bot = Bot(auto_sync=False, db_backend="memory")

    @bot.on_error
    async def global_handler(ctx, exc):
        events.append("global")

    try:
        bot.add_plugin(BrokenPlugin())
        ctx = await invoke(bot, "broken")

        assert events == ["plugin"]   # global never fires
        assert ctx.last_response == "plugin caught it"
    finally:
        await bot.close()
```

For component and modal errors, trigger the interaction directly via `FakeInteraction`:

```python
from easycord.testing import FakeInteraction

interaction = FakeInteraction(client=bot, custom_id="my_button")
await bot._handle_component(interaction)
```
