# EasyCord
![Version](https://img.shields.io/badge/v-5.4.0-blue)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Tests](https://img.shields.io/badge/tests-passing-brightgreen)

> A modern Discord bot framework for production bots. **No AI required.** Commands, events, moderation, leveling, per-guild configuration, and optional AI orchestration — all with minimal boilerplate. Start simple with slash commands. Add bundled plugins for features (moderation, roles, logging, leveling). Optionally add intelligent agents with multi-provider LLM support and permission-gated tool calling.

## Start here

1. Install: `pip install easycord`
2. Create: A bot with one slash command.
3. Grow: Split features into plugins.

### Architecture

```text
+----------------+      +-------------------+      +------------------+
|   Discord.py   | <--> |  EasyCord (Bot)   | <--> | InteractionRegistry|
+----------------+      +---------+---------+      +------------------+
                                  |
            +-----------+---------+---------+-----------+
            |           |                   |           |
      +-----+-----+ +---+-------+     +-----+-----+ +---+-------+
      |  Plugins  | | Middleware|     | Localization| | Database  |
      +-----------+ +-----------+     +-------------+ +-----------+
```

### 5 Minute Quickstart

```python
from easycord import Bot

bot = Bot()

@bot.slash(description="Ping the bot")
async def ping(ctx):
    await ctx.respond("Pong!")

bot.run("TOKEN")
```

### Advanced Examples

#### 1. Creating a Plugin
```python
from easycord import Plugin, slash

class Fun(Plugin):
    @slash(description="Greets the user")
    async def greet(self, ctx):
        await ctx.respond(f"Hello {ctx.user.display_name}!")

bot.add_plugin(Fun())
```

#### 2. Components & Modals
```python
from easycord import component, modal

@bot.component("my_button")
async def on_button(ctx):
    await ctx.respond("Button clicked!", ephemeral=True)

@bot.modal("my_modal")
async def on_modal(ctx, name: str):
    await ctx.respond(f"Received: {name}")
```

#### 3. Testing with FakeContext
```python
from easycord.testing import FakeContext

async def test_my_logic():
    ctx = FakeContext.make()
    await my_command(ctx)
    ctx.assert_content("Expected response")
```

For more, see [examples/](examples/) and [docs/](docs/).
Refer to [AGENTS.md](AGENTS.md) for detailed framework conventions.

Release links: [v5.4.0 release](https://github.com/rolling-codes/EasyCord/releases/tag/v5.4.0) · [Changelog](CHANGELOG.md)

## New in v5.4.0 (Current Release)

**Developer experience:**
- Stabilized JSON output contracts for `easycord doctor --json`, `easycord inspect --json`, and `easycord sync-plan --json`.
- Added `easycord new --template minimal|plugin|ai|database`; the default remains the v5.3 plugin scaffold.
- Added actionable `easycord doctor` diagnostics with stable `code`, `severity`, and `fix` fields.
- Added `FakeContextBuilder` for fluent offline command test setup.
- Added offline AI tool safety audits with `easycord audit-tools`, `audit_tool_registry(...)`, and `format_tool_audit(...)`.
- Added `easycord new --list-templates`, `easycord audit-tools --fail-on-warnings`, and role-aware `FakeContextBuilder.with_roles(...)`.

See [`docs/developer-toolkit.md`](docs/developer-toolkit.md).

## Previous: v5.3.0

**Developer toolkit:**
- Added a dependency-free `easycord` CLI with `easycord new`, `easycord inspect`, `easycord sync-plan`, `easycord doctor`, and `easycord test-template`.
- `easycord new <name>` scaffolds a runnable bot project with a plugin, `.env.example`, project metadata, and a starter pytest.
- `easycord doctor [module:bot]` checks the local Python/runtime setup, token configuration, and optional bot imports before you run the bot.
- Added text formatters: `format_interaction_inventory(...)`, `format_sync_plan(...)`, and `format_doctor_report(...)` for CLI output and app diagnostics.
- Added offline testing helpers: `invoke_user_command(...)`, `invoke_message_command(...)`, `invoke_component(...)`, and `invoke_modal(...)`.

See [`docs/developer-toolkit.md`](docs/developer-toolkit.md).

## Previous: v5.2.1

**Interaction architecture:**
- `InteractionRegistry` is now the authoritative EasyCord inventory for slash commands, context menus, components, modals, and autocomplete callbacks while `discord.app_commands.CommandTree` remains the Discord sync backend.
- Added `@slash_command` as a public compatibility alias for `@slash`.
- Added `bot.inspect_interactions()`, `bot.plan_command_sync(...)`, and `bot.sync_commands(..., dry_run=True)` for debugging registrations and previewing sync changes before touching Discord.
- Added dynamic component routes such as `@component("ticket:close:{ticket_id:int}")` with typed variables, TTL metadata, and collision checks.

**Developer debugging & Telemetry:**
- Added a global `/health` command with real-time telemetry: API latency, event loop latency (congestion monitoring), resident memory usage (via `psutil`), and active thread counts.
- Added `@autocomplete("option", command="name")` and `easycord.testing.invoke_autocomplete(...)`.
- Added option validators: `Duration`, `URL`, `Snowflake`, `Range`, `Regex`, and `ChoiceSet`.
- Added task supervision snapshots via `bot.task_statuses()` plus optional task restart/backoff metadata.

See [`docs/interactions.md`](docs/interactions.md), [`docs/command-sync.md`](docs/command-sync.md), and [`docs/components-dynamic-routing.md`](docs/components-dynamic-routing.md).

## Previous: v5.1.2

**Bug fixes:**
- `BotConfig.build_bot()` now honors `db_backend="memory"` and uses `guild_id` for guild-scoped command sync.
- `BotConfig.from_file()` now applies config precedence consistently: environment → file → explicit overrides.
- Added `ctx.send(...)` as a compatibility alias for `ctx.respond(...)` so bundled plugins and discord.py-style code work as expected.
- Fixed user-install command contexts for current `discord.py` versions and completed public exports for `command_error` and `describe`.

**Developer experience:**
- Added `BotConfig` for environment/file-driven startup.
- Added `easycord.testing.FakeContext` and `invoke()` for command tests without Discord.
- Added reusable command guards: `@cooldown`, `@require_permissions`, `@install_type`, and `@premium_required`.
- Added plugin-scoped `Plugin.on_error()` plus context helpers for app context, premium entitlements, forwarding, silent replies, and suppressing embeds.

**Docs & packaging:**
- Source distributions now include docs, examples, context notes, and agent notes.
- Documentation now describes the starter built-in plugin set and explicit plugin loading with `bot.add_plugin(...)`.

## Previous: v5.1.1

**Bug fixes:**
- Fixed `LevelsPlugin._award_xp` cooldown sentinel — default of `0.0` caused the first-message XP award to be silently blocked on freshly-booted CI runners and any host where `time.monotonic()` starts below `cooldown_seconds`. Changed to `float("-inf")` so a user who has never sent a message always passes the cooldown gate.

**CI & infra:**
- Corrected GitHub Actions versions across all three workflows — `actions/checkout@v6` and `actions/setup-python@v6` do not exist and resolved unpredictably. Pinned to `actions/checkout@v4` and `actions/setup-python@v5`.

## Previous: v5.1.0

**Bug fixes:**
- Fixed `LevelsPlugin` role reward assignment — `isinstance(author, discord.Member)` returned `False` on Python 3.11 with specced mocks and in some runtime edge cases; replaced with `hasattr(author, "add_roles")` which is version-agnostic and semantically correct.
- Fixed orchestrator empty-string output — `result.output or result.error` would fall through to the error branch when the AI returned an empty string (a valid response); now uses `result.output if result.output is not None else result.error`.
- Fixed `ToolRegistry` role check crash in DMs — when `allowed_roles` was set but `require_guild=False`, accessing `ctx.member.roles` in a DM context raised `AttributeError`; now safely fetches the member from the guild or returns a permission-denied message.

**New:**
- Added `OpenClawPlugin` — autonomous agent runner that lets the bot execute multi-step AI tasks on a schedule or on demand, with per-guild task history and slash commands (`/openclaw_task`, `/openclaw_stop`).

**CI & infra:**
- Added `test_levels_plugin.py` and `test_openclaw.py` — 411 tests now passing.
- Added `CLAUDE.md`, `AGENTS.md`, and `context/` architecture and conventions docs.

## Previous: v5.0.0

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
- All 9 AI provider classes and the `AIProvider` base class are now accessible directly from `easycord` via lazy import.
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
pip install "https://github.com/rolling-codes/EasyCord/releases/download/v5.4.0/EasyCord-v5.4.0.zip"
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

## Config-driven startup

Use `BotConfig` to load tokens, database settings, logging, and development
guild sync from environment variables or JSON:

```python
from easycord import BotConfig

cfg = BotConfig.from_env()
bot = cfg.build_bot()
bot.run(cfg.token)
```

`DISCORD_GUILD_ID` maps to `guild_id` and makes auto-sync target that one
guild. `db_backend="memory"` stays in-memory; `db_backend="sqlite"` uses
`db_path`.

## Command guards and context helpers

Declare common command policies with decorators:

```python
from easycord import cooldown, install_type, premium_required, require_permissions, slash_command

@slash_command(description="Purge messages")
@require_permissions("manage_messages")
@cooldown(rate=2, per=30, bucket="guild")
async def purge(ctx, count: int = 10):
    await ctx.send(f"Purged {count} messages.", silent=True)

@slash_command(description="Premium report")
@install_type(guild=True, user=True)
@premium_required
async def report(ctx):
    await ctx.respond("Premium report ready.", suppress_embeds=True)
```

Use `ctx.app_context` to inspect where a user-installable command ran,
`ctx.entitlements` for active Discord premium entitlements, `ctx.forward(...)`
to forward a message, and `ctx.send(...)` as an alias for `ctx.respond(...)`.
Built-in command cooldowns are process-local and in-memory; use external
coordination if you need cooldowns shared across shards or multiple bot
processes.

Plugins can override `async def on_error(self, ctx, exc)` for plugin-scoped
error handling. Per-command `@command_error("name")` handlers still run first;
the global `bot.on_error` handler runs only when neither handles the exception.

## Testing commands

Use `easycord.testing` to test commands without a live Discord connection:

```python
from easycord.testing import FakeContext, invoke

async def test_command(bot):
    ctx = await invoke(bot, "ping")
    assert ctx.last_response == "Pong!"

async def test_handler_directly():
    ctx = FakeContext.make(is_admin=True)
    await ctx.respond("ok")
    ctx.assert_content("ok")
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

Translations fallback gracefully: user locale → guild locale → default locale → English.

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

See the AI Orchestration section below for multi-provider examples.

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
- Built-in starter plugins via `load_builtin_plugins()`: welcome, tags, polls, and leveling; load other first-party plugins explicitly with `bot.add_plugin(...)`
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

Translations fallback gracefully: user locale → guild locale → default locale → English.

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

1. Read [`docs/getting-started.md`](docs/getting-started.md) — 5-minute walkthrough to a working bot.
2. Open [`examples/core-bot.py`](examples/core-bot.py) and make one change.
3. Move a command into a `Plugin` once the file starts feeling crowded.

## Examples and docs

- [`examples/core-bot.py`](examples/core-bot.py) — production bot without AI: slash commands, events, plugins, per-guild config
- [`docs/getting-started.md`](docs/getting-started.md) — install, first command, first plugin, localization, AI integration

## Project backstory

This project started as a way to cut down the repetitive work of Discord bot development for a school server. That original goal still drives the project: make the first command easy, then make the second and third commands feel just as simple.

# License

EasyCord is currently released under the **MIT License**.

- See `pyproject.toml` for the canonical package license metadata (`license = "MIT"`).
- Any future licensing experiments (including dual-license models) are **not part of this release line**.

Copyright (c) 2026 Rolling Codes
