# Getting started

## Create a bot application

1. Create an application in the Discord Developer Portal.
2. Create a bot user and copy the token.
3. Invite the bot with OAuth scopes:
   - `bot`
   - `applications.commands`
4. Enable any intents you need (for example, member join events).

## Running a bot locally

Set your token in an environment variable (recommended):

```bash
DISCORD_TOKEN=your_token_here python my_bot.py
```

## Minimal bot

```python
import os
from easycord import Bot

bot = Bot()

@bot.slash(description="Ping the bot")
async def ping(ctx):
    await ctx.respond("Pong!")

if __name__ == "__main__":
    bot.run(os.environ["DISCORD_TOKEN"])
```

## Project layout (recommended)

EasyCord works well with a simple “core + plugins” structure:

```
my_bot/
├── easycord/            # EasyCord framework source (vendored)
├── plugins/
│   ├── fun.py
│   └── moderation.py
├── main.py
└── requirements.txt
```

In `main.py`, you typically:

- create `Bot()`
- register middleware (`bot.use(...)`)
- load plugins (`bot.add_plugin(...)`)
- call `bot.run(token)`

## Command syncing behavior

By default, `Bot(auto_sync=True)` syncs the global slash command tree in `setup_hook()`.

- **Global commands** may take up to ~1 hour to appear.
- During development, prefer `guild_id=...` (see below) for instant visibility.

### Development tip: guild-only commands

```python
@bot.slash(description="Dev-only test", guild_id=123456789012345678)
async def test(ctx):
    await ctx.respond("Instant in this guild.")
```

## Logging

`Bot.run()` configures basic logging and then delegates to `discord.Client.run()`. You can configure logging yourself before calling `run()` if you want different formatting/handlers.

