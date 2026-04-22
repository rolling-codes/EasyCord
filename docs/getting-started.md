# Getting started

This guide is the shortest path from "I installed EasyCord" to "I have a bot that responds to a command."

## 1) Create a Discord application

1. Open the [Discord Developer Portal](https://discord.com/developers/applications).
2. Create a new application.
3. Under **Bot**, copy the token and enable any intents you need.
   - For `member_join` or member lookup features, enable **Server Members Intent**.
4. Under **OAuth2 → URL Generator**, select the `bot` and `applications.commands` scopes.
5. Invite the bot to a test server.

## 2) Install EasyCord

```bash
git clone https://github.com/rolling-codes/EasyCord.git
cd EasyCord
pip install -e .
```

If you want the development dependencies too:

```bash
pip install -e ".[dev]"
```

## 3) Make the first bot

Create `bot.py`:

```python
import os
from easycord import Bot

bot = Bot()

@bot.slash(description="Ping the bot")
async def ping(ctx):
    await ctx.respond("Pong!")

bot.run(os.environ["DISCORD_TOKEN"])
```

Run it with:

```bash
DISCORD_TOKEN=your_token_here python bot.py
```

## 4) Use a small project layout

Once the bot starts growing, move feature code out of the main file.

```text
my_bot/
├── bot.py
├── plugins/
│   ├── fun.py
│   └── moderation.py
└── pyproject.toml
```

A simple rule helps beginners stay organized:

- `bot.py` starts the bot and loads plugins.
- Each plugin owns one feature area.
- Shared settings live in `ServerConfigStore`.

## 5) Add one plugin

```python
from easycord import Plugin, slash

class FunPlugin(Plugin):
    @slash(description="Roll a die")
    async def roll(self, ctx, sides: int = 6):
        import random
        await ctx.respond(str(random.randint(1, sides)))
```

Then load it from `bot.py`:

```python
from easycord import Bot
from plugins.fun import FunPlugin

bot = Bot()
bot.add_plugin(FunPlugin())
bot.run(os.environ["DISCORD_TOKEN"])
```

## 6) Development tips

- Use `guild_id=YOUR_SERVER_ID` while testing so commands appear immediately.
- Keep the token in an environment variable instead of hardcoding it.
- Start with one command, then add middleware, then add plugins.
- If the bot file feels crowded, split the next feature into its own plugin.

## 7) When to read the rest

- Read [`concepts.md`](concepts.md) when you want to understand how the framework works.
- Read [`api.md`](api.md) when you need exact method signatures.
- Read [`fork-and-expand.md`](fork-and-expand.md) when the project becomes more than a single starter file.
