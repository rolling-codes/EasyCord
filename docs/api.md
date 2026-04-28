# API reference

## Start here

If you are learning the framework for the first time, these are the main building blocks:

| Goal | Use |
| --- | --- |
| Make a command | `@bot.slash(...)` |
| Load multiple plugins | `bot.add_plugins(...)` |
| Load multiple groups | `bot.add_groups(...)` |
| Group related commands | subclass `SlashGroup` |
| Add buttons or select menus | `@bot.component(...)` |
| Add context menus | `@bot.user_command(...)` / `@bot.message_command(...)` |
| Build a bot in steps | `Composer()` |
| Save guild settings | `ServerConfigStore` |
| Load bundled plugins | `bot.load_builtin_plugins()` |
| Store guild data | `bot.db` |
| Query an AI provider | `await ctx.ai(...)` |

```python
from easycord import Bot
from easycord.plugins import WelcomePlugin, LevelsPlugin

bot = Bot()
bot.add_plugins(WelcomePlugin(), LevelsPlugin())
```

That one pattern covers most starter bots: create the bot, load the plugins you
need, then register a few slash commands on top.

## `easycord.Bot`

`Bot(*, intents=None, auto_sync=True, load_builtin_plugins=False, database=None, db_backend=None, db_path=None, db_auto_sync_guilds=None, ai_provider=None, **kwargs)`

`bot.db` is auto-configured if you do not pass a database object. The default
backend is SQLite and the default path is `.easycord/library.db`. You can
override that behavior with environment variables:

| Env var | Meaning |
| --- | --- |
| `EASYCORD_DB_BACKEND` | `sqlite` or `memory` |
| `EASYCORD_DB_PATH` | SQLite file path |
| `EASYCORD_DB_AUTO_SYNC_GUILDS` | `1`/`0` toggle for auto-creating guild rows |

`Bot.load_builtin_plugins()` loads the bundled first-party plugin pack:
`WelcomePlugin`, `TagsPlugin`, `PollsPlugin`, and `LevelsPlugin`.

Other bundled plugins are available but not auto-loaded:
`AIPlugin` (multi-provider AI assistant), `OpenClaudePlugin` (Anthropic Claude shortcut),
`OpenAIProvider`, `GeminiProvider`, `OllamaProvider`.

### Slash commands

`Bot.slash(name=None, *, description, guild_id=None, guild_only=False, ephemeral=False, permissions=None, cooldown=None, autocomplete=None, choices=None)`

| Parameter | Type | Description |
| --- | --- | --- |
| `name` | `str \| None` | Command name; defaults to function name |
| `description` | `str` | Shown in Discord UI |
| `guild_id` | `int \| None` | Register to one guild (instant); `None` = global (up to 1 h) |
| `guild_only` | `bool` | Reject DM invocations ephemerally; replaces `if not ctx.guild` guard |
| `ephemeral` | `bool` | Force all responses from this command to be ephemeral |
| `permissions` | `list[str]` | `discord.Permissions` attribute names required (e.g. `["kick_members"]`) |
| `cooldown` | `float` | Per-user cooldown in seconds |
| `autocomplete` | `dict[str, async (str) -> list[str]]` | Live suggestions per parameter |
| `choices` | `dict[str, list]` | Fixed dropdown values per parameter |
| `aliases` | `list[str] \| None` | Extra command names that trigger the same handler |

### Context menus

`Bot.user_command(name=None, *, guild_id=None)` — right-click User menu; handler receives `(ctx, member)`

`Bot.message_command(name=None, *, guild_id=None)` — right-click Message menu; handler receives `(ctx, message)`

### Events / Middleware / Plugins

`Bot.on(event)` — decorator; event name without `on_` prefix; multiple handlers per event supported

`Bot.use(middleware)` — register middleware (decorator or direct call); runs for slash commands only

`@Bot.on_error` / `Bot.on_error(func)` — register a global error handler `async def handler(ctx, error)` called when any slash command raises an unhandled exception; overwrites any previously registered handler

`Bot.add_plugin(plugin)` — load one plugin; raises `TypeError` / `ValueError` on bad input or duplicate

`Bot.add_plugins(*plugins)` — load several plugins in one call

`Bot.add_group(group)` — load one SlashGroup namespace; raises `TypeError` / `ValueError` on bad input or duplicate

`Bot.add_groups(*groups)` — load several SlashGroup namespaces in one call

`Bot.load_builtin_plugins()` — load the bundled plugin pack once; safe to call before startup

`await Bot.remove_plugin(plugin)` — unload plugin; removes commands, deregisters handlers, calls `on_unload()`

`await Bot.reload_plugin(name: str)` — reload a plugin in-place by class name; calls `on_unload()` then `on_load()` on the same instance; constructor arguments and in-memory state preserved; raises `ValueError` if no loaded plugin has that class name

### Database

`bot.db` — framework-owned database service with guild-row sync and JSON values

`await bot.db.ensure_guild(guild_id)` — create a row for a guild if missing

`await bot.db.get(guild_id, key, default=None)` — read a guild-scoped value

`await bot.db.set(guild_id, key, value)` — store a guild-scoped value

`await bot.db.delete(guild_id, key)` — delete a guild-scoped value

`await bot.db.list_guilds()` — return all known guild records

### Guild / Channel / Webhook / Emoji

`await Bot.fetch_guild(guild_id)` → `discord.Guild` — cache-first; raises `discord.NotFound`

`await Bot.fetch_channel(channel_id)` → channel — cache-first; raises `discord.NotFound` / `discord.Forbidden`

`await Bot.leave_guild(guild_id)` — leave a guild; raises `RuntimeError` if not a member

`await Bot.create_channel(guild_id, name, *, channel_type="text", category_id=None, topic=None, reason=None)` → channel — `channel_type`: `"text" | "voice" | "category" | "stage" | "forum"`

`await Bot.delete_channel(channel_id, *, reason=None)`

`await Bot.send_webhook(channel_id, content=None, *, username=None, avatar_url=None, embed=None, **kwargs)` — one-shot webhook send; creates and caches a webhook on first use per channel

`await Bot.create_emoji(guild_id, name, image_path, *, reason=None)` → `discord.Emoji`

`await Bot.delete_emoji(guild_id, emoji_id, *, reason=None)`

`await Bot.fetch_guild_emojis(guild_id)` → `list[discord.Emoji]`

### Component routing

`@Bot.component` / `@Bot.component("custom_id")` — register a persistent button/select-menu handler; custom ID defaults to function name

`@Bot.component("prefix_")` — prefix match: `"prefix_suffix"` invokes handler with `(ctx, "suffix")`

Middleware runs on component interactions exactly as it does for slash commands.

### Lookup / Presence / Run

`await Bot.fetch_member(guild_id, user_id)` — cache-first guild member fetch; raises `discord.NotFound`

`await Bot.fetch_user(user_id)` — inherited from `discord.Client`; cache-first

`await Bot.set_status(status="online", *, activity=None, activity_type="playing")` — status: `"online" | "idle" | "dnd" | "invisible"`; activity_type: `"playing" | "watching" | "listening" | "streaming"`

`Bot.run(token, **kwargs)` — configures logging, starts the bot

---

## `easycord.Context`

### Properties

| Property | Type | Description |
| --- | --- | --- |
| `ctx.interaction` | `discord.Interaction` | Underlying interaction |
| `ctx.user` | `User \| Member` | Invoking user |
| `ctx.member` | `Member \| None` | Invoking user as `Member` (has `.roles`, `.nick`, `.guild_permissions`); `None` in DMs |
| `ctx.guild` | `Guild \| None` | Server or `None` in DMs |
| `ctx.guild_id` | `int \| None` | `ctx.guild.id` safe shortcut; `None` in DMs |
| `ctx.channel` | `Messageable \| None` | Channel |
| `ctx.command_name` | `str \| None` | Slash command name |
| `ctx.voice_channel` | `VoiceChannel \| StageChannel \| None` | Invoker's current voice channel |
| `ctx.is_admin` | `bool` | `True` if invoker has administrator permission; `False` in DMs |
| `ctx.data` | `dict \| None` | Raw interaction data |
| `ctx.bot_permissions` | `discord.Permissions` | Bot's own permissions in the current channel; raises `RuntimeError` in DMs |

### Responding

`await ctx.respond(content=None, *, ephemeral=False, embed=None, **kwargs)` — first call: `send_message`; subsequent: `followup.send`

`await ctx.defer(*, ephemeral=False)` — acknowledge without visible reply; use before slow operations

`await ctx.ai(prompt, *, provider=None, model=None)` — query the configured AI provider and return response text. Configure `Bot(ai_provider=provider)` for a shared provider, or pass `provider=...` for a one-off request. `model=...` temporarily overrides providers that expose `_model`.

`await ctx.send_embed(title, description=None, *, fields=None, footer=None, thumbnail=None, image=None, author=None, timestamp=None, color=blue, ephemeral=False)` — fields: `[(name, value)]` or `[(name, value, inline)]`; `thumbnail`/`image`: URL strings; `author`: name string or `{"name", "icon_url", "url"}` dict; `timestamp=True` uses current UTC time

`await ctx.send_file(path, *, filename=None, content=None, ephemeral=False)`

`await ctx.edit_response(content=None, *, embed=None, **kwargs)` — edit the original response in-place

`await ctx.dm(content=None, *, embed=None, **kwargs)` — DM the invoking user; raises `RuntimeError` if DMs disabled

`await ctx.send_to(channel_id, content=None, **kwargs)` — send to any channel by ID

### Interactive UI

`await ctx.ask_form(title, **fields)` → `dict[str, str] | None` — modal with text inputs

`await ctx.confirm(prompt, *, timeout=30, yes_label="Yes", no_label="Cancel", ephemeral=False)` → `bool | None`

`await ctx.choose(prompt, options, *, timeout=60, placeholder="Select an option", ephemeral=False)` → `str | None` — options: strings or `{"label", "value", "description"}` dicts

`await ctx.paginate(pages, *, timeout=120, ephemeral=False)` — Prev/Next multi-page embed/text

`await ctx.prompt(label, *, placeholder=None, max_length=None, timeout=660)` → `str | None` — single-field modal shortcut; returns submitted text or `None` on timeout/dismiss

### Moderation

`await ctx.kick(member, *, reason=None)`

`await ctx.ban(member, *, reason=None, delete_message_days=0)`

`await ctx.timeout(member, duration, *, reason=None)` — duration in seconds

`await ctx.unban(user, *, reason=None)`

### Member / Role management

`await ctx.set_nickname(member, nickname, *, reason=None)` — `None` resets to account username

`await ctx.move_member(member, channel_id, *, reason=None)` — `None` disconnects

`await ctx.add_role(member, role_id, *, reason=None)`

`await ctx.remove_role(member, role_id, *, reason=None)`

---

## Builders (`easycord.builders`)

Fluent wrappers that produce discord.py UI objects. Import from `easycord` directly:

```python
from easycord import EmbedBuilder, ButtonRowBuilder, SelectMenuBuilder, ModalBuilder
```

### `EmbedBuilder`

| Method | Description |
|---|---|
| `.title(text)` | Set the embed title (required) |
| `.description(text)` | Set the description |
| `.field(name, value, inline=True)` | Add a field (repeatable) |
| `.footer(text)` | Set the footer |
| `.color(color)` | Set the embed colour (default `discord.Color.blue()`) |
| `.build()` | Return the `discord.Embed` |

Raises `ValueError` if `.title()` was not called before `.build()`.

### `EmbedCard`

Wrap an existing embed and optionally attach buttons/select menus:

```python
from easycord import EmbedCard

card = (
    EmbedCard.from_embed(embed)
    .button("Approve", custom_id="approve", style="success")
    .button("Reject", custom_id="reject", style="danger")
)

await ctx.respond(**card.to_kwargs())
```

Common helpers:

| Method | Description |
|---|---|
| `.button(label, custom_id=None, style="primary", url=None)` | Add a button |
| `.link(label, url)` | Add a link button |
| `.select(custom_id, *, placeholder=None, options=(), min_values=1, max_values=1)` | Add a select menu |
| `.to_kwargs()` | Return kwargs for `ctx.respond` or `channel.send` |
| `.respond(ctx, *, content=None, ephemeral=False, **kwargs)` | Send the card directly |

Theme presets:

- `InfoEmbed`
- `SuccessEmbed`
- `WarningEmbed`
- `ErrorEmbed`

### `ButtonRowBuilder`

| Method | Description |
|---|---|
| `.button(label, custom_id=None, style="primary", url=None)` | Add a button (repeatable) |
| `.build()` | Return a `discord.ui.View` |

Valid `style` values: `"primary"`, `"secondary"`, `"success"`, `"danger"`, `"link"`.
For link buttons use `style="link"` and `url="https://..."` instead of `custom_id`.
Non-link buttons handled by `@bot.component(custom_id)`.

### `SelectMenuBuilder`

| Method | Description |
|---|---|
| `.placeholder(text)` | Set the placeholder text |
| `.option(label, value)` | Add an option (repeatable) |
| `.build(custom_id)` | Return a `discord.ui.View` |

Raises `ValueError` if no options were added. Handler wired via `@bot.component(custom_id)`.

### `ModalBuilder`

| Method | Description |
|---|---|
| `.title(text)` | Set the modal title (required) |
| `.field(key, label, *, placeholder=None, required=True)` | Add a text field (repeatable) |
| `await .send(ctx)` | Show the modal; returns `dict[str, str]` or `None` on timeout |

Raises `ValueError` if `.title()` was not called before `.send()`.

`await ctx.create_role(name, *, color=default, hoist=False, mentionable=False, reason=None)` → `discord.Role`

`await ctx.delete_role(role_id, *, reason=None)`

`ctx.get_member(user_id)` → `Member | None` — cache-only lookup

`await ctx.fetch_member(user_id)` → `discord.Member` — API fetch; raises `RuntimeError` in DMs, `discord.NotFound` if not in guild

### Messages / Reactions / Threads / Channel

`await ctx.purge(limit=10)` → `int` — bulk-delete; returns count

`await ctx.fetch_messages(limit=10)` → `list[discord.Message]`

`await ctx.delete_message(message, *, delay=None)`

`await ctx.react(message, emoji)` / `await ctx.unreact(message, emoji)` / `await ctx.clear_reactions(message)`

`await ctx.pin(message, *, reason=None)` / `await ctx.unpin(message, *, reason=None)`

`await ctx.crosspost(message)` — publish from announcement channel

`await ctx.create_thread(name, *, auto_archive_minutes=1440, reason=None)` → `discord.Thread`

`await ctx.slowmode(seconds, *, reason=None)` — 0 = off; max 21600

`await ctx.lock_channel(*, reason=None)` / `await ctx.unlock_channel(*, reason=None)` — @everyone send_messages

`ctx.fetch_bans(limit=100)` → `list[discord.BanEntry]`

`ctx.typing()` → context manager — show typing indicator; use with `async with ctx.typing()`

`await ctx.fetch_pinned_messages()` → `list[discord.Message]`

---

## `easycord.Plugin`

`async on_load()` — called when plugin is loaded

`async on_unload()` — called when plugin is unloaded

`self.bot` — back-reference to `Bot` (raises `RuntimeError` if accessed before `add_plugin`)

---

## Plugin decorators (`easycord.decorators`)

`@slash(name=None, *, description, guild_id=None, guild_only=False, ephemeral=False, permissions=None, cooldown=None, autocomplete=None, choices=None, aliases=None)` — same parameters as `Bot.slash`

`@on(event)` — mark method as event handler

`@task(*, seconds=0, minutes=0, hours=0)` — repeating background task; starts on load, stops on unload

---

## `easycord.SlashGroup`

Subclass with `name` and `description` class attributes. Use `@slash` on methods, then register with `bot.add_group(MyGroup())` or `bot.add_groups(...)`.

Group-level options:

- `guild_only=True` keeps the whole group out of DMs.
- `allowed_contexts=...` limits where the group can appear.
- `allowed_installs=...` controls which install types can use it.
- `nsfw=True` marks the entire group as age-gated.
- `default_permissions=...` applies one permission set to every command in the group.

---

## `easycord.Composer`

Fluent builder — chains middleware + plugins, returns a configured `Bot`.

| Method | Description |
| --- | --- |
| `.intents(intents)` | Set gateway intents |
| `.auto_sync(enabled)` | Enable/disable startup sync |
| `.log(level, fmt)` | Add `log_middleware` |
| `.catch_errors(message)` | Add `catch_errors` middleware |
| `.rate_limit(limit, window)` | Add `rate_limit` middleware |
| `.guild_only()` | Add `guild_only` middleware |
| `.use(middleware)` | Add custom middleware |
| `.add_plugin(plugin)` | Queue a plugin |
| `.add_plugins(*plugins)` | Queue several plugins |
| `.add_group(group)` | Queue a SlashGroup namespace |
| `.add_groups(*groups)` | Queue several SlashGroup namespaces |
| `.build()` | Return configured `Bot` |

---

## Built-in middleware (`easycord.middleware`)

All factories return `MiddlewareFn = async (ctx, next) -> None`.

| Factory | Blocks when… | Passes in DMs |
| --- | --- | --- |
| `log_middleware(level, fmt)` | never (logging only) | yes |
| `catch_errors(message)` | never (error handler) | yes |
| `rate_limit(limit=5, window=10.0)` | user exceeds `limit` calls in `window` seconds | yes |
| `guild_only()` | invoked in a DM | — |
| `dm_only()` | invoked in a guild | — |
| `admin_only(message)` | invoker lacks `administrator` permission | yes |
| `allowed_roles(*role_ids, message)` | invoker holds none of the given role IDs | yes |
| `channel_only(*channel_ids, message)` | channel not in the given set | yes |
| `boost_only(message)` | invoker is not a server booster | yes |
| `has_permission(*perms, message)` | invoker lacks any of the given permissions | yes |

---

## `easycord.ServerConfigStore`

`ServerConfigStore(data_dir=".easycord/server-config")` — per-guild JSON, atomic writes, per-guild async locks.

`await store.load(guild_id)` → `ServerConfig` (empty if none exists)

`await store.save(config)`

`await store.delete(guild_id)`

`await store.exists(guild_id)` → `bool`

### `ServerConfig`

| Group | Methods |
| --- | --- |
| Roles | `set_role(key, id)` `get_role(key)` `has_role(key)` `remove_role(key)` `list_roles()` `clear_roles()` |
| Channels | `set_channel(key, id)` `get_channel(key)` `has_channel(key)` `remove_channel(key)` `list_channels()` `clear_channels()` |
| Other | `set_other(key, val)` `get_other(key, default)` `has_other(key)` `remove_other(key)` `list_other()` `clear_other()` |
| Misc | `reset()` `merge(other)` `to_dict()` |

JSON schema: `{"roles": {key: int}, "channels": {key: int}, "other": {key: any}}`

---

## `easycord.AuditLog`

Structured embed logging to a Discord channel.

`AuditLog(bot, channel_id)` — instantiate in `on_load()`

`await log.send(title, description=None, *, fields=None, color=blue)` — posts an embed to the audit channel

---

## `LevelsPlugin` (`easycord.plugins.levels`)

`LevelsPlugin(*, xp_per_message=10, cooldown_seconds=60.0, data_dir=".easycord/levels", announce_levelups=True)`

XP formula: `level * (level + 1) // 2 * 100` total XP to reach `level`.

Slash commands: `/rank` `/leaderboard` `/give_xp` `/set_rank` `/remove_rank` `/set_level_role` `/ranks`

`await plugin.add_xp(guild_id, user_id, amount)` → `(total_xp, level, leveled_up)`

`plugin.get_entry(guild_id, user_id)` → `{"xp": int, "level": int}`

Storage: `<data_dir>/<guild_id>_xp.json`, `<data_dir>/<guild_id>_config.json`

## `TagsPlugin` (`easycord.plugins.tags`)

`TagsPlugin(*, data_dir="tags_data")`

Per-guild text snippet store. All commands require a guild context.

| Command | Args | Description |
| --- | --- | --- |
| `/tag get <name>` | name | Retrieve and display a tag |
| `/tag set <name> <text>` | name, text | Create or overwrite a tag |
| `/tag delete <name>` | name | Delete a tag (admin or original creator only) |
| `/tag list` | — | List all tag names in this server |

Storage: `tags_<guild_id>.json` in `data_dir`.

---

## Helper Libraries (`easycord.helpers`)

Production-ready utilities for common bot operations. Import directly:

```python
from easycord import EmbedBuilder, ContextHelpers, ConfigHelpers, ToolHelpers, RateLimitHelpers
```

### `EmbedBuilder`

Fluent embed constructor with presets:

```python
from easycord import EmbedBuilder

# Basic embed
embed = (
    EmbedBuilder()
    .title("User Info")
    .description("Details about the member")
    .field("Status", "Active")
    .color(0x00ff00)
    .build()
)

# Preset embeds
success = EmbedBuilder().success("Operation completed")
error = EmbedBuilder().error("Something went wrong")
info = EmbedBuilder().info("FYI: Important notice")
warning = EmbedBuilder().warning("Be careful")
```

Methods: `.title()` `.description()` `.field(name, value, inline=True)` `.footer()` `.color()` `.timestamp()` `.author()` `.thumbnail()` `.image()` `.build()`

### `ContextHelpers`

Shortcuts for common context operations:

```python
from easycord import ContextHelpers

# Respond + return all members in guild
members = await ContextHelpers.list_all_members(ctx)

# Respond + confirm before action
confirmed = await ContextHelpers.confirm_action(ctx, "Ban this user?")

# Respond + paginate results
await ContextHelpers.paginate_results(ctx, items, page_size=10)

# Respond + pick from list
choice = await ContextHelpers.pick_from_list(ctx, options)
```

### `ConfigHelpers`

Shortcuts for per-guild configuration:

```python
from easycord import ConfigHelpers

# Load config or defaults
config = await ConfigHelpers.load_or_default(store, guild_id, key, defaults={...})

# Atomically update
await ConfigHelpers.update_atomic(store, guild_id, key, field=value)

# Load all guild configs
all_configs = await ConfigHelpers.load_all_guilds(store)

# Delete config
await ConfigHelpers.delete_config(store, guild_id)
```

### `ToolHelpers`

Manage AI tool registration:

```python
from easycord import ToolHelpers, ToolSafety

# Register batch of tools
tools = [
    ("is_member", "Check if user is in server", ToolSafety.SAFE),
    ("timeout_user", "Timeout a user", ToolSafety.CONTROLLED),
]
ToolHelpers.register_batch(bot.tool_registry, tools)

# Check if tool callable
allowed = await ToolHelpers.check_permission(ctx, "timeout_user")

# List all registered tools
all_tools = ToolHelpers.list_all_tools(bot.tool_registry)
```

### `RateLimitHelpers`

Manage rate limits on tools/users:

```python
from easycord import RateLimitHelpers

# Create new limit: 3 uses per hour
limit = RateLimitHelpers.create_limit("ban", 3, 3600)

# Check if user hit limit
blocked = await RateLimitHelpers.check(limit, user_id)

# Reset user from limit
await RateLimitHelpers.reset_user(limit, user_id)

# Get limit stats
stats = await RateLimitHelpers.get_stats(limit)
```

---

## Scheduled Events (Context methods)

Create and manage Discord scheduled events:

`await ctx.create_event(name, start_time, *, end_time=None, description=None, channel=None, location=None, image=None)` → `discord.ScheduledEvent`

- `channel`: for voice/stage events
- `location`: string for external events (requires `end_time`)
- `image`: bytes for event cover image
- Entity type inferred automatically; raises `RuntimeError` if ambiguous

`await ctx.get_events()` → `list[discord.ScheduledEvent]` — all upcoming events in guild

`await ctx.delete_event(event_or_id)` — cancel event by object or ID

### Event Lifecycle Events

Listen for scheduled event changes via `@bot.on()`:

```python
@bot.on("scheduled_event_create")
async def on_event_created(event: discord.ScheduledEvent):
    print(f"Event created: {event.name}")

@bot.on("scheduled_event_update")
async def on_event_updated(before: discord.ScheduledEvent, after: discord.ScheduledEvent):
    print(f"Event updated: {before.name} → {after.name}")

@bot.on("scheduled_event_delete")
async def on_event_deleted(event: discord.ScheduledEvent):
    print(f"Event deleted: {event.name}")

@bot.on("scheduled_event_user_add")
async def on_rsvp(event: discord.ScheduledEvent, user: discord.User):
    print(f"{user.name} RSVPd to {event.name}")
```

---

## Invite Management (Context methods)

Create and manage server invites:

`await ctx.create_invite(*, max_uses=0, max_age=0, temporary=False, unique=True, reason=None)` → `discord.Invite`

- `max_uses=0`: unlimited uses
- `max_age=0`: never expires
- `temporary=False`: invites do NOT expire after user joins
- `unique=True`: create new invite each call (set `False` to reuse)

`await ctx.get_invites()` → `list[discord.Invite]` — all invites for current channel

`await ctx.revoke_invite(code)` — delete invite by code

---

## AI & Orchestration

### `ctx.ai(...)`

Use a shared provider for small custom AI commands without adding a full plugin:

```python
from easycord import Bot
from easycord.plugins import OpenAIProvider

provider = OpenAIProvider(api_key="sk-...")
bot = Bot(ai_provider=provider)

@bot.slash(description="Ask AI")
async def ask(ctx, prompt: str):
    response = await ctx.ai(prompt, model="gpt-4o")
    await ctx.respond(response[:2000])
```

### `AIPlugin` / `OpenClaudePlugin`

`AIPlugin(provider, *, rate_limit=3, rate_window=60.0)` registers `/ask` for any provider.
`OpenClaudePlugin(api_key=None, model="claude-3-5-sonnet-20241022", rate_limit=3, rate_window=60.0)` keeps the Claude shortcut.

`OpenClaudePlugin` sends `openclaude.thinking` through `ctx.t(...)` before calling the provider, then edits that message with the final response. `AIPlugin` and `OpenClaudePlugin` both enforce the per-user, per-guild request limit and use `ai.rate_limited` for localized cooldown text.

### `Orchestrator`

Multi-provider LLM routing with tool calling:

```python
from easycord import Orchestrator, FallbackStrategy, RunContext
from easycord.plugins import AnthropicProvider, GroqProvider

# Create with fallback chain
orchestrator = Orchestrator(
    strategy=FallbackStrategy([
        AnthropicProvider(),  # Try Claude first
        GroqProvider(),       # Fallback to Groq
    ]),
    tools=bot.tool_registry,
)

# Run with tool calling
context = RunContext(
    messages=[{"role": "user", "content": "Check if user 123 is in server"}],
    ctx=ctx,
    max_steps=5,  # Max tool calls before returning
    timeout=30.0,
)
result = await orchestrator.run(context)
```

### `RunContext`

`RunContext(*, messages, ctx, max_steps=5, timeout=30.0, system_prompt=None)`

- `messages`: conversation history `[{"role": "user/assistant", "content": ...}]`
- `ctx`: Discord context (for tool execution)
- `max_steps`: max iterations before giving final answer
- `timeout`: seconds per tool call
- `system_prompt`: override default system instructions

### `ToolRegistry` / `@ai_tool`

```python
from easycord import Plugin, ai_tool, ToolSafety

class MyPlugin(Plugin):
    @ai_tool(
        description="Check if user is in server",
        safety=ToolSafety.SAFE,
        permissions=["view_members"],
    )
    async def is_member(self, ctx, user_id: int) -> str:
        try:
            await ctx.guild.fetch_member(user_id)
            return "User is a member"
        except:
            return "User is not a member"

    @ai_tool(
        description="Timeout user",
        safety=ToolSafety.CONTROLLED,
        require_admin=True,
    )
    async def timeout_user(self, ctx, user_id: int, seconds: int = 3600) -> str:
        member = await ctx.guild.fetch_member(user_id)
        await member.timeout(timedelta(seconds=seconds))
        return f"Timed out {member.name}"
```

Safety levels:
- **SAFE** — read-only (queries, lookups, info)
- **CONTROLLED** — validated actions (moderation, writes, role changes)
- **RESTRICTED** — never expose to AI (admin-only, destructive)

---

## Conversation Memory

Maintain multi-turn context across commands:

```python
from easycord import ConversationMemory, Conversation

memory = ConversationMemory(max_conversations=100)

# Add to conversation
conv = memory.get_or_create("user_123")
conv.add_turn("user", "What's my level?")
conv.add_turn("assistant", "You're level 5")

# Retrieve history
history = conv.get_history(limit=10)  # Last 10 turns

# Clear conversation
conv.clear()
```

`Conversation` methods:
- `.add_turn(role, content)` — add message
- `.get_history(limit=None)` → `list[ConversationTurn]` — recent messages
- `.clear()` — reset conversation
- `.to_messages()` → list for LLM (role/content format)

---

## Decorators (Advanced)

### `@component`

Handle button/select interactions:

```python
@bot.component("approve")
async def on_approve(ctx):
    await ctx.respond("Approved!", ephemeral=True)

@bot.component("vote_")  # Prefix match
async def on_vote(ctx, option):
    await ctx.respond(f"Voted for {option}")
```

Middleware runs on components the same as slash commands.

### `@modal`

Handle modal form submissions:

```python
@bot.modal("feedback_form")
async def on_feedback(ctx, form_data: dict[str, str]):
    feedback = form_data.get("message", "")
    await ctx.respond(f"Feedback received: {feedback}")
```

### `@task`

Background repeating task:

```python
@task(hours=1)
async def periodic_cleanup(self):
    # Runs every hour, auto-starts on plugin load, stops on unload
    await self.cleanup_old_data()
```

Valid parameters: `seconds`, `minutes`, `hours`, `days`.

### `@on` (Event handlers)

```python
@on("member_join")
async def welcome(self, member):
    await member.send(f"Welcome {member.name}!")

@on("message")
async def log_message(self, message):
    if not message.author.bot:
        print(f"{message.author}: {message.content}")
```

Common events: `member_join`, `member_remove`, `message`, `message_edit`, `reaction_add`, `ready`, `guild_join`, `guild_remove`.

---

## Composer (Fluent Builder)

Build a bot declaratively:

```python
from easycord import Composer

bot = (
    Composer()
    .intents("default")
    .with_members()
    .with_messages()
    .auto_sync(True)
    .log(level="INFO")
    .catch_errors("An error occurred")
    .add_plugin(ModerationPlugin())
    .add_plugin(LevelsPlugin())
    .add_group(MySlashGroup())
    .build()
)
```

Available shortcuts:
- `.intents(intents)` — set gateway intents
- `.with_members()` / `.with_messages()` / `.with_invites()` — enable privileged intents
- `.auto_sync(enabled)` — command sync at startup
- `.log(level, fmt)` — add logging middleware
- `.catch_errors(message)` — add error handler
- `.rate_limit(limit, window)` — add rate limiting
- `.guild_only()` — add guild-only guard
- `.use(middleware)` — add custom middleware
- `.add_plugin(plugin)` / `.add_plugins(*plugins)` — queue plugins
- `.add_group(group)` / `.add_groups(*groups)` — queue groups
- `.build()` — return configured Bot
