# EasyCord
![Version](https://img.shields.io/badge/v-5.61.1-blue)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Tests](https://img.shields.io/badge/tests-1871-brightgreen)
[![Discord.py](https://img.shields.io/badge/discord.py-2.7%2B-blueviolet)](https://discordpy.readthedocs.io/)

> **Production-grade Discord bot framework** for building scalable, maintainable bots with clean, type-safe code.
>
> Slash commands, context menus, modal forms, components with dynamic routing, plugins with versioned config schemas and dependency management, per-guild storage, multi-language i18n, conversation memory, optional AI orchestration, middleware pipeline, lifecycle hooks, and task scheduling—all with **zero boilerplate**.
>
> **30 built-in plugins** including levels, economy, moderation, starboard, polls, translation, AI moderation, and more. **1871 tests**, atomic database operations, concurrent plugin safety, proper error isolation, and comprehensive type hints. Deploy with confidence.

### Why EasyCord?

- **No boilerplate.** Decorators do the work. Define commands in two lines, not thirty.
- **Type-safe.** Full Pyright support. Catch bugs at dev time, not runtime.
- **Plugin-native.** Modular, testable, reusable. Versioned config schemas with automatic migration. Build plugins in minutes, not hours.
- **Optional AI.** Includes conversation memory and multi-provider LLM orchestration (9 providers). Use it or ignore it.
- **Tested.** 1871 tests covering concurrency, crashes, race conditions, and edge cases.
- **Async-first.** Proper lock safety, atomic database operations, isolated error handling. Won't silently corrupt state.

---

## Quick Start

```bash
pip install "https://github.com/rolling-codes/EasyCord/releases/download/v5.61.1/easycord-5.61.1-py3-none-any.whl"
```

Or scaffold a full project:

```bash
easycord new my-bot
cd my-bot && pip install -e ".[dev]"
```

**Requirements:** Python 3.10+. The only runtime dependency is `discord.py>=2.7.1,<3`.

### Your first bot

```python
import os
from easycord import Bot, Plugin, slash, SQLiteDatabase
from easycord.plugins import LevelsPlugin, ModerationPlugin

class MyPlugin(Plugin):
    @slash(description="Server info")
    async def info(self, ctx):
        await ctx.respond(f"{ctx.guild.name} — {ctx.guild.member_count} members")

bot = Bot(database=SQLiteDatabase("bot.db"))
bot.add_plugins(LevelsPlugin(), ModerationPlugin(), MyPlugin())
bot.run(os.environ["DISCORD_TOKEN"])
```

That's `/rank`, `/leaderboard`, `/kick`, `/ban`, `/timeout`, `/warn`, and `/info` — from 10 lines.

### Test it offline

```python
from easycord.testing import invoke

async def test_info():
    ctx = await invoke(bot, "info")
    assert "members" in ctx.last_response
```

No bot token, no Discord connection. See [Testing Commands](docs/testing.md).

---

## Reference Implementations

### Community Bot

A full-featured community server bot: leveling, tags, polls, moderation, economy, and a custom admin dashboard — all from built-in plugins and one custom `Plugin`.

```python
import os, discord
from easycord import Bot, Plugin, slash, SQLiteDatabase
from easycord.plugins import ModerationPlugin, EconomyPlugin, ReminderPlugin, StarboardPlugin

class AdminPlugin(Plugin):
    @slash(description="Show server overview", guild_only=True, require_admin=True)
    async def dashboard(self, ctx):
        guild = ctx.guild
        embed = discord.Embed(title=f"Admin — {guild.name}", color=discord.Color.gold())
        embed.add_field(name="Members", value=str(guild.member_count), inline=True)
        embed.add_field(name="Channels", value=str(len(guild.channels)), inline=True)
        embed.add_field(name="Roles", value=str(len(guild.roles)), inline=True)
        await ctx.respond(embed=embed, ephemeral=True)

bot = Bot(
    load_builtin_plugins=True,       # WelcomePlugin, TagsPlugin, PollsPlugin, LevelsPlugin
    database=SQLiteDatabase("bot.db"),
)
bot.add_plugins(
    AdminPlugin(),
    ModerationPlugin(),
    EconomyPlugin(),
    ReminderPlugin(),
    StarboardPlugin(),
)
bot.run(os.environ["DISCORD_TOKEN"])
```

**What you get:** `/rank`, `/leaderboard`, `/tag`, `/poll`, `/welcome`, `/kick`, `/ban`, `/timeout`, `/warn`, `/balance`, `/daily`, `/transfer`, `/remind`, plus ⭐ starboard pinning and a custom `/dashboard` — all production-ready with persistent SQLite storage.

---

### AI Assistant Bot

Multi-provider AI assistant with tool access. Tries Claude first, falls back to Groq on failure, and exposes a server-info tool the AI can call during reasoning.

```python
import os
from easycord import Bot, Plugin, slash, Orchestrator, FallbackStrategy, RunContext, ai_tool
from easycord.plugins import AnthropicProvider, GroqProvider

class AiPlugin(Plugin):
    def __init__(self):
        super().__init__()

    async def on_load(self):
        self._orchestrator = Orchestrator(
            strategy=FallbackStrategy([AnthropicProvider(), GroqProvider()]),
            tools=self.bot.tool_registry,
        )

    @slash(description="Ask the AI a question")
    async def ask(self, ctx, question: str):
        await ctx.defer()
        result = await self._orchestrator.run(
            RunContext(messages=[{"role": "user", "content": question}], ctx=ctx, max_steps=3)
        )
        await ctx.respond(result.text[:2000])

    @ai_tool(description="Return this server's name and member count")
    async def server_info(self, ctx) -> str:
        return f"{ctx.guild.name} has {ctx.guild.member_count} members."

bot = Bot()
bot.add_plugin(AiPlugin())
bot.run(os.environ["DISCORD_TOKEN"])
```

**What you get:** `/ask` backed by Claude (falls back to Groq automatically), with a tool the AI can call to look up server info. Swap providers in one line — the command never changes. See [AI Features](docs/conversation-memory.md) for conversation memory, tool safety levels, and all 9 providers.

---

### Production Bot — Config Schemas + Middleware

A bot that won't corrupt guild config across schema changes, with rate limiting and error isolation from the start.

```python
import os
from easycord import Bot, Plugin, slash, task, SQLiteDatabase
from easycord.config_schema import ConfigSchema
from easycord.middleware import catch_errors, rate_limit, log_middleware
from easycord.plugins import PluginConfigManager

_DEFAULTS = {"xp_enabled": True, "welcome_channel": None, "mod_log": None}
SCHEMA = ConfigSchema(key="server", version=1, defaults=_DEFAULTS)

@SCHEMA.migration(from_version=0)
def _v0_to_v1(section: dict) -> dict:
    return {**section, "mod_log": None}   # backfill field added in v1

class ServerPlugin(Plugin):
    def __init__(self):
        super().__init__()
        self.config = PluginConfigManager(".easycord/server")

    @slash(description="Toggle XP tracking", guild_only=True, require_admin=True)
    async def set_xp(self, ctx, enabled: bool):
        await self.config.get_schema(ctx.guild.id, SCHEMA)
        await self.config.update(ctx.guild.id, SCHEMA.key, xp_enabled=enabled)
        await ctx.respond(f"XP {'enabled' if enabled else 'disabled'}.", ephemeral=True)

    @task(hours=1)
    async def health_ping(self):
        pass   # runs every hour without blocking the event loop

bot = Bot(database=SQLiteDatabase("bot.db"))
bot.use(catch_errors())
bot.use(rate_limit(limit=5, window=10.0))
bot.use(log_middleware())
bot.add_plugin(ServerPlugin())
bot.run(os.environ["DISCORD_TOKEN"])
```

**What you get:** Per-guild config that survives schema changes — missing keys backfilled, stale keys migrated, all transparently. Heal drifted configs any time with `easycord doctor bot:bot --fix-configs`. Rate limiting and structured error replies out of the box. See [Plugin Config Schemas](docs/config-schema.md) and [Request Lifecycle](docs/request-lifecycle.md).

---

## 30 Built-in Plugins

Load the starter set with one call, or cherry-pick:

```python
bot = Bot(load_builtin_plugins=True)   # loads Welcome, Tags, Polls, Levels
# or
from easycord.plugins import ModerationPlugin, EconomyPlugin, TicketsPlugin
bot.add_plugins(ModerationPlugin(), EconomyPlugin(), TicketsPlugin())
```

| Plugin | Key Commands | Description |
|---|---|---|
| `LevelsPlugin` | `/rank`, `/leaderboard`, `/set_xp_multiplier` | XP, leveling, role rewards, leaderboard caching |
| `ModerationPlugin` | `/kick`, `/ban`, `/unban`, `/timeout`, `/warn` | Member moderation with reason logging |
| `EconomyPlugin` | `/balance`, `/daily`, `/transfer` | Virtual currency with per-guild balances |
| `TagsPlugin` | `/tag get/set/delete/list` | Per-guild text snippets |
| `PollsPlugin` | `/poll` | Reaction-based emoji polls |
| `WelcomePlugin` | `/welcome` | Configurable join messages |
| `StarboardPlugin` | _(reaction-based)_ | Pins messages reaching a ⭐ threshold |
| `TicketsPlugin` | `/ticket_open`, `/ticket_close` | Private support ticket channels |
| `SuggestionsPlugin` | `/suggest` | Community suggestions with voting |
| `GiveawayPlugin` | `/giveaway`, `/giveaway_end`, `/giveaway_reroll` | Timed giveaways with role requirements |
| `ReminderPlugin` | `/remind me in X do Y` | User-scheduled reminders |
| `BirthdayPlugin` | `/birthday_set`, `/birthday_unset`, `/birthday_list` | Per-guild birthday tracking and announcements |
| `ReputationPlugin` | `/rep`, `/rep_check`, `/rep_top` | Member reputation system |
| `TranslatePlugin` | `/translate` | Google Translate, no API key required |
| `VerificationPlugin` | `/verify` | CAPTCHA-style member gate |
| `WordFilterPlugin` | `/filter_add`, `/filter_remove`, `/filter_list` | Auto-delete messages matching patterns |
| `AutoResponderPlugin` | _(event-based)_ | Keyword-triggered auto-replies |
| `AutoRolePlugin` | `/autorole_add`, `/autorole_remove`, `/autorole_list` | Assign roles automatically on join |
| `ReactionRolesPlugin` | _(reaction-based)_ | Role assignment via emoji reactions |
| `ScheduledAnnouncementsPlugin` | `/announcement_add`, `/announcement_list`, `/announcement_remove` | Recurring channel announcements |
| `ServerStatsPlugin` | _(dynamic channels)_ | Live member/channel count display channels |
| `MemberLoggingPlugin` | _(event-based)_ | Logs joins, leaves, nickname and role changes |
| `InviteTrackerPlugin` | _(event-based)_ | Tracks which invite brought each member |
| `RolePersistencePlugin` | _(event-based)_ | Restores roles when members rejoin |
| `AIModeratorPlugin` | _(event-based)_ | AI-powered content moderation |
| `SecurityLabPlugin` | `/lab_report`, `/lab_flood_check`, `/lab_redos` | Audit guild permissions and security posture |
| `ServerSetupPlugin` | `/setup-server` | Preview and apply channel/role presets from four server templates |
| `AIPlugin` | `/ask` | Base conversational AI plugin — powers any configured provider |
| `OpenClaudePlugin` | `/ask` | Backwards-compatible subclass of `AIPlugin` for Anthropic Claude |
| `OpenClawPlugin` | `/claw` | Lightweight Claude assistant variant |

Full documentation: [docs/builtin-plugins.md](docs/builtin-plugins.md)

---

## Architecture

```
+----------------+      +-------------------+      +----------------------+
|   Discord.py   | <--> |  EasyCord (Bot)   | <--> | InteractionRegistry  |
+----------------+      +---------+---------+      +----------------------+
                                  |
          +-----------+-----------+-----------+-----------+
          |           |           |           |           |
    +-----+-----+ +---+-------+ +-+--------+ +-+-------+ +-----------+
    |  Plugins  | | Middleware| | Database | |  i18n   | | AI Layer  |
    +-----------+ +-----------+ +----------+ +---------+ +-----------+
```

`InteractionRegistry` is the authoritative EasyCord inventory. `discord.app_commands.CommandTree` remains the Discord sync backend.

---

## Recommended Project Layout

```text
my_bot/
├── bot.py              # startup, BotConfig, plugin registration
├── plugins/
│   ├── __init__.py
│   ├── fun.py          # one Plugin subclass per file
│   └── moderation.py
├── locales/
│   ├── en-US.json
│   └── es-ES.json
├── tests/
│   └── test_commands.py
└── pyproject.toml
```

- Keep `bot.py` for startup and wiring only.
- Put each feature in its own `Plugin` — reloadable, testable, isolated.
- Use `db_backend="memory"` in tests so runs stay offline and produce no local files.

---

## Why EasyCord vs. raw discord.py

| What you need | Raw `discord.py` | EasyCord |
|---|---|---|
| Slash command with typed args | `CommandTree` + manual sync | `@slash(description="...")` — sync handled |
| Component routing | Match string IDs manually per handler | `@component("ticket:close:{id:int}")` — typed |
| Reusable feature module | `Cog` with manual setup/teardown | `Plugin` with `on_load`, `on_unload`, `on_reload` |
| Per-guild settings | Hand-rolled storage + migration code | `ServerConfigStore` + `ConfigSchema` migrations |
| Request control | Decorator chains on every command | `bot.use(catch_errors(), rate_limit(), guild_only())` |
| Error waterfall | Re-raise or duplicate handlers | `@command_error` → `Plugin.on_error` → `@bot.on_error` |
| Offline testing | Mock the entire discord.py client | `ctx = await invoke(bot, "kick")` |
| AI tool calling | LLM SDK + prompt engineering + glue | `@ai_tool` + `Orchestrator` + safety levels |
| Day-one feature set | Zero plugins, all from scratch | 30 built-in plugins, `load_builtin_plugins=True` |

---

## License

EasyCord is released under the **MIT License**.

See `pyproject.toml` for the canonical license metadata.  
Copyright (c) 2026 Rolling Codes.

**Docs:** [Getting Started](docs/getting-started.md) · [Built-in Plugins](docs/builtin-plugins.md) · [AI Features](docs/conversation-memory.md) · [All guides →](docs/README.md)

Release: [v5.61.1](https://github.com/rolling-codes/EasyCord/releases/tag/v5.61.1) · [Changelog](CHANGELOG.md) · [GitHub](https://github.com/rolling-codes/EasyCord)
