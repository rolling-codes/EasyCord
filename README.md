# EasyCord
![Version](https://img.shields.io/badge/v-5.55.0-blue)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Tests](https://img.shields.io/badge/tests-1300%2B-brightgreen)
[![Discord.py](https://img.shields.io/badge/discord.py-2.7%2B-blueviolet)](https://discordpy.readthedocs.io/)

> **Production-grade Discord bot framework** for building scalable, maintainable bots with clean, type-safe code.
>
> Slash commands, context menus, modal forms, components with dynamic routing, plugins with dependency management, per-guild storage, multi-language i18n, conversation memory, optional AI orchestration, middleware pipeline, lifecycle hooks, and task scheduling—all with **zero boilerplate**.
>
> **Built for scale**: 1300+ tests, atomic database operations, concurrent plugin safety, proper error isolation, and comprehensive type hints. Deploy with confidence.

### Why EasyCord?

- **No boilerplate.** Decorators do the work. Define commands in two lines, not thirty.
- **Type-safe.** Full Pyright support. Catch bugs at dev time, not runtime.
- **Plugin-native.** Modular, testable, reusable. Build plugins in minutes, not hours.
- **Optional AI.** Includes conversation memory and multi-provider LLM orchestration. Use it or ignore it.
- **Tested.** 1300+ tests covering concurrency, crashes, race conditions, and edge cases.
- **Async-first.** Proper lock safety, atomic database operations, isolated error handling. Won't silently corrupt state.

## Documentation

**New here?** Start with [Your First Bot (Day 1)](#your-first-bot-day-1) below, then jump to [Browse all guides →](docs/README.md).

**Guides organized by what you want to do:**

| Core Learning Path | What to read |
|---|---|
| **Installation & first command** | [Getting Started](docs/getting-started.md) |
| **Add commands (slash, buttons, forms)** | [Building Commands](docs/building-commands.md) — slash, groups, buttons, modals, dynamic routing |
| **Control who can run commands** | [Request Lifecycle](docs/request-lifecycle.md) — middleware, error handlers, lifecycle hooks |
| **Split code into plugins** | [Organizing Code](docs/organizing-code.md) — plugins, task scheduling, event bus |
| **Store per-guild data** | [Storage & State](docs/database-guide.md) — databases, concurrency, backends |
| **Test your commands** | [Testing Commands](docs/testing.md) — offline testing without Discord |

| Specialized Topics |  |
|---|---|
| [Interactive UI](docs/context-interactive-ui.md) | Confirm, paginate, choose, prompt, ask_form |
| [Command Sync](docs/command-sync.md) | Preview, diff, and apply Discord registration |
| [AI Features](docs/conversation-memory.md) | Optional: multi-turn memory, provider selection |
| [Built-in Plugins](docs/builtin-plugins.md) | 28 ready-made plugins (levels, economy, tags, moderation, etc.) |
| [Hot-Reload Development](docs/hot-reload-development.md) | Reload code without restarting |
| [Type Checking](docs/type-checking.md) | Pyright configuration |
| [Deprecation Helpers](docs/deprecation.md) | `@deprecated` and `@version_introduced` |
| [Developer Toolkit](docs/developer-toolkit.md) | CLI for scaffolding, inspection, diagnostics |
| [Full Context Reference](docs/context-reference.md) | Complete `Context` API |
| [Examples](examples/) | Working bot code |

---

## Installation

```bash
pip install "https://github.com/rolling-codes/EasyCord/releases/download/v5.55.0/easycord-5.55.0-py3-none-any.whl"
```

Or clone and install locally:

```bash
git clone https://github.com/rolling-codes/EasyCord.git
cd EasyCord
pip install -e ".[dev]"
```

**Requirements:** Python 3.10+. The only runtime dependency is `discord.py>=2.7.1,<3`.

---

## Your First Bot (Day 1)

### 1. Create a new bot project
```bash
easycord new my-bot
cd my-bot
pip install -e ".[dev]"
```

### 2. Write your first command
Open `my_bot/bot.py` and replace the placeholder:

```python
from easycord import Bot, Plugin, slash

class GreetingPlugin(Plugin):
    @slash(description="Greet a user")
    async def greet(self, ctx, user: str):
        """Say hello to someone."""
        await ctx.respond(f"Hello, {user}! 👋")

bot = Bot()
bot.add_plugin(GreetingPlugin())

if __name__ == "__main__":
    bot.run("YOUR_DISCORD_BOT_TOKEN")
```

### 3. Run it
```bash
python -m my_bot.bot
```

Type `/greet alice` in Discord. It works instantly.

### 4. Test it offline (no bot running needed)
```python
# In tests/test_bot.py
from easycord.testing import invoke
from my_bot.bot import bot, GreetingPlugin

async def test_greet():
    plugin = GreetingPlugin()
    ctx = await invoke(bot, "greet alice")
    assert "Hello, alice" in ctx.last_response
```

Run: `pytest tests/test_bot.py`

### What you just did
- ✅ Created a slash command with one decorator
- ✅ Added a typed parameter (`user: str`)
- ✅ Tested it without running Discord at all
- ✅ Have a foundation for 28 built-in plugins (levels, economy, tags, moderation, etc.)

### Next steps

**Pick your path:**

| Path | What to do |
|---|---|
| **Extend with plugins** | See [examples/with-builtin-plugins.py](examples/with-builtin-plugins.py) for a bot that loads default plugins (tags, levels, polls, welcome) + opt-in plugins (moderation, economy, reminders). Then read [Built-in Plugins](docs/builtin-plugins.md). |
| **Build custom commands** | Follow [Building Commands](docs/building-commands.md) to add buttons, modals, groups, autocomplete. |
| **Organize into plugins** | Follow [Organizing Code](docs/organizing-code.md) to split code into reusable plugins. |
| **Add permissions & control** | Follow [Request Lifecycle](docs/request-lifecycle.md) for guards, rate limits, error handlers. |
| **Store persistent data** | Follow [Storage & State](docs/database-guide.md) for per-guild SQLite or in-memory storage. |
| **Test without Discord** | Follow [Testing Commands](docs/testing.md) to test offline. |
| **Add AI features** | Follow [Conversation Memory](docs/conversation-memory.md) for optional LLM integration. |

---

## Advanced: Start a larger project with templates

If you want a pre-configured structure for a specific use case:

```bash
easycord new my-bot --template plugin
cd my-bot
pip install -e ".[dev]"
pytest  # runs example tests
easycord doctor bot:bot  # validates your setup
```

Templates available (choose one based on your use case):

| Template | What it generates |
|---|---|
| `minimal` | Single `bot.py` with one slash command and one command test |
| `plugin` | Plugin-oriented project with a memory database — **the default** |
| `ai` | Plugin scaffold with an AI-provider placeholder command |
| `database` | Plugin scaffold with SQLite app setup and in-memory tests |

Run `easycord new --list-templates` to see all options.

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

## Commands and Interactions

### Slash commands

```python
from easycord import Bot, slash_command

bot = Bot()

@bot.slash(description="Add two numbers")
async def add(ctx, a: int, b: int):
    await ctx.respond(str(a + b))
```

`@slash` and `@slash_command` are identical — use either. Parameters are typed via Python annotations and rendered as Discord option types automatically.

**Decorator options:**

| Option | Type | Effect |
|---|---|---|
| `name` | `str` | Command name; defaults to the function name |
| `description` | `str` | Shown in the Discord UI — required |
| `guild_id` | `int` | Register to one guild (instant); `None` = global (up to 1 hour) |
| `guild_only` | `bool` | Reject DM invocations with an ephemeral message |
| `ephemeral` | `bool` | Force all responses from this command to be ephemeral |
| `permissions` | `list[str]` | `discord.Permissions` attribute names the invoker must hold |
| `cooldown` | `float` | Per-user cooldown in seconds |
| `autocomplete` | `dict` | Live suggestion callbacks keyed to parameter names |
| `choices` | `dict` | Fixed dropdown values keyed to parameter names |

### Command guards

Stack reusable guards with decorators:

```python
from easycord import cooldown, install_type, premium_required, require_permissions, slash_command

@slash_command(description="Clean up messages")
@require_permissions("manage_messages")
@cooldown(rate=2, per=30, bucket="guild")
async def cleanup(ctx, count: int = 10):
    await ctx.send(f"Cleaned {count} messages.", silent=True)

@slash_command(description="Premium-only feature")
@install_type(guild=True, user=True)
@premium_required
async def exclusive(ctx):
    await ctx.respond("Thanks for supporting the bot!", suppress_embeds=True)
```

- `@require_permissions(*perms)` — blocks the command if the invoker lacks any named permission.
- `@cooldown(rate, per, bucket)` — per-user or per-guild rate limit stored in process memory.
- `@install_type(guild, user)` — restricts where a user-installable command appears.
- `@premium_required` — blocks the command unless the invoker has an active Discord premium entitlement.

### Context menus

```python
@bot.user_command(name="View Profile")
async def profile(ctx, member):
    await ctx.respond(f"{member.display_name} joined {member.guild.name}.")

@bot.message_command(name="Quote This")
async def quote(ctx, message):
    await ctx.respond(f'"{message.content}" — {message.author.display_name}')
```

### Buttons, select menus, and modals

```python
from easycord import component, modal

@bot.component("approve_btn")
async def on_approve(ctx):
    await ctx.respond("Approved!", ephemeral=True)

@bot.modal("feedback_form")
async def on_feedback(ctx, message: str):
    await ctx.respond(f"Feedback received: {message}")
```

### Dynamic component routing

Route component interactions using typed URL-style patterns with collision checking:

```python
from easycord import Plugin, component

class TicketPlugin(Plugin):
    @component("ticket:close:{ticket_id:int}")
    async def close_ticket(self, ctx, ticket_id: int):
        await ctx.respond(f"Closing ticket {ticket_id}.", ephemeral=True)

    @component("poll:vote:{poll_id:int}:{choice_id:int}")
    async def record_vote(self, ctx, poll_id: int, choice_id: int):
        await ctx.respond("Vote recorded.", ephemeral=True)

    @component("wizard:{session_id:snowflake}:next", ttl=300)
    async def wizard_next(self, ctx, session_id: int):
        ...
```

Supported route types: `str`, `int`, `snowflake`. Routes with `ttl=` expire without dispatching after their deadline. Routes without `ttl` are persistent and survive restarts.

### Autocomplete

```python
from easycord import Plugin, autocomplete, slash_command

class FruitPlugin(Plugin):
    @autocomplete("fruit", command="pick")
    async def fruit_choices(self, ctx, current: str, options: dict):
        return [name for name in ["apple", "banana", "cherry"] if current.lower() in name]

    @slash_command(description="Pick a fruit")
    async def pick(self, ctx, fruit: str):
        await ctx.respond(fruit)
```

### Option validators

Validate slash command parameters before the handler runs:

```python
from easycord.validators import Duration, URL, Snowflake, Range, Regex, ChoiceSet
```

- `Duration` — parses human-readable durations like `"2h30m"` into seconds.
- `URL` — validates and normalizes a URL string.
- `Snowflake` — validates a Discord snowflake ID.
- `Range` — enforces a numeric min/max range.
- `Regex` — matches input against a pattern.
- `ChoiceSet` — enforces membership in a fixed set of strings.

`ValidationError` is raised on failure. Call `exc.user_message(ctx)` for the localized string.

---

## Plugins

A plugin groups related commands, event handlers, and background tasks into a single reloadable unit with lifecycle hooks.

```python
from easycord import Bot, Plugin, on, slash, task

class GreetPlugin(Plugin):
    async def on_load(self):
        print("GreetPlugin loaded")

    async def on_unload(self):
        print("GreetPlugin unloaded")

    @slash(description="Say hello")
    async def hello(self, ctx):
        await ctx.respond(f"Hello, {ctx.user.display_name}!")

    @on("member_join")
    async def welcome(self, member):
        if channel := member.guild.system_channel:
            await channel.send(f"Welcome, {member.mention}!")

    @task(minutes=30)
    async def periodic_cleanup(self):
        ...  # runs every 30 minutes, starts on load, stops on unload

bot = Bot()
bot.add_plugin(GreetPlugin())
bot.run("YOUR_TOKEN")
```

Lifecycle hooks:
- `on_load()` — runs when the plugin is registered with `bot.add_plugin()`.
- `on_unload()` — runs when the plugin is removed with `bot.remove_plugin()`.
- `on_reload()` — runs after a successful hot-reload (see [hot-reload-development.md](docs/hot-reload-development.md)).
- `on_error(ctx, exc)` — catches unhandled exceptions from any command in the plugin.

### Bundled first-party plugins

Load the starter set with one call:

```python
bot = Bot(load_builtin_plugins=True)   # loads WelcomePlugin, TagsPlugin, PollsPlugin, LevelsPlugin
```

Or load them selectively:

```python
from easycord.plugins import (
    LevelsPlugin,
    ModerationPlugin,
    PollsPlugin,
    StarboardPlugin,
    TagsPlugin,
    WelcomePlugin,
    InviteTrackerPlugin,
    ReactionRolesPlugin,
    MemberLoggingPlugin,
    SuggestionsPlugin,
    OpenClaudePlugin,
    TranslatePlugin,
)

bot.add_plugin(LevelsPlugin(xp_per_message=15, cooldown_seconds=45))
bot.add_plugin(ModerationPlugin())
bot.add_plugin(PollsPlugin())
bot.add_plugin(StarboardPlugin())
bot.add_plugin(TagsPlugin())
bot.add_plugin(WelcomePlugin())
bot.add_plugin(InviteTrackerPlugin())
bot.add_plugin(ReactionRolesPlugin())
bot.add_plugin(MemberLoggingPlugin())
bot.add_plugin(SuggestionsPlugin())
bot.add_plugin(TranslatePlugin())         # /translate with Google Translate, no API key
bot.add_plugin(OpenClaudePlugin(api_key="sk-ant-..."))  # /ask backed by Claude
```

### Hot-reload during development

```python
import os
bot.run(os.environ["DISCORD_TOKEN"], reload=os.environ.get("ENV") == "development")
```

When a plugin file changes on disk, EasyCord calls `importlib.reload()`, swaps the instance, and calls `on_reload()`. Syntax errors keep the old plugin running; the next successful save retries automatically.

---

## Middleware

Middleware intercepts every slash command before it reaches the handler. Each layer receives `ctx` and a `proceed()` coroutine. Call `proceed()` to continue; skip it to block.

```python
bot.use(catch_errors())
bot.use(guild_only())
bot.use(admin_only())
bot.use(rate_limit(limit=5, window=10.0))
bot.use(log_middleware())
```

**Recommended order:** `catch_errors` first (outermost), then access gates, then rate limiting, then logging.

### Built-in middleware

| Factory | Blocks when… |
|---|---|
| `guild_only()` | Command is invoked in a DM |
| `dm_only()` | Command is invoked inside a guild |
| `admin_only(message=None)` | Invoker lacks the `administrator` permission |
| `allowed_roles(*role_ids, message=None)` | Invoker holds none of the given role IDs |
| `has_permission(*perms, message=None)` | Invoker lacks any of the named permissions |
| `channel_only(*channel_ids, message=None)` | Command is invoked outside the specified channels |
| `boost_only(message=None)` | Invoker is not currently boosting the server |
| `rate_limit(limit=5, window=10.0)` | User exceeds `limit` calls within `window` seconds |
| `log_middleware(level, fmt)` | Never — logs every invocation and always proceeds |
| `catch_errors(message=None)` | Never — catches exceptions and sends an ephemeral reply |

### Custom middleware

```python
from easycord.middleware import MiddlewareFn

def require_prefix(prefix: str) -> MiddlewareFn:
    async def handler(ctx, proceed):
        if not ctx.user.name.startswith(prefix):
            await ctx.respond(f"Only users whose name starts with '{prefix}' can use this.", ephemeral=True)
            return
        await proceed()
    return handler

bot.use(require_prefix("dev_"))
```

---

## Error Handling

EasyCord walks a waterfall and stops at the first registered handler:

```
1. @command_error("name")   — per-command handler on the plugin
2. Plugin.on_error()        — plugin-scoped override
3. @bot.on_error            — global bot-level handler
4. Framework fallback       — re-raises for slash commands; logs for tasks and components
```

```python
from easycord import Plugin, slash, command_error

class MathPlugin(Plugin):
    @slash(description="Divide two numbers")
    async def divide(self, ctx, a: int, b: int):
        await ctx.respond(str(a // b))

    @command_error("divide")
    async def divide_error(self, ctx, exc):
        if isinstance(exc, ZeroDivisionError):
            await ctx.respond("Cannot divide by zero.", ephemeral=True)
        else:
            await ctx.respond("Math failed. Try again.", ephemeral=True)

    async def on_error(self, ctx, exc):
        # catches any command in this plugin not handled by @command_error
        await ctx.respond("Something went wrong.", ephemeral=True)

@bot.on_error
async def global_handler(ctx, exc):
    # ctx is None for task-originated errors
    if ctx is not None:
        await ctx.respond("An unexpected error occurred.", ephemeral=True)
```

See [error-handling.md](docs/error-handling.md) for the full guide including common exceptions and testing patterns.

---

## Storage

### Guild-scoped key-value store

```python
from easycord import ServerConfigStore

store = ServerConfigStore()
await store.set(ctx.guild.id, "welcome_channel", channel_id)
value = await store.get(ctx.guild.id, "welcome_channel")
```

### SQLite database

```python
from easycord import Bot, SQLiteDatabase

bot = Bot(database=SQLiteDatabase(path="data/bot.db"))
await bot.db.set(guild_id, "key", {"any": "json_value"})
value = await bot.db.get(guild_id, "key", default=None)
```

### Memory database (for tests and disposable bots)

```python
bot = Bot(db_backend="memory")
# or
from easycord import MemoryDatabase
bot = Bot(database=MemoryDatabase())
# or
EASYCORD_DB_BACKEND=memory python bot.py
```

---

## Config-driven startup

```python
from easycord import BotConfig

cfg = BotConfig.from_env()   # reads DISCORD_TOKEN, DISCORD_GUILD_ID, db_backend, etc.
bot = cfg.build_bot()
bot.run(cfg.token)
```

JSON files use the same field names: `token`, `guild_id`, `db_backend`, `db_path`, `auto_sync`, `log_level`, `extra`. Config precedence: environment → file → explicit keyword overrides.

---

## Localization

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

Locale resolution order: user locale → guild locale → default locale → English. Missing keys fall back gracefully at every step.

**Google Translate auto-translation** (no API key required):

```python
from easycord import make_google_auto_translator

locales = LocalizationManager(auto_translator=make_google_auto_translator())
```

Missing-key lookups are translated on-the-fly and cached. After `bot.use_google_translate()` + `sync_commands()`, Discord shows localized command names per locale — French users see `/traduire`, German users see `/übersetzen` — all routed to the same handler.

**TranslatePlugin** adds a `/translate` slash command backed by Google Translate:

```python
from easycord.plugins import TranslatePlugin

bot.add_plugin(TranslatePlugin())
# Members use: /translate text:"Hello" languages:"English to French"
# or:          /translate text:"Hola"  (auto-detects language, translates to invoker's Discord locale)
```

---

## Testing

Test commands without a live Discord connection:

```python
from easycord.testing import (
    FakeContext,
    FakeContextBuilder,
    invoke,
    invoke_autocomplete,
    invoke_component,
    invoke_message_command,
    invoke_modal,
    invoke_user_command,
)

async def test_ping(bot):
    ctx = await invoke(bot, "ping")
    assert ctx.last_response == "Pong!"

async def test_user_command(bot):
    ctx = await invoke_user_command(bot, "View Profile", target_id=42)
    ctx.assert_contains("profile")

async def test_component(bot):
    ctx = await invoke_component(bot, "ticket:close:7")
    ctx.assert_content("Closing ticket 7.")

async def test_modal(bot):
    ctx = await invoke_modal(bot, "feedback_form", message="Great bot")
    ctx.assert_contains("received")

async def test_autocomplete(bot):
    choices = await invoke_autocomplete(bot, "pick", "fruit", "ap")
    assert "apple" in choices
```

Build a richer context with `FakeContextBuilder`:

```python
ctx = (
    FakeContextBuilder()
    .with_user(42, display_name="Ada")
    .in_guild(100, name="Test Guild")
    .as_admin()
    .with_permissions(manage_messages=True)
    .with_roles(123456789)
    .with_locale("en-US", guild_locale="en-GB")
    .build()
)
```

---

## AI Integration (optional)

EasyCord works without AI. Add AI features as plugins when needed.

### Quick AI assistant

```python
from easycord.plugins import OpenClaudePlugin

bot.add_plugin(OpenClaudePlugin(api_key="sk-ant-..."))
# Members use: /ask "your question"
# Responses are rate-limited per user and truncated to Discord's 2000-character limit.
```

### 9 supported LLM providers

```python
from easycord.plugins import (
    AnthropicProvider,    # Claude (claude-sonnet-4-6 default)
    OpenAIProvider,       # GPT-4o and others
    GeminiProvider,       # Google Gemini
    GroqProvider,         # Groq (fast inference)
    MistralProvider,      # Mistral AI
    HuggingFaceProvider,  # HuggingFace Inference API
    TogetherProvider,     # Together.ai
    OllamaProvider,       # Local Ollama models
    LiteLLMProvider,      # LiteLLM proxy (routes to any backend)
)
```

### Multi-provider orchestration with fallback chains

```python
from easycord import Orchestrator, FallbackStrategy, RunContext

orchestrator = Orchestrator(
    strategy=FallbackStrategy([
        AnthropicProvider(),   # tried first
        GroqProvider(),        # tried if Anthropic fails
        OpenAIProvider(),      # tried if Groq fails
    ]),
    tools=bot.tool_registry,
)

@bot.slash(description="Ask AI with tool access")
async def ask(ctx, prompt: str):
    await ctx.defer()
    result = await orchestrator.run(
        RunContext(
            messages=[{"role": "user", "content": prompt}],
            ctx=ctx,
            max_steps=5,    # max tool calls before returning a final answer
            timeout=30.0,   # seconds per tool call
        )
    )
    await ctx.respond(result.text[:2000])
```

The orchestrator:
- **Selects providers** by trying the best first and falling back if it fails.
- **Detects tool calls** when the AI requests a function.
- **Executes tools** with permission checks, timeouts, and exception handling.
- **Loops** by feeding tool results back to the AI until it returns a final response.
- **Enforces constraints** — admin-only, role-gated, and user-allowlisted tools are checked at each step.

### AI tool registration

Expose bot functions to the AI with `@ai_tool`:

```python
import discord
from easycord import Plugin, ai_tool, ToolSafety
from datetime import timedelta

class ModToolsPlugin(Plugin):
    @ai_tool(description="Check if a user is a member of this server")
    async def is_member(self, ctx, user_id: int) -> str:
        try:
            await ctx.guild.fetch_member(user_id)
            return "User is a member."
        except discord.NotFound:
            return "User is not a member."
        except discord.HTTPException as exc:
            return f"Could not check membership: {exc}"

    @ai_tool(
        description="Timeout a user from the server",
        safety=ToolSafety.CONTROLLED,
        require_admin=True,
    )
    async def timeout_user(self, ctx, user_id: int, seconds: int = 3600) -> str:
        member = await ctx.guild.fetch_member(user_id)
        await member.timeout(timedelta(seconds=seconds))
        return f"Timed out {member.name} for {seconds}s."
```

Safety levels:
- `ToolSafety.SAFE` — read-only operations (queries, lookups, member info).
- `ToolSafety.CONTROLLED` — validated write operations (moderation, role changes, database writes).
- `ToolSafety.RESTRICTED` — never exposed to AI (admin-only or destructive operations).

Each tool optionally requires `require_admin=True`, specific `allowed_roles`, or `allowed_users`.

Audit tools offline before connecting to Discord:

```bash
easycord audit-tools bot:bot
easycord audit-tools bot:bot --fail-on-warnings   # exit 1 in CI if warnings exist
```

---

## Command Sync

Preview what would change before syncing with Discord:

```python
plan = bot.plan_command_sync(remote_commands=["old_ping"])
# plan has: added, changed, removed, unchanged, warnings

plan = await bot.sync_commands(dry_run=True, remote_commands=["old_ping"])
await bot.sync_commands()                                        # live sync
await bot.sync_commands(guild_id=123456789012345678)            # guild sync
await bot.sync_commands(remote_commands=["old_ping"], confirm_removals=True)
```

From the CLI:

```bash
easycord sync-plan bot:bot --remote old_ping
easycord sync-plan bot:bot --remote old_ping --json
```

---

## Inspect Registered Interactions

```python
inventory = bot.inspect_interactions()
# returns: slash, context_menu, component, modal, autocomplete
```

Each entry includes: interaction type, name or route pattern, callback name, source plugin, guild scope, metadata, enabled state, sync state, and registration time.

From the CLI:

```bash
easycord inspect bot:bot
easycord inspect bot:bot --json
```

---

## Built-in Embeds

```python
from easycord import EasyEmbed, EmbedBuilder, EmbedCard
from easycord.embed_cards import InfoEmbed, SuccessEmbed, WarningEmbed, ErrorEmbed

# Quick status embeds
await ctx.respond(embed=EasyEmbed.success("Operation complete!"))
await ctx.respond(embed=EasyEmbed.error("Something went wrong."))
await ctx.respond(embed=EasyEmbed.info("Update available."))
await ctx.respond(embed=EasyEmbed.warning("Double-check this setting."))

# Fluent builder
embed = (
    EmbedBuilder()
    .title("Member Info")
    .description("Details about the member")
    .field("Joined", "2024-01-01")
    .field("Roles", "Moderator, Staff")
    .color(0x5865F2)
    .build()
)

# Card with buttons
card = (
    EmbedCard.from_embed(embed)
    .button("Approve", custom_id="approve", style="success")
    .button("Reject",  custom_id="reject",  style="danger")
)
await ctx.respond(**card.to_kwargs())
```

---

## Pagination

```python
from easycord import Paginator

@bot.slash(description="Show all commands")
async def help(ctx):
    lines = [f"/command{i}" for i in range(1, 37)]
    await Paginator.from_lines(lines, per_page=10, title="Commands").send(ctx)

@bot.slash(description="Browse results")
async def browse(ctx):
    embeds = [page_one, page_two, page_three]
    await Paginator.from_embeds(embeds).send(ctx)
```

---

## Developer Diagnostics

```bash
easycord doctor                        # check Python, discord.py, DISCORD_TOKEN
easycord doctor bot:bot                # also check bot imports and interaction count
easycord doctor bot:bot --json         # stable JSON output for CI

easycord inspect bot:bot               # print all registered interactions
easycord inspect bot:bot --json

easycord sync-plan bot:bot             # preview command sync changes
easycord audit-tools bot:bot           # check AI tool safety classification

easycord test-template my_plugin       # generate a starter test file
easycord test-template my_plugin -o tests/test_my_plugin.py

easycord plugin create my_plugin       # scaffold a new plugin module
easycord plugin check ./my_plugin      # validate manifest, layout, and imports
easycord plugin discover --json        # list installed easycord.plugins entry points
```

---

## Fluent Setup (alternative to manual wiring)

```python
from easycord import FrameworkManager

bot = FrameworkManager.build_bot(
    builtin_plugins=True,
    guild_only=True,
)
bot.run("YOUR_TOKEN")
```

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
- Put each feature in its own `Plugin`.
- Move shared settings into `ServerConfigStore` (no database) or `SQLiteDatabase` (relational).
- Use `db_backend="memory"` in tests so test runs stay offline and produce no local files.

---

## Full Feature Reference

**Commands and interactions:**
- Slash commands with typed parameters, cooldowns, permission guards, and ephemeral forcing.
- Context menu commands for right-click User and right-click Message actions.
- Button and select menu components with static or dynamic typed-route custom IDs.
- Modals with named field extraction.
- Autocomplete callbacks for live suggestions as the user types.
- Option validators: `Duration`, `URL`, `Snowflake`, `Range`, `Regex`, `ChoiceSet`.
- Command sync planner with dry-run mode and explicit removal confirmation.

**Plugins:**
- `Plugin` base class with `on_load`, `on_unload`, `on_reload`, and `on_error` hooks.
- `@slash`, `@on`, `@component`, `@modal`, `@task` decorators inside plugins.
- `SlashGroup` for command namespaces with subcommands.
- `bot.add_plugin()`, `bot.remove_plugin()`, and hot-reload via `reload=True`.
- Plugin authoring helpers: `create_package_plugin`, `check_plugin_project`, `discover_plugins`, `load_entrypoint_plugins`.
- Plugin manifest validation and `easycord.plugins` entry-point discovery.

**Bundled plugins:**
- `WelcomePlugin` — configurable welcome messages on member join.
- `TagsPlugin` — per-guild text snippet store with `/tag get/set/delete/list`.
- `PollsPlugin` — slash-command polls with reaction-based voting.
- `LevelsPlugin` — per-guild XP, leveling, rank names, and role rewards.
- `ModerationPlugin` — kick, ban, unban, timeout, warn, mute, unmute.
- `StarboardPlugin` — archives messages that reach a reaction threshold.
- `InviteTrackerPlugin` — tracks which invite brought each member.
- `ReactionRolesPlugin` — auto-assigns roles on emoji reactions.
- `MemberLoggingPlugin` — logs joins, leaves, nickname changes, and role changes.
- `SuggestionsPlugin` — collects and votes on server suggestions.
- `OpenClaudePlugin` — `/ask` command backed by Anthropic Claude.
- `TranslatePlugin` — `/translate` backed by Google Translate, no API key required.

**Middleware:**
- `guild_only`, `dm_only`, `admin_only`, `allowed_roles`, `has_permission`, `channel_only`, `boost_only`.
- `rate_limit` — per-user sliding-window rate limiter.
- `log_middleware` — logs every invocation to the `easycord` logger.
- `catch_errors` — wraps the chain in a broad except and sends an ephemeral reply.
- Custom middleware: function-factory pattern or stateful class with `__call__`.

**Storage:**
- `ServerConfigStore` — per-guild JSON key-value store with atomic writes.
- `SQLiteDatabase` — persistent relational storage with guild-row sync.
- `MemoryDatabase` — in-process storage for tests and disposable bots.
- `BotConfig` — environment/file-driven startup with config precedence rules.

**Localization:**
- `LocalizationManager` — registers locale files and resolves keys.
- `ctx.t(key, default=...)` — resolves a translation key in the invoker's locale.
- Locale fallback chain: user locale → guild locale → default locale → English.
- `make_google_auto_translator()` — auto-translates missing keys on-the-fly.
- `bot.use_google_translate()` + `sync_commands()` — localizes Discord command names per locale.

**AI and orchestration:**
- 9 `AIProvider` implementations: Anthropic, OpenAI, Gemini, Groq, Mistral, HuggingFace, Together.ai, Ollama, LiteLLM.
- `Orchestrator` — multi-step tool execution loop with provider routing.
- `FallbackStrategy` — tries providers in order, falls back on failure.
- `@ai_tool` — exposes a plugin method to the AI with permission gates and safety classification.
- `ToolSafety.SAFE / CONTROLLED / RESTRICTED` — three-tier safety model.
- `ToolRegistry` — manages registered tools with explicit permission gates.
- `ConversationMemory` — maintains multi-turn context across commands.
- `easycord audit-tools` — offline safety audit before connecting to any provider.

**Developer toolkit:**
- `easycord new` — scaffolds a runnable bot project with one of four templates.
- `easycord doctor` — checks Python version, discord.py, token, and optional bot import.
- `easycord inspect` — prints all registered interactions grouped by type.
- `easycord sync-plan` — diffs local commands against remote names without contacting Discord.
- `easycord audit-tools` — checks tool safety, descriptions, schemas, and permission gates.
- `easycord test-template` — generates a starter test file for a plugin.
- `easycord plugin create/check/discover` — plugin scaffolding and validation.

**Testing:**
- `invoke(bot, "name", **kwargs)` — invokes a slash command offline.
- `invoke_user_command`, `invoke_message_command` — invokes context menus offline.
- `invoke_component(bot, "custom_id")` — invokes a component handler offline.
- `invoke_modal(bot, "custom_id", **fields)` — submits a modal offline.
- `invoke_autocomplete(bot, "cmd", "param", "current")` — fetches autocomplete choices offline.
- `FakeContextBuilder` — fluent builder for richer offline handler contexts.
- `FakeContext.make(is_admin=True)` — quick one-line fake context.
- `ctx.assert_content(str)`, `ctx.assert_contains(str)` — inline response assertions.

**Error handling:**
- `@command_error("name")` — per-command handler on the plugin.
- `Plugin.on_error(ctx, exc)` — plugin-scoped handler for all commands in the plugin.
- `@bot.on_error` — global fallback handler (one allowed; second call overwrites).
- Framework fallback — re-raises for slash commands; logs for tasks and components.

**Type checking:**
- Ships `pyrightconfig.json` pre-configured for `standard` mode.
- `SENDABLE_CHANNEL_TYPES` for narrowing channel sends without type suppression.
- `TYPE_CHECKING` import pattern for cyclic dependency resolution.

---

## Why EasyCord vs. raw discord.py

| Task | Raw `discord.py` | EasyCord |
|---|---|---|
| Slash commands | Build `CommandTree`, sync manually | `@bot.slash(description="...")` |
| Permission checks | Repeat in each command | `@require_permissions(...)` on the decorator |
| Cooldowns | Track timestamps yourself | `@cooldown(rate=2, per=30)` |
| Components | Wire handlers by matching string IDs | `@bot.component("ticket:close:{id:int}")` |
| Middleware | Write custom decorator chains | `bot.use(rate_limit())` |
| Plugins | Custom `Cog` wiring | `Plugin` with lifecycle hooks |
| Per-guild config | Hand-rolled JSON or a database | `ServerConfigStore` or `bot.db` |
| Error handling | Catch and re-raise in each command | `@command_error`, `on_error`, `@bot.on_error` |
| Offline tests | Mock the entire discord.py client | `invoke(bot, "command_name")` |
| AI integration | discord.py + LLM SDK glue code | `Orchestrator` + `ToolRegistry` |
| Tool calling | Manual prompt engineering | `@ai_tool` with safety classification |

---

## License

EasyCord is released under the **MIT License**.

- See `pyproject.toml` for the canonical license metadata.
- Copyright (c) 2026 Rolling Codes.

Release: [v5.55.0](https://github.com/rolling-codes/EasyCord/releases/tag/v5.55.0) · [Changelog](CHANGELOG.md) · [GitHub](https://github.com/rolling-codes/EasyCord)
