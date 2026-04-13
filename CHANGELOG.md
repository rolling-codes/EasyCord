# Changelog

## [2.0] — 2026-04-12

Context menus, message editing, pinning, crosspost publishing, voice state, ban listing, and two bug fixes.

**Jump to docs:**

- [Context menus](docs/api.md#context-menus)
- [Response editing](docs/api.md#responding)
- [Pinning](docs/api.md#message-management)
- [Voice state](docs/api.md#easycordcontext)
- [Member & ban helpers](docs/api.md#member--ban-helpers)

---

### 2.0 — New `Bot` decorators

| Decorator | What it does |
| --- | --- |
| `@bot.user_command(name)` | Register a right-click User context menu command |
| `@bot.message_command(name)` | Register a right-click Message context menu command |

Both pass middleware through the same stack as slash commands. Handlers receive `(ctx, target)` where `target` is `discord.Member \| discord.User` or `discord.Message` respectively.

Full docs: [docs/api.md#context-menus](docs/api.md#context-menus)

---

### 2.0 — New `Context` helpers

| Method / Property | What it does |
| --- | --- |
| `ctx.voice_channel` | Property — voice/stage channel the invoker is currently in, or `None` |
| `await ctx.edit_response(content, *, embed)` | Edit the bot's original response in-place |
| `await ctx.pin(message, *, reason)` | Pin a message in the current channel |
| `await ctx.unpin(message, *, reason)` | Unpin a message from the current channel |
| `await ctx.crosspost(message)` | Publish a message from an announcement channel to all followers |
| `ctx.get_member(user_id)` | Cache-only guild member lookup — no API call, returns `None` if not found |
| `await ctx.fetch_bans(limit)` | Return a list of `discord.BanEntry` for the guild |

Full signatures: [docs/api.md#easycordcontext](docs/api.md#easycordcontext)

---

### 2.0 — Bug fixes

| Method | Fix |
| --- | --- |
| `ctx.move_member` | Now accepts `discord.StageChannel` as a valid destination (previously rejected all non-`VoiceChannel` channels) |
| `ctx.purge` | Now works in `discord.Thread` channels (previously restricted to `TextChannel` only) |

---

## [1.199] — 2026-04-12

Reactions, targeted message deletion, static parameter choices, and bot-level user/member lookup.

**Jump to docs:**

- [Reactions](docs/api.md#reactions)
- [Message deletion](docs/api.md#message-management)
- [Static choices on slash params](docs/api.md#slash-commands)
- [Bot fetch helpers](docs/api.md#easycordbot)

---

### New `Context` helpers

#### Reactions

| Method | What it does |
| --- | --- |
| `await ctx.react(message, emoji)` | Add a reaction to a message |
| `await ctx.unreact(message, emoji)` | Remove the bot's own reaction |
| `await ctx.clear_reactions(message)` | Remove all reactions (requires `manage_messages`) |

Full signatures: [docs/api.md#reactions](docs/api.md#reactions)

#### Message management

| Method | What it does |
| --- | --- |
| `await ctx.delete_message(message, *, delay)` | Delete a message, optionally after a delay in seconds |

Full signatures: [docs/api.md#message-management](docs/api.md#message-management)

---

### New `@slash` / `@bot.slash` parameter

| Parameter | What it does |
| --- | --- |
| `choices={"param": ["a", "b", "c"]}` | Show a fixed dropdown in Discord for the named parameter |

Works on both `@bot.slash` and the plugin `@slash` decorator. Values may be strings or numbers — Discord renders them as a locked dropdown (no free-text entry).

Full docs: [docs/api.md#slash-commands](docs/api.md#slash-commands)

---

### New `Bot` method

| Method | What it does |
| --- | --- |
| `await bot.fetch_member(guild_id, user_id)` | Fetch a `discord.Member` by guild and user ID (cache-first, API fallback) |

`await bot.fetch_user(user_id)` is already available via the inherited `discord.Client` API.

Full signatures: [docs/api.md#easycordbot](docs/api.md#easycordbot)

---

## [1.198] — 2026-04-12

Server management: nickname editing, voice moves, role CRUD, slowmode, and channel locking.

**Jump to docs:**

- [Member management](docs/api.md#member-management)
- [Role management](docs/api.md#role-management)
- [Channel management](docs/api.md#channel-management)

---

### 1.198 — New `Context` helpers

#### Member management

| Method | What it does |
| --- | --- |
| `await ctx.set_nickname(member, nickname, *, reason)` | Set or clear a member's server nickname (`None` resets to default) |
| `await ctx.move_member(member, channel_id, *, reason)` | Move to a voice channel by ID, or disconnect (`None`) |

Full signatures: [docs/api.md#member-management](docs/api.md#member-management)

#### Role management

| Method | What it does |
| --- | --- |
| `await ctx.create_role(name, *, color, hoist, mentionable, reason)` | Create a new role; returns `discord.Role` |
| `await ctx.delete_role(role_id, *, reason)` | Delete a role by ID |

Full signatures: [docs/api.md#role-management](docs/api.md#role-management)

#### Channel management

| Method | What it does |
| --- | --- |
| `await ctx.slowmode(seconds, *, reason)` | Set slowmode delay (0 = off, max 21600) |
| `await ctx.lock_channel(*, reason)` | Prevent @everyone from sending messages |
| `await ctx.unlock_channel(*, reason)` | Restore @everyone send permission |

Full signatures: [docs/api.md#channel-management](docs/api.md#channel-management)

---

## [1.197] — 2026-04-12

Moderation helpers, role assignment, bulk delete, file sending, threads, message history, select-menu UI, autocomplete, and bot presence.

**Jump to docs:**

- [Autocomplete](docs/api.md#slash-commands)
- [Bot presence](docs/api.md#presence)
- [Select-menu UI (`ctx.choose`)](docs/api.md#interactive-ui)
- [Moderation helpers](docs/api.md#moderation)
- [Role management](docs/api.md#role-management)
- [Message management](docs/api.md#message-management)
- [Threads & history](docs/api.md#threads)

---

### 1.197 — New `Context` helpers

| Method | What it does |
| --- | --- |
| `await ctx.choose(prompt, options, ...)` | Select-menu; returns chosen string or `None` on timeout |
| `await ctx.kick(member, *, reason)` | Kick a member |
| `await ctx.ban(member, *, reason, delete_message_days)` | Ban a member |
| `await ctx.timeout(member, duration, *, reason)` | Temporarily mute (seconds) |
| `await ctx.unban(user, *, reason)` | Unban a user |
| `await ctx.add_role(member, role_id, *, reason)` | Add a role by ID |
| `await ctx.remove_role(member, role_id, *, reason)` | Remove a role by ID |
| `await ctx.purge(limit)` | Bulk-delete recent messages; returns count |
| `await ctx.send_file(path, *, filename, content, ephemeral)` | Send a file attachment |
| `await ctx.fetch_messages(limit)` | Return N most recent messages |
| `await ctx.create_thread(name, *, auto_archive_minutes, reason)` | Create a thread; returns `discord.Thread` |

### 1.197 — New `Bot` method

| Method | What it does |
| --- | --- |
| `await bot.set_status(status, *, activity, activity_type)` | Set presence and activity text |

### 1.197 — New `@slash` parameter

| Parameter | What it does |
| --- | --- |
| `autocomplete={"param": async_fn}` | Live suggestions as the user types |

---

## 1.196 and earlier — Initial release

| Feature | Docs |
| --- | --- |
| `@bot.slash` — slash commands, permission guards, cooldowns | [concepts.md](docs/concepts.md#slash-commands) |
| `@bot.on` — multi-handler event system | [concepts.md](docs/concepts.md#events) |
| `bot.use` — middleware chain | [concepts.md](docs/concepts.md#middleware) |
| `Plugin` / `SlashGroup` — lifecycle hooks and grouping | [concepts.md](docs/concepts.md#plugins) |
| `@task` — repeating background tasks | [api.md](docs/api.md#decorators-for-plugins-easycorddecorators) |
| `Context` — respond, defer, send\_embed, dm, send\_to, ask\_form, confirm, paginate | [api.md](docs/api.md#easycordcontext) |
| `ServerConfigStore` — per-guild atomic JSON config | [api.md](docs/api.md#easycordserverconfigstore) |
| `AuditLog` — structured embed logging | [api.md](docs/api.md) |
| `Composer` — fluent bot builder | [README.md](README.md#composer) |
