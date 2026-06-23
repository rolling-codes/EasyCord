# Context Reference

Every EasyCord command receives a `ctx` object. It carries the Discord interaction and exposes helpers organized into five categories: responding, sending to other places, member lookups, moderation, and channel management.

---

## Properties

```python
ctx.user          # discord.User | discord.Member — the command invoker
ctx.member        # discord.Member | None — the invoker as a Member (None in DMs)
ctx.guild         # discord.Guild | None — the server, or None in DMs
ctx.guild_id      # int | None — shortcut for ctx.guild.id; safe without a guild check
ctx.channel       # the channel the command was used in
ctx.locale        # str — the invoker's Discord locale (e.g. "en-US", "fr", "ja")
ctx.is_admin      # bool — True if the invoker has the administrator permission
ctx.bot_permissions  # discord.Permissions — the bot's permissions in ctx.channel
ctx.interaction   # discord.Interaction — the raw interaction object
```

`ctx.is_admin` is a property — do not call it as a method. `ctx.bot_permissions` raises `RuntimeError` in DMs.

---

## Responding

### `ctx.respond()`

Send a reply to the command. The first call sends the initial response; additional calls send follow-up messages automatically.

```python
async def respond(
    content: str | None = None,
    *,
    ephemeral: bool = False,
    embed: discord.Embed | None = None,
    silent: bool = False,
    suppress_embeds: bool = False,
    **kwargs,
) -> None
```

```python
await ctx.respond("Hello!")
await ctx.respond("Only you see this.", ephemeral=True)
await ctx.respond(embed=discord.Embed(title="Result", description="Done"))
```

`silent=True` suppresses the notification sound. `suppress_embeds=True` prevents link previews.

`ctx.send(...)` is an alias for `ctx.respond(...)`.

### `ctx.defer()`

Acknowledge the interaction without a visible reply. Use this for commands that take more than 3 seconds, then call `ctx.respond()` later.

```python
async def defer(*, ephemeral: bool = False) -> None
```

```python
@slash(description="Slow command")
async def slow(self, ctx):
    await ctx.defer()
    result = await long_running_operation()
    await ctx.respond(result)
```

Has no effect if `respond()` has already been called.

### `ctx.edit_response()`

Edit the bot's original response to this interaction. Useful for "Loading…" → result patterns.

```python
async def edit_response(
    content: str | None = None,
    *,
    embed: discord.Embed | None = None,
    **kwargs,
) -> None
```

```python
await ctx.respond("Loading…")
result = await fetch_data()
await ctx.edit_response(content=result)
```

---

## Sending to other places

### `ctx.dm()`

Send a direct message to the user who invoked the command. Raises `RuntimeError` if the user has DMs disabled.

```python
async def dm(
    content: str | None = None,
    *,
    embed: discord.Embed | None = None,
    **kwargs,
) -> None
```

```python
await ctx.dm("Your report has been submitted.")
```

### `ctx.send_to()`

Send a message to any channel by ID. Looks up the channel from the client cache first; falls back to an API fetch.

```python
async def send_to(channel_id: int, content: str | None = None, **kwargs) -> None
```

```python
LOG_CHANNEL = 123456789

await ctx.send_to(LOG_CHANNEL, f"{ctx.user} ran /nuke in {ctx.guild.name}")
await ctx.send_to(LOG_CHANNEL, embed=log_embed)
```

Raises `RuntimeError` if the channel doesn't exist or the bot lacks access.

### `ctx.send_file()`

Send a file attachment as the command response.

```python
async def send_file(
    path: str,
    *,
    filename: str | None = None,
    content: str | None = None,
    ephemeral: bool = False,
) -> None
```

```python
await ctx.send_file("reports/output.csv", filename="report.csv", content="Here's your export:")
```

### `ctx.forward()`

Forward a `discord.Message` to the current channel (or another channel).

```python
async def forward(message: discord.Message, *, channel: discord.abc.Messageable | None = None) -> None
```

---

## Member lookups

### `ctx.get_member()`

Look up a guild member from the local cache without an API call. Returns `None` if not cached or in DMs.

```python
def get_member(user_id: int) -> discord.Member | None
```

### `ctx.fetch_member()`

Fetch a guild member by user ID. Tries the cache first; falls back to an API call. Raises `RuntimeError` in DMs and `discord.NotFound` if the user isn't in the guild.

```python
async def fetch_member(user_id: int) -> discord.Member
```

```python
@slash(description="Show info about a user ID")
async def userinfo(self, ctx, user_id: str):
    try:
        member = await ctx.fetch_member(int(user_id))
    except discord.NotFound:
        await ctx.respond("That user is not in this server.", ephemeral=True)
        return
    await ctx.respond(f"{member.display_name} joined {member.joined_at:%Y-%m-%d}")
```

---

## Moderation

All moderation methods require the bot to have the relevant permissions.

### `ctx.kick(member, *, reason=None)`

Kick a member from the server.

```python
await ctx.kick(member, reason="Spam")
```

### `ctx.ban(member, *, reason=None, delete_message_days=0)`

Ban a member. `delete_message_days` (0–7) controls how many days of messages to delete.

```python
await ctx.ban(member, reason="Repeated violations", delete_message_days=1)
```

### `ctx.unban(user, *, reason=None)`

Unban a user. Raises `RuntimeError` in DMs.

### `ctx.timeout(member, duration, *, reason=None)`

Temporarily mute a member. `duration` is in seconds.

```python
await ctx.timeout(member, 3600, reason="Cooling off period")  # 1 hour
```

### `ctx.set_nickname(member, nickname, *, reason=None)`

Set or clear a member's server nickname. Pass `None` to reset to default.

### `ctx.add_role(member, role_id, *, reason=None)`
### `ctx.remove_role(member, role_id, *, reason=None)`

Add or remove a role by ID.

```python
VERIFIED_ROLE = 987654321
await ctx.add_role(member, VERIFIED_ROLE)
```

### `ctx.create_role(name, *, color, hoist, mentionable, reason=None) → discord.Role`

Create a new role and return it.

### `ctx.delete_role(role_id, *, reason=None)`

Delete a role by ID.

### `ctx.move_member(member, channel_id, *, reason=None)`

Move a member to a voice channel by ID, or disconnect them by passing `None`.

### `ctx.purge(limit=10) → int`

Bulk-delete recent messages in the current channel or thread. Returns the count deleted. Only works in text channels and threads.

### `ctx.fetch_bans(limit=None) → list[discord.BanEntry]`

Return ban entries for the current guild.

---

## Channel management

### `ctx.lock_channel(*, reason=None)`
### `ctx.unlock_channel(*, reason=None)`

Prevent or restore `@everyone`'s ability to send messages in the current channel. Preserves existing per-role overrides.

```python
@slash(description="Lock this channel")
async def lock(self, ctx):
    await ctx.lock_channel(reason=f"Locked by {ctx.user}")
    await ctx.respond("Channel locked.", ephemeral=True)
```

### `ctx.slowmode(seconds, *, reason=None)`

Set the slowmode delay on the current text channel. Pass `0` to disable. Maximum is `21600` (6 hours).

### `ctx.create_thread(name, *, auto_archive_minutes=1440, reason=None) → discord.Thread`

Create a public thread in the current channel. `auto_archive_minutes` must be one of `60`, `1440`, `4320`, or `10080`.

```python
thread = await ctx.create_thread(f"Support: {ctx.user.display_name}")
await thread.send(f"Hi {ctx.user.mention}, how can we help?")
```

### `ctx.fetch_messages(limit=10) → list[discord.Message]`

Return the most recent messages in the current channel.

### `ctx.react(message, emoji)` / `ctx.unreact(message, emoji)` / `ctx.clear_reactions(message)`

Add, remove, or clear reactions on a message.

### `ctx.delete_message(message, *, delay=None)`

Delete a message, optionally after a delay in seconds.

### `ctx.pin(message)` / `ctx.unpin(message)`

Pin or unpin a message. Requires `manage_messages`.

### `ctx.crosspost(message)`

Publish a message from an announcement channel to all followers.

### `ctx.typing()`

Context manager that shows the typing indicator. Use with `async with`:

```python
async with ctx.typing():
    result = await slow_operation()
await ctx.respond(result)
```

---

## Interactive UI

See [docs/context-interactive-ui.md](context-interactive-ui.md) for `ctx.confirm()`, `ctx.paginate()`, `ctx.choose()`, `ctx.prompt()`, and `ctx.ask_form()`.

---

## AI shortcuts

See [docs/conversation-memory.md](conversation-memory.md) for `ctx.ai()` and `ctx.conversation_history()`.
