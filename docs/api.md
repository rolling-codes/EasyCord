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
| Add locale-aware strings | `LocalizationManager` + `ctx.t(...)` |
| Build a bot in steps | `Composer()` |
| Save guild settings | `ServerConfigStore` |

```python
from easycord import Bot
from easycord.plugins import WelcomePlugin, LevelsPlugin

bot = Bot()
bot.add_plugins(WelcomePlugin(), LevelsPlugin())
```

That one pattern covers most starter bots: create the bot, load the plugins you
need, then register a few slash commands on top.

## `easycord.Bot`

`Bot(*, intents=None, auto_sync=True, localization=None, default_locale="en-US", translations=None, **kwargs)`

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

`bot.localization` / `bot.i18n` — `LocalizationManager` instance used by `Context.t(...)`

`@Bot.on_error` / `Bot.on_error(func)` — register a global error handler `async def handler(ctx, error)` called when any slash command raises an unhandled exception; overwrites any previously registered handler

`Bot.add_plugin(plugin)` — load one plugin; raises `TypeError` / `ValueError` on bad input or duplicate

`Bot.add_plugins(*plugins)` — load several plugins in one call

`Bot.add_group(group)` — load one SlashGroup namespace; raises `TypeError` / `ValueError` on bad input or duplicate

`Bot.add_groups(*groups)` — load several SlashGroup namespaces in one call

`await Bot.remove_plugin(plugin)` — unload plugin; removes commands, deregisters handlers, calls `on_unload()`

`await Bot.reload_plugin(name: str)` — reload a plugin in-place by class name; calls `on_unload()` then `on_load()` on the same instance; constructor arguments and in-memory state preserved; raises `ValueError` if no loaded plugin has that class name

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

### Localization

`LocalizationManager(default_locale="en-US", translations=None)` — store string templates by locale and resolve fallback chains

`bot.localization.register(locale, translations)` — add or merge a locale catalog

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
| `ctx.locale` | `discord.Locale \| str \| None` | The invoking user's locale when Discord provides one |
| `ctx.guild_locale` | `discord.Locale \| str \| None` | The guild locale when Discord provides one |
| `ctx.channel` | `Messageable \| None` | Channel |
| `ctx.command_name` | `str \| None` | Slash command name |
| `ctx.voice_channel` | `VoiceChannel \| StageChannel \| None` | Invoker's current voice channel |
| `ctx.is_admin` | `bool` | `True` if invoker has administrator permission; `False` in DMs |
| `ctx.data` | `dict \| None` | Raw interaction data |
| `ctx.bot_permissions` | `discord.Permissions` | Bot's own permissions in the current channel; raises `RuntimeError` in DMs |

### Responding

`await ctx.respond(content=None, *, ephemeral=False, embed=None, **kwargs)` — first call: `send_message`; subsequent: `followup.send`

`await ctx.defer(*, ephemeral=False)` — acknowledge without visible reply; use before slow operations

`await ctx.send_embed(title, description=None, *, fields=None, footer=None, thumbnail=None, image=None, author=None, timestamp=None, color=blue, ephemeral=False)` — fields: `[(name, value)]` or `[(name, value, inline)]`; `thumbnail`/`image`: URL strings; `author`: name string or `{"name", "icon_url", "url"}` dict; `timestamp=True` uses current UTC time

`ctx.t(key, *, default=None, locale=None, guild_locale=None, **kwargs)` — translate and format a string key using the bot's localization manager

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
| `.localization(manager)` / `.i18n(manager)` | Provide a shared `LocalizationManager` |
| `.default_locale(locale)` | Set the manager's default locale |
| `.translations(mapping)` | Seed locale catalogs |
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
