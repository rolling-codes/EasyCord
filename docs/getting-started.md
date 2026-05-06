# Getting Started with EasyCord

## Install

```bash
pip install "https://github.com/rolling-codes/EasyCord/releases/download/v5.1.1/EasyCord-v5.1.1.zip"
```

Or clone and install locally:

```bash
git clone https://github.com/rolling-codes/EasyCord.git
cd EasyCord
pip install -e ".[dev]"
```

Python 3.10 or newer is required. The only runtime dependency is `discord.py>=2.0.0`.

---

## Your first bot

```python
from easycord import Bot

bot = Bot()

@bot.slash(description="Ping the bot")
async def ping(ctx):
    await ctx.respond("Pong!")

bot.run("YOUR_TOKEN")
```

Save this as `bot.py` and run it. The slash command `/ping` will appear in Discord automatically.

---

## Adding your first plugin

Split features into plugins as the bot grows. A plugin is a class that groups
related commands and event handlers.

```python
from easycord import Bot, Plugin, slash, on

class GreetPlugin(Plugin):
    @slash(description="Say hello")
    async def hello(self, ctx):
        await ctx.respond(f"Hello, {ctx.user.display_name}!")

    @on("member_join")
    async def on_join(self, member):
        channel = member.guild.system_channel
        if channel:
            await channel.send(f"Welcome, {member.mention}!")

bot = Bot()
bot.add_plugin(GreetPlugin())
bot.run("YOUR_TOKEN")
```

---

## Loading all bundled plugins

EasyCord ships with 10+ bundled plugins (moderation, leveling, welcome, polls,
tags, starboard, and more). Load them all in one call:

```python
from easycord import Bot

bot = Bot(load_builtin_plugins=True)
bot.run("YOUR_TOKEN")
```

Or selectively load the ones you need:

```python
from easycord import Bot
from easycord.plugins import LevelsPlugin, ModerationPlugin, WelcomePlugin

bot = Bot()
bot.add_plugin(LevelsPlugin(xp_per_message=15, cooldown_seconds=45))
bot.add_plugin(ModerationPlugin())
bot.add_plugin(WelcomePlugin())
bot.run("YOUR_TOKEN")
```

---

## Per-guild configuration

Use `ServerConfigStore` to persist per-guild settings without a full database:

```python
from easycord import Bot, Plugin, slash
from easycord import ServerConfigStore

class PrefixPlugin(Plugin):
    def __init__(self):
        self._store = ServerConfigStore()

    @slash(description="Set the welcome channel")
    async def set_welcome(self, ctx, channel_id: str):
        await self._store.set(ctx.guild.id, "welcome_channel", channel_id)
        await ctx.respond(f"Welcome channel set to <#{channel_id}>.")
```

For relational or larger data, use `SQLiteDatabase` (or `MemoryDatabase` in tests):

```python
from easycord import Bot, SQLiteDatabase

bot = Bot(database=SQLiteDatabase(path="data/bot.db"))
```

---

## Localization (multi-language)

```python
from easycord import Bot, LocalizationManager

locales = LocalizationManager()
locales.register("en-US", "locales/en.json")
locales.register("es-ES", "locales/es.json")

bot = Bot(localization=locales, default_locale="en-US")

@bot.slash(description="Ping")
async def ping(ctx):
    await ctx.respond(ctx.t("commands.ping.response", default="Pong!"))
```

EasyCord resolves the locale automatically: user locale → guild locale → default.

---

## AI integration (optional)

EasyCord works fine without AI. If you want an AI assistant command, add
`OpenClaudePlugin` (requires `anthropic` package and `ANTHROPIC_API_KEY`):

```python
import os
from easycord import Bot
from easycord.plugins import OpenClaudePlugin

bot = Bot()
bot.add_plugin(OpenClaudePlugin(api_key=os.environ["ANTHROPIC_API_KEY"]))
bot.run("YOUR_TOKEN")
```

Members use `/ask "your question"`. Responses are rate-limited per user and
automatically truncated to Discord's 2000-character limit.

For other providers (OpenAI, Gemini, Groq, Ollama, etc.) or multi-provider
fallback chains, see the AI Orchestration section of the README.

---

## Fluent builder (alternative setup)

```python
from easycord import FrameworkManager

bot = FrameworkManager.build_bot(
    builtin_plugins=True,
    guild_only=True,
)
bot.run("YOUR_TOKEN")
```

---

## Project layout recommendation

```text
my_bot/
├── bot.py            # startup and wiring
├── plugins/
│   ├── fun.py        # one feature per file
│   └── moderation.py
├── locales/
│   └── en.json
└── pyproject.toml
```

Keep `bot.py` for startup. Put each feature in its own `Plugin`. Move shared
settings into `ServerConfigStore` or `SQLiteDatabase` when you need them.

---

## Next steps

- Browse [`examples/core-bot.py`](../examples/core-bot.py) for a complete bot
  with commands, events, plugins, and per-guild config.
- See the README for the full API reference and AI orchestration docs.
- Check [CHANGELOG.md](../CHANGELOG.md) for what changed in each release.
