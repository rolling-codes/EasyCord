# Examples and patterns

These snippets are designed to be copied into a first bot project.

## Smallest starter bot

```python
from easycord import Bot

bot = Bot()

@bot.slash(description="Ping the bot.")
async def ping(ctx):
    await ctx.respond("Pong!")
```

## Command validation with ephemeral errors

```python
@bot.slash(description="Echo your message back to you.")
async def echo(ctx, message: str, times: int = 1):
    if times < 1 or times > 5:
        await ctx.respond("`times` must be between 1 and 5.", ephemeral=True)
        return
    await ctx.respond("\n".join([message] * times))
```

## Plugin structure

```python
from easycord import Bot, Plugin, slash, on

bot = Bot()

class MyPlugin(Plugin):
    @slash(description="Roll a dice")
    async def roll(self, ctx, sides: int = 6):
        import random
        await ctx.respond(str(random.randint(1, sides)))

    @on("member_join")
    async def welcome(self, member):
        await member.send("Welcome!")

bot.add_plugin(MyPlugin())
```

For the bundled example plugins, `server_commands/__init__.py` keeps the default plugin list in one place and exposes `load_default_plugins(bot)` so bot startup stays simple.

## Grouped commands

```python
from easycord import Composer, SlashGroup, slash

class ModerationGroup(SlashGroup, name="mod", description="Moderation commands"):
    @slash(description="Kick a member")
    async def kick(self, ctx, member):
        await member.kick()
        await ctx.respond(f"Kicked {member.display_name}.")

bot = Composer().add_groups(ModerationGroup()).build()
```

## Using `respond()` vs follow-ups

`Context.respond()` automatically switches to a follow-up message if you’ve already responded once. That means you can write:

```python
await ctx.respond("First response")
await ctx.respond("Second response")  # follow-up automatically
```

## Development: guild-only commands

```python
@bot.slash(description="Instant during development", guild_id=123456789012345678)
async def dev(ctx):
    await ctx.respond("Instant in one guild.")
```

