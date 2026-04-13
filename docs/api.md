# API reference

This reference is derived from the actual EasyCord source in this codebase.

## `easycord.Bot`

### Constructor

`Bot(*, intents: discord.Intents | None = None, auto_sync: bool = True, **kwargs)`

- **intents**: passed to `discord.Client`. Defaults to `discord.Intents.default()`.
- **auto_sync**: if true, `setup_hook()` runs `await tree.sync()`.
- **kwargs**: forwarded to `discord.Client`.

### Slash commands

`Bot.slash(name: str | None = None, *, description: str = "No description provided.", guild_id: int | None = None, permissions: list[str] | None = None, cooldown: float | None = None, autocomplete: dict[str, Callable] | None = None) -> Callable`

Decorator that registers a top-level slash command.

- **name**: defaults to the function name.
- **description**: shown in Discord UI.
- **guild_id**: `None` registers globally; `int` registers to one guild (instant).
- **permissions**: list of `discord.Permissions` attribute names required (e.g. `["kick_members"]`). Responds ephemerally and skips the command if any are missing.
- **cooldown**: per-user cooldown in seconds. Blocks ephemerally until the window expires.
- **autocomplete**: dict mapping parameter names to async callbacks. Each callback receives the current typed string and returns a `list[str]` of suggestions.
- **choices**: dict mapping parameter names to a fixed list of values. Discord renders these as a locked dropdown — no free-text entry. Values may be strings or numbers.

```python
@bot.slash(description="Kick a member", permissions=["kick_members"])
async def kick(ctx, member: discord.Member):
    await member.kick()
    await ctx.respond(f"Kicked {member.display_name}.")

@bot.slash(description="Roll dice", cooldown=5)
async def roll(ctx):
    import random
    await ctx.respond(str(random.randint(1, 6)))

FRUITS = ["apple", "banana", "cherry", "date"]

async def fruit_ac(current: str) -> list[str]:
    return [f for f in FRUITS if current.lower() in f]

@bot.slash(description="Pick a fruit", autocomplete={"fruit": fruit_ac})
async def pick(ctx, fruit: str):
    await ctx.respond(f"You picked {fruit}!")
```

### Presence

`await Bot.set_status(status: str = "online", *, activity: str | None = None, activity_type: str = "playing") -> None`

Set the bot's presence status and optional activity text.

- **status**: `"online"`, `"idle"`, `"dnd"`, or `"invisible"`.
- **activity**: display text shown alongside the status indicator. `None` clears it.
- **activity_type**: `"playing"`, `"watching"`, or `"listening"`.

```python
await bot.set_status("idle", activity="Taking a break", activity_type="watching")
```

### Events

`Bot.on(event: str) -> Callable`

Decorator that registers an event listener for `event` (without the `on_` prefix).

Example:

```python
@bot.on("message")
async def on_message(message): ...
```

### Middleware

`Bot.use(middleware: MiddlewareFn) -> MiddlewareFn`

Registers a middleware function. Middleware runs for slash commands only.

Middleware signature:

`async def middleware(ctx: Context, next: Callable[[], Awaitable[None]]) -> None`

### Plugins

`Bot.add_plugin(plugin: Plugin) -> None`

Loads a plugin instance:

- assigns the bot reference (`plugin._bot`)
- registers all plugin slash commands and event handlers
- calls `on_load()`:
  - in `setup_hook()` for plugins loaded before `run()`
  - or scheduled immediately if the bot is already ready

`await Bot.remove_plugin(plugin: Plugin) -> None`

Unloads a plugin instance:

- removes the plugin's registered slash commands from the command tree (best-effort)
- deregisters the plugin's event handlers
- awaits `plugin.on_unload()`

Raises:

- `ValueError` if the plugin is not loaded.

### Lifecycle hooks

Bot overrides:

- `setup_hook()`:
  - syncs commands (if enabled)
  - awaits `on_load()` for all loaded plugins
- `dispatch(event, *args, **kwargs)`:
  - calls `discord.Client.dispatch`
  - schedules all EasyCord event handlers for `event`
- `on_ready()`:
  - logs ready information

### Context menus

`Bot.user_command(name: str | None = None, *, guild_id: int | None = None) -> Callable`

Decorator that registers a right-click **User** context menu command. The handler receives `(ctx, member)` where `member` is `discord.Member | discord.User` depending on where the right-click occurred.

`Bot.message_command(name: str | None = None, *, guild_id: int | None = None) -> Callable`

Decorator that registers a right-click **Message** context menu command. The handler receives `(ctx, message)` where `message` is a `discord.Message`.

Both decorators run the full middleware stack, support `guild_id` for guild-scoped registration, and default `name` to the function name.

```python
@bot.user_command(name="User Info")
async def user_info(ctx, member):
    await ctx.respond(f"{member.display_name} — ID {member.id}", ephemeral=True)

@bot.message_command(name="Quote")
async def quote(ctx, message):
    await ctx.respond(f"> {message.content[:100]}")
```

### User & member lookup

`await Bot.fetch_member(guild_id: int, user_id: int) -> discord.Member`

Fetch a guild member by guild and user ID. Tries the cache first; falls back to the API. Raises `discord.NotFound` if the user is not in the guild.

`await bot.fetch_user(user_id)` is available directly from the inherited `discord.Client` API.

```python
user = await bot.fetch_user(123456789)   # inherited from discord.Client
await ctx.unban(user, reason="Appeal accepted")

member = await bot.fetch_member(ctx.guild.id, stored_id)
await ctx.kick(member)
```

### Convenience

`Bot.run(token: str, **kwargs) -> None`

Configures basic logging and calls `discord.Client.run(...)`.

## `easycord.Context`

### Constructor

`Context(interaction: discord.Interaction)`

### Core attributes

- `ctx.interaction`: the underlying `discord.Interaction`
- `ctx.user`: `discord.User | discord.Member`
- `ctx.guild`: `discord.Guild | None`
- `ctx.channel`: channel from the interaction
- `ctx.command_name`: slash command name or `None`
- `ctx.data`: raw `interaction.data`

### Responding

`await ctx.respond(content: str | None = None, *, ephemeral: bool = False, embed: discord.Embed | None = None, **kwargs) -> None`

Behavior:

- first response uses `interaction.response.send_message(...)`
- subsequent responses use `interaction.followup.send(...)`

`await ctx.defer(*, ephemeral: bool = False) -> None`

Defers the response and marks the context as responded.

`await ctx.send_embed(title: str, description: str | None = None, *, fields: list[tuple] | None = None, footer: str | None = None, color: discord.Color = discord.Color.blue(), ephemeral: bool = False, **kwargs) -> None`

Builds a `discord.Embed` and sends it via `respond()`.

- **fields**: list of `(name, value)` or `(name, value, inline)` tuples. `inline` defaults to `True`.
- **footer**: optional footer text.

```python
await ctx.send_embed(
    "Server Stats",
    fields=[("Members", "150"), ("Online", "42")],
    footer="Updated just now",
    color=discord.Color.green(),
)
```

`await ctx.send_file(path: str, *, filename: str | None = None, content: str | None = None, ephemeral: bool = False) -> None`

Send a file attachment as the command response.

### Interactive UI

`await ctx.ask_form(title: str, **fields) -> dict[str, str] | None`

Show a modal with text inputs. Returns submitted values or `None` on timeout/dismiss.

`await ctx.confirm(prompt: str, *, timeout: float = 30, yes_label: str = "Yes", no_label: str = "Cancel", ephemeral: bool = False) -> bool | None`

Show Yes/No buttons. Returns `True`, `False`, or `None` on timeout.

`await ctx.choose(prompt: str, options: list[str | dict], *, timeout: float = 60, placeholder: str = "Select an option", ephemeral: bool = False) -> str | None`

Show a select-menu. Options may be strings or `{"label", "value", "description"}` dicts. Returns the chosen value or `None` on timeout.

```python
color = await ctx.choose("Pick a color", ["Red", "Green", "Blue"])
```

`await ctx.paginate(pages: list[str | discord.Embed], *, timeout: float = 120, ephemeral: bool = False) -> None`

Show a multi-page message with Prev/Next buttons.

### Moderation

`await ctx.kick(member: discord.Member, *, reason: str | None = None) -> None`

`await ctx.ban(member: discord.Member, *, reason: str | None = None, delete_message_days: int = 0) -> None`

`await ctx.timeout(member: discord.Member, duration: float, *, reason: str | None = None) -> None`

Temporarily mute a member. `duration` is in seconds.

`await ctx.unban(user: discord.User, *, reason: str | None = None) -> None`

Unban a user. Requires a guild context.

### Member management

`await ctx.set_nickname(member: discord.Member, nickname: str | None, *, reason: str | None = None) -> None`

Set or clear a member's server nickname. Pass `None` to reset to their account username.

`await ctx.move_member(member: discord.Member, channel_id: int | None, *, reason: str | None = None) -> None`

Move a member to a voice channel by ID. Pass `None` to disconnect them entirely.

### Role management

`await ctx.add_role(member: discord.Member, role_id: int, *, reason: str | None = None) -> None`

`await ctx.remove_role(member: discord.Member, role_id: int, *, reason: str | None = None) -> None`

`await ctx.create_role(name: str, *, color: discord.Color = discord.Color.default(), hoist: bool = False, mentionable: bool = False, reason: str | None = None) -> discord.Role`

Create a new role and return it. `hoist=True` makes members with this role appear separately in the member list.

`await ctx.delete_role(role_id: int, *, reason: str | None = None) -> None`

Delete a role by ID.

### Message management

`await ctx.purge(limit: int = 10) -> int`

Bulk-delete recent messages in the current channel. Returns count deleted. Requires a `TextChannel`.

`await ctx.fetch_messages(limit: int = 10) -> list[discord.Message]`

Return the N most recent messages in the current channel.

`await ctx.delete_message(message: discord.Message, *, delay: float | None = None) -> None`

Delete a specific message. Pass `delay` (seconds) to schedule a delayed deletion.

### Reactions

`await ctx.react(message: discord.Message, emoji: str) -> None`

Add a reaction to a message.

`await ctx.unreact(message: discord.Message, emoji: str) -> None`

Remove the bot's own reaction from a message.

`await ctx.clear_reactions(message: discord.Message) -> None`

Remove all reactions from a message. Requires `manage_messages`.

### Channel management

`await ctx.slowmode(seconds: int, *, reason: str | None = None) -> None`

Set the slowmode delay on the current text channel. `0` disables it; maximum is `21600` (6 hours).

`await ctx.lock_channel(*, reason: str | None = None) -> None`

Prevent `@everyone` from sending messages by setting `send_messages = False` on the default role overwrite. Preserves all other existing permission overwrites.

`await ctx.unlock_channel(*, reason: str | None = None) -> None`

Restore `@everyone`'s ability to send messages (`send_messages = True`).

### Threads

`await ctx.create_thread(name: str, *, auto_archive_minutes: int = 1440, reason: str | None = None) -> discord.Thread`

Create a public thread in the current channel. `auto_archive_minutes` must be `60`, `1440`, `4320`, or `10080`.

```python
thread = await ctx.create_thread(f"Support: {topic}")
await ctx.respond(f"Thread created: {thread.mention}", ephemeral=True)
```

## Decorators for plugins (`easycord.decorators`)

### `slash(...)`

`slash(name: str | None = None, *, description: str = "No description provided.", guild_id: int | None = None, permissions: list[str] | None = None, cooldown: float | None = None, autocomplete: dict[str, Callable] | None = None, choices: dict[str, list] | None = None) -> Callable`

Marks a plugin method as a slash command. All `@bot.slash` parameters are supported.

```python
from easycord import Plugin, slash

class MyPlugin(Plugin):
    @slash(description="Hello")
    async def hello(self, ctx, name: str): ...
```

### `on(event)`

`on(event: str) -> Callable`

Marks a plugin method as an event handler.

## `easycord.Plugin`

Base class for plugins.

- `plugin.bot -> Bot`: back-reference (only valid after `add_plugin()`)
- `async plugin.on_load()`: optional async setup hook
- `async plugin.on_unload()`: optional async teardown hook

## Built-in middleware factories (`easycord.middleware`)

All return a `MiddlewareFn`.

### `log_middleware(level=logging.INFO, fmt="/{command} invoked by {user} in {guild}")`

Logs every slash command invocation using `logging.getLogger("easycord")`.

Format placeholders:

- `{command}`: `ctx.command_name`
- `{user}`: `ctx.user`
- `{guild}`: `ctx.guild` or `"DM"`

### `guild_only()`

Blocks commands invoked in DMs and responds ephemerally with an error message.

### `rate_limit(limit=5, window=10.0)`

Simple per-user sliding-window rate limiter using timestamps from `time.monotonic()`.

When limited, responds ephemerally with a "try again in Xs" message.

### `catch_errors(message="Something went wrong. Please try again.")`

Catches exceptions thrown by later middleware/handlers, logs them, and attempts to send an ephemeral error response.
