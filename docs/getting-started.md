# Getting Started with EasyCord

## Install

```bash
pip install "https://github.com/rolling-codes/EasyCord/releases/download/v5.4.0/EasyCord-v5.4.0.zip"
```

Or clone and install locally:

```bash
git clone https://github.com/rolling-codes/EasyCord.git
cd EasyCord
pip install -e ".[dev]"
```

Python 3.10 or newer is required. The only runtime dependency is `discord.py>=2.4.0`.

---

## Start a project with the CLI

EasyCord includes a dependency-free developer toolkit:

```bash
easycord new my-bot --template plugin
cd my-bot
pip install -e ".[dev]"
pytest
easycord doctor bot:bot
easycord audit-tools bot:bot
```

The generated project includes a runnable `bot.py`, one example plugin, an
`.env.example`, and a starter command test.

`easycord doctor [module:bot]` checks Python support, `discord.py`,
`DISCORD_TOKEN`, and optional bot imports before you connect to Discord. Use
`--template minimal`, `--template ai`, or `--template database` for alternate
starter projects.

`easycord audit-tools [module:bot]` inspects registered AI tools offline and
reports safety warnings before any provider or Discord connection is used.
`easycord new --list-templates` prints the available scaffold options.

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

## Config-driven startup

Use `BotConfig` when you want environment variables or a JSON file to define
startup settings:

```python
from easycord import BotConfig

cfg = BotConfig.from_env()
bot = cfg.build_bot()
bot.run(cfg.token)
```

`DISCORD_GUILD_ID` is used as a development sync target, so commands sync to
that guild instead of globally. JSON files use the same field names:
`token`, `guild_id`, `db_backend`, `db_path`, `auto_sync`, `log_level`, and
`extra`.

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

## Loading bundled plugins

EasyCord ships multiple first-party plugins in `easycord.plugins`.
Setting `load_builtin_plugins=True` loads the starter set: welcome, tags,
polls, and leveling.

```python
from easycord import Bot

bot = Bot(load_builtin_plugins=True)
bot.run("YOUR_TOKEN")
```

Or selectively load the ones you need:

```python
from easycord import Bot
from easycord.plugins import LevelsPlugin, PollsPlugin, TagsPlugin, WelcomePlugin

bot = Bot()
bot.add_plugin(LevelsPlugin(xp_per_message=15, cooldown_seconds=45))
bot.add_plugin(PollsPlugin())
bot.add_plugin(TagsPlugin())
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

## Command guards and responses

Stack reusable guards with `@slash`:

```python
from easycord import cooldown, premium_required, require_permissions, slash

@slash(description="Clean up messages")
@require_permissions("manage_messages")
@cooldown(rate=2, per=30, bucket="guild")
async def cleanup(ctx, count: int = 10):
    await ctx.send(f"Cleaned {count} messages.", silent=True)

@slash(description="Premium feature")
@premium_required
async def exclusive(ctx):
    await ctx.respond("Thanks for supporting the bot!", suppress_embeds=True)
```

Use `@install_type(guild=True, user=True)` for Discord user-installable
commands. Inside handlers, `ctx.app_context` exposes the Discord app command
context and `ctx.entitlements` exposes active premium entitlements.

Plugins can override `async def on_error(self, ctx, exc)` for plugin-scoped
error handling after optional per-command handlers decorated with
`@command_error("command_name")` and before the global `bot.on_error` handler.

---

## Testing commands

`easycord.testing` lets you test command handlers without connecting to Discord:

```python
from easycord.testing import (
    FakeContext,
    FakeContextBuilder,
    invoke,
    invoke_component,
    invoke_message_command,
    invoke_modal,
    invoke_user_command,
)

async def test_ping(bot):
    ctx = await invoke(bot, "ping")
    assert ctx.last_response == "Pong!"

async def test_handler_directly():
    ctx = FakeContext.make(is_admin=True)
    await ctx.respond("ok")
    ctx.assert_content("ok")
```

Context menu, component, and modal handlers can be tested without Discord too:

```python
ctx = await invoke_user_command(bot, "Profile", target_id=42)
ctx = await invoke_message_command(bot, "Quote", content="Ship it")
ctx = await invoke_component(bot, "ticket:close:42")
ctx = await invoke_modal(bot, "feedback", message="Great bot")
```

For direct handler tests with richer setup, use the fluent builder:

```python
ctx = (
    FakeContextBuilder()
    .with_user(42, display_name="Ada")
    .in_guild(100)
    .with_permissions(manage_messages=True)
    .with_roles(123456789)
    .build()
)
```

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
