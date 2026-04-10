# EasyCord documentation

EasyCord is a small, decorator-first framework for building Discord bots on top of `discord.py>=2.0`.

It provides:

- **Slash command registration** via `Bot.slash(...)`
- **Event listeners** via `Bot.on(...)` (supports multiple handlers per event)
- **Middleware** that wraps every slash command invocation
- **Plugins** (`Plugin` subclasses) with `@slash` and `@on` decorators

## Requirements

- **Python**: 3.10+ (type syntax like `X | Y` is used)
- **Dependency**: `discord.py>=2.0.0` (see `requirements.txt`)

## Installation

EasyCord is currently vendored (copied) into your project rather than installed from PyPI:

1. Install dependency:

```bash
pip install "discord.py>=2.0"
```

2. Put the EasyCord source on your import path (commonly as a package folder named `easycord/`).

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

## Documentation map

- `getting-started.md`: how to run, develop, and structure a bot
- `concepts.md`: slash commands, events, middleware, plugins, lifecycle
- `api.md`: API reference for `EasyCord`, `Context`, decorators, middleware factories, `Plugin`
- `examples.md`: patterns and snippets based on included examples
- `fork-and-expand.md`: how to organize and extend a real bot project

