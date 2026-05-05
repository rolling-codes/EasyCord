# EasyCord
![Version](https://img.shields.io/badge/v-5.0.0-blue)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Tests](https://img.shields.io/badge/tests-passing-brightgreen)

> A modern Discord bot framework for production bots. **No AI required.** Commands, events, moderation, leveling, per-guild configuration, and optional AI orchestration — all with minimal boilerplate. Start simple with slash commands. Add bundled plugins for features (moderation, roles, logging, leveling). Optionally add intelligent agents with multi-provider LLM support and permission-gated tool calling.

## Start here

1. Install the latest release: `pip install "easycord @ git+https://github.com/rolling-codes/EasyCord.git@v5.0.0"`
2. Create a bot with one slash command.
3. Split features into plugins once the bot grows.

```python
from easycord import Bot

bot = Bot()
bot.load_builtin_plugins()

@bot.slash(description="Ping the bot")
async def ping(ctx):
    await ctx.respond("Pong!")

bot.run("YOUR_TOKEN")
```

**Want to see a production bot without AI?** Open [`examples/core-bot.py`](examples/core-bot.py).

For the shortest path to a working bot, open [`docs/getting-started.md`](docs/getting-started.md).

## New in v5.0.0 (Current Release)

**Bug fixes:**
- Fixed `FallbackStrategy.select()` — the fallback chain was broken: `min(attempt, len-1)` caused it to pin to the last provider instead of advancing through the list. All configured providers are now tried in order.
- Fixed `ctx.is_admin` — was being called as `ctx.is_admin()` (method call) in the tool registry, meaning the permission check always passed because a bound method is truthy. Now correctly reads the `@property`.
- Fixed `ToolLimiter` race condition — `check_limit` and `reset_*` now hold an `asyncio.Lock`, preventing concurrent commands from bypassing rate limits.
- Fixed `asyncio.get_event_loop()` deprecation across all 9 AI provider implementations — replaced with `asyncio.get_running_loop()`.
- Fixed unused `import discord` in `plugins/tags.py`.

**Improvements:**
- `ToolRegistry.can_execute` is now `async` so the rate-limit check is a proper awaited call instead of a sync call on an async method.
- Provider failures in the orchestrator are now logged (`WARNING`) instead of silently swallowed, making debugging provider issues possible.
- `AnthropicProvider` default model updated from `claude-3-5-sonnet-20241022` to `claude-sonnet-4-6`.
- All 9 AI provider classes (`AnthropicProvider`, `OpenAIProvider`, `GeminiProvider`, `GroqProvider`, `MistralProvider`, `HuggingFaceProvider`, `TogetherAIProvider`, `OllamaProvider`, `LiteLLMProvider`) and the `AIProvider` base class are now accessible directly from `easycord` via lazy import (no circular-import issues).
- `easycord.__version__` is now set to `"5.0.0"`.
- Python 3.13 added to supported classifiers.
- Package status promoted from `Beta` to `Production/Stable`.

**Earlier in v4.5.0-beta.3:**
- Platform-grade localization infrastructure: locale auto-detection with intelligent fallback chains (user → guild → system → default), regional fallback (pt-BR → pt → en-US), three diagnostic modes (SILENT/WARN/STRICT), translation completeness validation, optional metrics tracking.

## New in v4.2

### Easy Paginator

Create paginated help/results in one line:

```python
from easycord import Paginator

@bot.slash(description="Show commands")
async def help(ctx):
    lines = [f"/cmd{i}" for i in range(1, 37)]
    await Paginator.from_lines(lines, per_page=10, title="Command List").send(ctx)
```

Or paginate existing embeds:

```python
from easycord import Paginator

embeds = [embed_page_1, embed_page_2, embed_page_3]
await Paginator.from_embeds(embeds).send(ctx)
```

### Smart Embeds

Use status templates for common bot responses:

```python
from easycord import EasyEmbed

await ctx.respond(embed=EasyEmbed.success("Operation complete!"))
await ctx.respond(embed=EasyEmbed.error("Something went wrong."))
await ctx.respond(embed=EasyEmbed.info("Update available."))
await ctx.respond(embed=EasyEmbed.warning("Double-check this setting."))
```

### Faster Bot Bootstrap

Start with a safer default stack in one line:

```python
from easycord import FrameworkManager

bot = (
    FrameworkManager.build_bot(
        builtin_plugins=True,
        guild_only=True,
    )
)
```

## Installation

### From GitHub (via pip)

```bash
pip install "easycord @ git+https://github.com/rolling-codes/EasyCord.git@v5.0.0"
```

### Clone and install locally

```bash
git clone https://github.com/rolling-codes/EasyCord.git
cd EasyCord
pip install .
```

### With dev dependencies

```bash
pip install -e ".[dev]"
```

## Localization (multi-language support)

Build bots that speak your server's language:

```python
# Define translations in a locale file (en.json)
{
  "commands": {
    "ping": {
      "response": "Pong!"
    }
  }
}

# Use in your command
@bot.slash()
async def ping(ctx):
    await ctx.respond(ctx.t("commands.ping.response"))
```

Initialize the bot with localization:

```python
from easycord import Bot, LocalizationManager

locales = LocalizationManager()
locales.register("en", "locales/en.json")
locales.register("es", "locales/es.json")

bot = Bot(localization=locales, default_locale="en")
```

Translations fallback gracefully: user locale → guild locale → default locale → English. See [`docs/localization.md`](docs/localization.md) for the full guide.

## Optional: AI Integration

EasyCord core works great without AI. If you want intelligent agents, add them optionally.

### Simple AI assistant (ask Claude)

```python
from easycord import Bot
from easycord.plugins import OpenClaudePlugin

bot = Bot()
bot.add_plugin(OpenClaudePlugin(api_key="sk-ant-..."))  # or ANTHROPIC_API_KEY env var

bot.run("YOUR_TOKEN")
```

Members use `/ask "your question"` to query Claude API. Responses are automatically truncated to Discord's 2000-char limit, requests are rate limited per user, and the waiting message can be localized with `openclaude.thinking`.

For custom commands, configure a shared provider and call it through context:

```python
from easycord.plugins import OpenAIProvider

bot = Bot(ai_provider=OpenAIProvider(api_key="sk-..."))

@bot.slash(description="Ask AI")
async def ask(ctx, prompt: str):
    response = await ctx.ai(prompt, model="gpt-4o")
    await ctx.respond(response[:2000])
```

**Setup:** Install `anthropic` SDK and set `ANTHROPIC_API_KEY` environment variable.

See [`docs/examples.md`](docs/examples.md) for examples with OpenAI, Gemini, Groq, Ollama, and custom providers.

### Advanced: AI Tool Registration (function calling)

Let AI safely call into your bot via `@ai_tool` decorator:

```python
from easycord import Plugin, ai_tool, ToolSafety
from datetime import timedelta

class ModToolsPlugin(Plugin):
    @ai_tool(description="Check if user is a member of the server")
    async def is_member(self, ctx, user_id: int):
        try:
            await ctx.guild.fetch_member(user_id)
            return "User is a member"
        except:
            return "User is not a member"

    @ai_tool(
        description="Timeout a user from the server",
        safety=ToolSafety.CONTROLLED,
        require_admin=True,
        parameters={
            "type": "object",
            "properties": {
                "user_id": {"type": "integer"},
                "seconds": {"type": "integer"}
            }
        }
    )
    async def timeout_user(self, ctx, user_id: int, seconds: int = 3600):
        member = await ctx.guild.fetch_member(user_id)
        await member.timeout(timedelta(seconds=seconds))
        return f"Timed out {member.name} for {seconds}s"
```

Tools are categorized by safety:
- **SAFE** — read-only (queries, lookups, member info)
- **CONTROLLED** — validated actions (moderation, database writes, role changes)
- **RESTRICTED** — never expose to AI (admin-only, destructive operations)

Each tool can require `require_admin=True`, specific `allowed_roles`, or `allowed_users`.

## AI Orchestration (multi-provider routing & tool calling)

Use the orchestration layer for intelligent provider selection with fallback chains:

```python
from easycord import Bot, Plugin, slash, Orchestrator, FallbackStrategy, RunContext
from easycord.plugins import AnthropicProvider, GroqProvider, OpenAIProvider

bot = Bot()

# Create orchestrator with fallback chain
orchestrator = Orchestrator(
    strategy=FallbackStrategy([
        AnthropicProvider(),  # Try first
        GroqProvider(),       # Fallback
        OpenAIProvider(),     # Last resort
    ]),
    tools=bot.tool_registry,  # Auto-includes @ai_tool methods
)

class AIPlugin(Plugin):
    @slash(description="Ask AI with tool access")
    async def ask_with_tools(self, ctx, prompt: str):
        await ctx.defer()
        response = await orchestrator.run(
            RunContext(
                messages=[{"role": "user", "content": prompt}],
                ctx=ctx,
                max_steps=5,  # Max tool calls before returning
            )
        )
        await ctx.respond(response.text[:2000])

bot.add_plugin(AIPlugin())
bot.run("YOUR_TOKEN")
```

The orchestrator:
- **Routes intelligently:** tries best provider first, falls back if it fails
- **Detects tool calls:** when AI requests a function call
- **Executes safely:** checks permissions, enforces timeouts, handles exceptions
- **Loops:** feeds tool results back to AI, continues until final response
- **Respects constraints:** admin-only, role-gated, and user-allowlisted tools

## Features at a glance

**Bot Framework (complete lifecycle management):**
- Slash commands, context menus, buttons, select menus, modals — all with decorators
- Event handlers (`@on`) for member joins, message updates, reactions, etc.
- Per-guild configuration and persistent storage (SQLite or in-memory)
- Plugins: reusable feature bundles with lifecycle hooks (`on_load`, `on_ready`, `on_unload`)
- 10+ bundled plugins: moderation, reaction roles, leveling, member logging, auto-responder, starboard, invite tracking, welcome, polls, tags
- Rate limiting per-user, per-tool, or per-guild
- Permission checks (built-in or custom via middleware)
- Localization: user/guild/default locale fallback
- Conversation memory for multi-turn context

**Moderation & Server Management (built-in):**
- Manual moderation: kick, ban, unban, timeout, warn, mute/unmute
- AI-powered moderation: message analysis with configurable confidence thresholds
- Member audit logging: track joins, leaves, nickname changes, role changes
- Reaction roles: auto-assign/revoke roles via emoji reactions
- Starboard: archive popular messages
- Invite tracking: see which invite brought each member

**Developer Experience:**
- Minimal boilerplate — decorators handle registration
- Middleware for cross-cutting concerns (logging, auth, rate limits)
- Fluent builder (`Composer`) for declarative bot setup
- Context object with shortcuts for common operations
- Embed helpers with buttons/selects built-in
- Helper libraries for common tasks (EmbedBuilder, ConfigHelpers, ContextHelpers, ToolHelpers, RateLimitHelpers)

**AI & Orchestration:**
- **9 LLM providers:** Anthropic (Claude), OpenAI (GPT), Google (Gemini), Groq, Mistral, HuggingFace, Together.ai, Ollama (local), LiteLLM (proxy)
- **Multi-provider routing:** fallback chain (try Anthropic → Groq → OpenAI if first fails)
- **Tool registration:** expose bot commands and custom functions to AI via `@ai_tool` decorator
- **Permission-gated tools:** SAFE (read-only), CONTROLLED (validated), RESTRICTED (never expose) — each tool can require admin/roles/users
- **Tool execution loop:** AI detects function calls, executes with timeout + exception handling, feeds results back
- **Conversation memory:** maintain context across multi-turn interactions
- **Smart truncation:** responses auto-fit Discord's 2000-char limit

## Localization (multi-language support)

Build bots that speak your server's language:

```python
# Define translations in a locale file (en.json)
{
  "commands": {
    "ping": {
      "response": "Pong!"
    }
  }
}

# Use in your command
@bot.slash()
async def ping(ctx):
    await ctx.respond(ctx.t("commands.ping.response"))
```

Initialize the bot with localization:

```python
from easycord import Bot, LocalizationManager

locales = LocalizationManager()
locales.register("en", "locales/en.json")
locales.register("es", "locales/es.json")

bot = Bot(localization=locales, default_locale="en")
```

Translations fallback gracefully: user locale → guild locale → default locale → English. See [`docs/localization.md`](docs/localization.md) for the full guide.

## Why this exists

Built for the moment a bot stops being a weekend project and becomes production infrastructure.

EasyCord started as a way to eliminate repetitive Discord bot boilerplate. It evolved into something deeper: **a framework that removes architectural decisions you'd otherwise have to make**.

With discord.py, you decide:
- How to structure commands (app_commands, prefixed, cogs?)
- How to handle permissions (decorators, checks, middleware?)
- How to rate limit (custom tracking, cooldowns, both?)
- How to organize features (cogs, blueprints, file layout?)
- How to configure per-guild (JSON files, database, cache?)

With EasyCord, those are answered. One way. Designed for production.

**AI is optional.** You can build fully-featured bots with zero AI dependencies. If you want intelligent agents, the framework has you covered—but you don't need it.

That's worth more than "less code"—it's fewer design questions.

| Task | Raw `discord.py` | This framework |
| --- | --- | --- |
| Slash commands | Build command tree, sync manually | `@bot.slash(...)` |
| Permission checks | Repeat in each command | Declare on decorator |
| Cooldowns | Track timestamps yourself | `cooldown=...` |
| Components | Wire interaction handlers by ID | `@bot.component(...)` |
| Middleware | Write custom decorators | `bot.use(log_middleware())` |
| Plugins | Custom `Cog` wiring | `Plugin` + lifecycle |
| AI integration | Build from discord.py + LLM SDK | `Orchestrator` + `ToolRegistry` |
| Tool calling | Manual prompt engineering | `@ai_tool` + routing |

## Recommended first project layout

```text
my_bot/
├── bot.py
├── plugins/
│   ├── fun.py
│   └── moderation.py
└── pyproject.toml
```

- Keep `bot.py` for startup and wiring.
- Put each feature in its own plugin.
- Move shared config into `ServerConfigStore` when you need it.

## Core pieces

**Commands & Interaction:**
- `Bot` for slash commands, events, components, and plugin loading
- `@slash`, `@on`, `@component`, `@modal`, `@task` decorators
- `SlashGroup` for command namespaces
- `Context` for replies, DMs, embeds, moderation
- `EmbedCard` and themed embed helpers

**Plugins & Configuration:**
- `Plugin` for reusable feature bundles with `on_load()` / `on_unload()`
- `Bot.db` for guild-scoped storage (SQLite or in-memory)
- `ServerConfigStore` for per-guild settings without a database
- `Composer` for fluent declarative setup

**Middleware & Utilities:**
- Middleware for logging, error handling, rate limiting, permission guards
- Built-in: `guild_only`, `admin_only`, `allowed_roles`, `has_permission`, `boost_only`
- `LocalizationManager` for multi-language support

**AI & Orchestration:**
- 9 `AIProvider` implementations (Anthropic, OpenAI, Gemini, Groq, Mistral, HuggingFace, Together, Ollama, LiteLLM)
- `Orchestrator` for provider routing + tool execution loops
- `ToolRegistry` for explicit tool registration with permission gates
- `@ai_tool` decorator for AI-callable functions
- `FallbackStrategy` for multi-provider resilience

## Best beginner path

1. Read [`docs/getting-started.md`](docs/getting-started.md) to make your first bot.
2. Read [`docs/concepts.md`](docs/concepts.md) to understand the pieces.
3. Copy [`examples/basic_bot.py`](examples/basic_bot.py) and make one change.
4. Move a command into a plugin once the file starts feeling crowded.

## Examples and docs

- [`examples/core-bot.py`](examples/core-bot.py): production bot with zero AI dependencies (commands, events, logging, permissions)
- [`examples/basic_bot.py`](examples/basic_bot.py): the smallest practical starter bot
- [`examples/plugin_bot.py`](examples/plugin_bot.py): a feature split across plugins
- [`examples/group_bot.py`](examples/group_bot.py): grouped slash commands with `SlashGroup`
- [`docs/index.md`](docs/index.md): documentation home
- [`docs/getting-started.md`](docs/getting-started.md): 5-minute walkthrough to a working bot
- [`docs/quickstart-production.md`](docs/quickstart-production.md): complete bot from scratch showing plugins, events, AI, error handling (canonical pattern)
- [`docs/api.md`](docs/api.md): complete API reference with examples
- [`docs/examples.md`](docs/examples.md): patterns and snippets
- [`docs/fork-and-expand.md`](docs/fork-and-expand.md): how to grow a real bot project
- [`docs/migration-from-discord.py.md`](docs/migration-from-discord.py.md): side-by-side comparison, "delete after migrating" checklist
- [`docs/security-best-practices.md`](docs/security-best-practices.md): token management, permissions, AI safety pipeline, prompt injection prevention
- [`docs/performance-tuning.md`](docs/performance-tuning.md): optimize latency, memory, throughput
- [`docs/troubleshooting.md`](docs/troubleshooting.md): common issues and solutions
- [`docs/stability-and-scope.md`](docs/stability-and-scope.md): API stability guarantees, intentional gaps, extension surface, upgrade safety
- [`server_commands/__init__.py`](server_commands/__init__.py): one place to load the bundled plugins

## Project backstory

This project started as a way to cut down the repetitive work of Discord bot development for a school server. That original goal still drives the project: make the first command easy, then make the second and third commands feel just as simple.

# License

EasyCord is currently released under the **MIT License**.

- See `pyproject.toml` for the canonical package license metadata (`license = "MIT"`).
- Any future licensing experiments (including dual-license models) are **not part of this release line**.

Copyright (c) 2026 Rolling Codes
