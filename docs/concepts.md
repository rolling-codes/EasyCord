# Concepts

## Slash commands

### What you write

In EasyCord you write handlers shaped like:

```python
@bot.slash(description="Say hello")
async def hello(ctx, name: str, loud: bool = False):
    await ctx.respond(f"Hello {name}!")
```

Your function’s type annotations are used by `discord.py` to infer option types.

### What EasyCord registers

Internally, EasyCord must register an `app_commands.Command` callback that receives a `discord.Interaction`. To keep your code ergonomic, EasyCord wraps your handler and:

- builds a `Context(interaction)`
- runs middleware
- calls your handler with `ctx` and the parsed options

### Signature rewriting (important)

`discord.py` discovers options by inspecting the registered callback signature. EasyCord rewrites the signature of the internal callback so the first parameter is `interaction: discord.Interaction` (instead of `ctx`).

EasyCord also strips a leading `ctx`/`context` parameter from the user handler when building the callback, and for plugin methods it also accounts for bound-method `self`.

Practical guidance:

- **Standalone slash handler**: write `async def cmd(ctx, ...)`
- **Plugin slash handler**: write `async def cmd(self, ctx, ...)`

## Events

`Bot.on("message")` registers a handler for that event name (without the `on_` prefix).

Key behavior:

- Multiple handlers per event are supported.
- EasyCord overrides `discord.Client.dispatch` and schedules handlers via `asyncio.create_task(...)`.

Implication:

- Event handlers run asynchronously; if a handler raises, it won’t crash the main dispatch loop, but you should still handle errors/logging appropriately.

## Middleware

Middleware wraps **every slash command invocation** (not events).

Middleware shape:

```python
async def middleware(ctx, next):
    # before
    await next()
    # after
```

Ordering:

- Middleware runs in **registration order** (`bot.use(...)` order).
- The final “handler” is the actual slash command function.

Short-circuiting:

- If middleware does not call `await next()`, the command will not run.
- This is how `guild_only()` and rate limiting work.

## Plugins

Plugins are instances of `Plugin` subclasses.

In a plugin you decorate methods with:

- `@easycord.decorators.slash(...)` (imported as `from easycord import slash`)
- `@easycord.decorators.on(event)`

Then you register the plugin:

```python
bot.add_plugin(MyPlugin())
```

### Plugin lifecycle

- `add_plugin()`:
  - sets `plugin._bot = bot`
  - scans methods and registers slash commands + event handlers
  - if the bot is already ready, schedules `plugin.on_load()` as a task
- `setup_hook()`:
  - syncs commands (if enabled)
  - calls `on_load()` for any plugins loaded before `run()`
- `remove_plugin()` (async):
  - removes the plugin’s slash commands from the command tree (best-effort)
  - deregisters the plugin’s event handlers
  - awaits `plugin.on_unload()`

### `Plugin.bot` safety

`Plugin.bot` raises a `RuntimeError` if accessed before the plugin is loaded into a bot.

