# EasyCord documentation

EasyCord is a decorator-first framework for building Discord bots on top of `discord.py>=2.0`.

It removes the boilerplate that discord.py requires for every common task while keeping the full power of the underlying library available whenever you need it.

## Why EasyCord?

Every feature below collapses a block of raw discord.py code into a single line or decorator.

### Slash commands

**discord.py** — build a `CommandTree`, register with `@tree.command`, handle `discord.Interaction` directly, sync manually in `setup_hook`.

```python
tree = app_commands.CommandTree(client)

@tree.command(name="ping", description="Ping the bot")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message("Pong!")

async def setup_hook():
    await tree.sync()
```

**EasyCord** — one decorator, no tree, no interaction object, auto-synced.

```python
@bot.slash(description="Ping the bot")
async def ping(ctx):
    await ctx.respond("Pong!")
```

---

### Permission checks

**discord.py** — check permissions manually inside every command.

```python
@tree.command()
async def kick(interaction: discord.Interaction, member: discord.Member):
    if not interaction.guild:
        await interaction.response.send_message("Server only.", ephemeral=True)
        return
    m = interaction.guild.get_member(interaction.user.id)
    if not m or not m.guild_permissions.kick_members:
        await interaction.response.send_message("Missing permission.", ephemeral=True)
        return
    await member.kick()
    await interaction.response.send_message(f"Kicked {member.display_name}.")
```

**EasyCord** — declared on the decorator, checked automatically.

```python
@bot.slash(description="Kick a member", permissions=["kick_members"])
async def kick(ctx, member: discord.Member):
    await member.kick()
    await ctx.respond(f"Kicked {member.display_name}.")
```

---

### Per-user cooldowns

**discord.py** — track timestamps yourself in a dict, guard every invocation.

```python
_last: dict[int, float] = {}

@tree.command()
async def roll(interaction: discord.Interaction):
    now = time.monotonic()
    remaining = 5.0 - (now - _last.get(interaction.user.id, 0.0))
    if remaining > 0:
        await interaction.response.send_message(
            f"Cooldown: {remaining:.1f}s", ephemeral=True
        )
        return
    _last[interaction.user.id] = now
    await interaction.response.send_message(str(random.randint(1, 6)))
```

**EasyCord** — one argument.

```python
@bot.slash(description="Roll dice", cooldown=5)
async def roll(ctx):
    await ctx.respond(str(random.randint(1, 6)))
```

---

### Rich embeds

**discord.py** — build the embed, add each field individually, then send.

```python
embed = discord.Embed(title="Stats", color=discord.Color.green())
embed.add_field(name="Members", value="150", inline=True)
embed.add_field(name="Online", value="42", inline=True)
embed.set_footer(text="Updated just now")
await interaction.response.send_message(embed=embed)
```

**EasyCord** — one call.

```python
await ctx.send_embed(
    "Stats",
    fields=[("Members", "150"), ("Online", "42")],
    footer="Updated just now",
    color=discord.Color.green(),
)
```

---

### DMs and cross-channel messaging

**discord.py** — fetch the channel, guard against cache misses, then send.

```python
# DM the user
await interaction.user.send("Private message")

# Send to a specific channel
channel = client.get_channel(LOG_CHANNEL_ID)
if channel is None:
    channel = await client.fetch_channel(LOG_CHANNEL_ID)
await channel.send("Log entry")
```

**EasyCord** — one line each.

```python
await ctx.dm("Private message")
await ctx.send_to(LOG_CHANNEL_ID, "Log entry")
```

---

### Per-guild config

**discord.py** — no built-in solution. You build your own database layer or JSON management.

**EasyCord** — built-in atomic JSON store, no setup.

```python
store = ServerConfigStore()
cfg = await store.load(guild_id)
cfg.set_role("moderator", role_id)
cfg.set_channel("logs", channel_id)
await store.save(cfg)
```

---

## Requirements

- Python 3.10+
- `discord.py>=2.0.0`

## Installation

```bash
git clone https://github.com/rolling-codes/EasyCord.git
cd EasyCord
pip install -e .
```

## Quick start

```python
import os
from easycord import Bot
from easycord.middleware import log_middleware, catch_errors

bot = Bot()
bot.use(log_middleware())
bot.use(catch_errors())

@bot.slash(description="Ping the bot")
async def ping(ctx):
    await ctx.respond("Pong!")

bot.run(os.environ["DISCORD_TOKEN"])
```

### Persistent button/select-menu handlers

**discord.py** — manually intercept every interaction, check the type, parse the custom ID.

```python
@client.event
async def on_interaction(interaction):
    if interaction.type != discord.InteractionType.component:
        return
    cid = interaction.data.get("custom_id", "")
    if cid.startswith("ban_"):
        user_id = int(cid.removeprefix("ban_"))
        member = await interaction.guild.fetch_member(user_id)
        await member.ban()
        await interaction.response.send_message("Banned.")
```

**EasyCord** — one decorator, suffix extracted automatically.

```python
@bot.component("ban_")
async def ban_button(ctx, suffix: str):
    member = await ctx.fetch_member(int(suffix))
    await ctx.ban(member)
    await ctx.respond("Banned.")
```

---

### Permission-gated middleware

**discord.py** — repeat the permission check inside every command.

```python
@tree.command()
async def kick(interaction):
    m = interaction.guild.get_member(interaction.user.id)
    if not m or not m.guild_permissions.kick_members:
        await interaction.response.send_message("Missing permission.", ephemeral=True)
        return
    ...
```

**EasyCord** — register once, applies to every command.

```python
bot.use(has_permission("kick_members"))
```

---

### Webhook messages

**discord.py** — create a webhook object, store it, call send separately.

```python
webhook = await channel.create_webhook(name="Bot")
await webhook.send("Hello!", username="MyBot")
```

**EasyCord** — one call, webhook created and cached automatically.

```python
await bot.send_webhook(CHANNEL_ID, "Hello!", username="MyBot")
```

---

## Documentation map

- [`getting-started.md`](getting-started.md): how to run, develop, and structure a bot
- [`concepts.md`](concepts.md): slash commands, events, middleware, plugins, lifecycle
- [`api.md`](api.md): full API reference
- [`examples.md`](examples.md): patterns and snippets
- [`fork-and-expand.md`](fork-and-expand.md): how to organize and extend a real bot project
