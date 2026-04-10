# Examples and patterns

This project includes example scripts (`examples/basic_bot.py`, `examples/plugin_bot.py`) demonstrating typical usage.

## Inline middleware for timing

```python
@bot.use
async def timing_middleware(ctx, next):
    import time
    start = time.monotonic()
    await next()
    elapsed = (time.monotonic() - start) * 1000
    print(f"/{ctx.command_name} finished in {elapsed:.1f}ms")
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

