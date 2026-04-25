# EasyCord: Unified Bot Framework

EasyCord is a **unified Discord bot framework** — not just an interaction handler or command wrapper. It provides a complete system for building production bots with moderation, logging, configuration, events, and AI orchestration built-in.

## Framework Philosophy

A Discord bot isn't just slash commands. It's:
- **Commands & interactions** — handle user input
- **Events** — respond to members joining, messages being posted, reactions changing
- **State & config** — store per-guild settings, track user data, persist across restarts
- **Middleware** — enforce permissions, rate limits, error handling
- **Features** — moderation, logging, welcome messages, role assignment, leveling
- **AI** — intelligent agents that leverage the above via tool calling

EasyCord unifies all these concerns into a single framework. Start simple. Add plugins as you grow. Scale to AI agents that can safely call your bot functions.

## Core Architecture

### Bot (lifecycle & wiring)

The `Bot` class manages:
- Slash command registration (global or guild-specific)
- Event listeners (`@on`)
- Component handlers (buttons, selects, modals)
- Plugin loading and lifecycle
- Middleware stack
- Tool registry for AI

```python
from easycord import Bot

bot = Bot()

# Add plugins
bot.add_plugin(ModerationPlugin())
bot.add_plugin(ReactionRolesPlugin())

# Register commands/events/middleware
@bot.slash(description="Check your level")
async def rank(ctx):
    # ...

@bot.on("member_join")
async def welcome_member(member):
    # ...

bot.use(log_middleware())
bot.run("TOKEN")
```

### Plugins (reusable features)

Plugins are self-contained feature bundles with:
- Lifecycle hooks: `on_load()` (when added), `on_ready()` (bot ready), `on_unload()` (removed)
- Commands, events, middleware — all scoped to the plugin
- Per-guild configuration (via `ServerConfigStore` or `PluginConfigManager`)
- No global state — plugins are isolated

```python
from easycord import Plugin, on, slash

class MyFeaturePlugin(Plugin):
    def __init__(self):
        super().__init__()
        self.config = PluginConfigManager(".easycord/my-feature")
    
    async def on_load(self):
        # Initialize (e.g., connect to database, start background tasks)
        pass
    
    async def on_ready(self):
        # Called when bot becomes ready (and again after reconnects)
        # Use for periodic tasks, validation
        pass
    
    @slash(description="Do something")
    async def my_command(self, ctx):
        cfg = await self.config.get(ctx.guild.id, "my-feature", defaults={...})
        # ...
    
    @on("message")
    async def on_message(self, message):
        if message.author.bot:
            return
        # ...
    
    async def on_unload(self):
        # Cleanup (e.g., close connections, cancel tasks)
        pass
```

### Context (shortcuts for common operations)

The `Context` object (passed to all commands) provides shortcuts for responses, moderation, configuration, and UI:

```python
@bot.slash()
async def example(ctx):
    # Respond with embed
    await ctx.respond("Hello!", ephemeral=True)
    
    # Moderation
    await ctx.kick(user, reason="...")
    await ctx.ban(user, delete_days=7)
    
    # Localization
    msg = ctx.t("key.path", default="Fallback")
    
    # Defer for long operations
    await ctx.defer()
    # ... do work ...
    await ctx.respond("Done")
    
    # Interactive UI
    choice = await ctx.choose(["Option A", "Option B"], "Pick one:")
```

### Bundled Plugins (production-ready)

EasyCord ships with 10+ plugins ready to use:

| Plugin | Purpose |
|--------|---------|
| `ModerationPlugin` | Kick, ban, timeout, warn, mute (manual) |
| `AIModeratorPlugin` | LLM-powered message analysis for spam/abuse |
| `ReactionRolesPlugin` | Auto-assign roles via emoji reactions |
| `MemberLoggingPlugin` | Audit trail: joins, leaves, nickname/role changes |
| `AutoResponderPlugin` | Trigger responses on keywords or regex patterns |
| `StarboardPlugin` | Archive popular messages to a channel |
| `InviteTrackerPlugin` | Track which invite code brought each member |
| `WelcomePlugin` | Send welcome messages to new members |
| `PollsPlugin` | Create polls with emoji voting |
| `TagsPlugin` | Store and retrieve snippets/canned responses |
| `LevelsPlugin` | XP system with leveling and rank roles |

Load all at once:
```python
bot.load_builtin_plugins()
```

Or add specific ones:
```python
bot.add_plugin(ModerationPlugin())
bot.add_plugin(ReactionRolesPlugin())
```

### Configuration (per-guild)

Each guild has its own isolated configuration. Store settings without needing a database:

```python
from easycord.plugins import PluginConfigManager

config = PluginConfigManager(".easycord/my-plugin")

# Get config (auto-creates defaults if missing)
cfg = await config.get(guild_id, "my-plugin", defaults={
    "enabled": True,
    "threshold": 3,
})

# Atomically update
await config.update(guild_id, "my-plugin", threshold=5)
```

Each guild's config is stored in a JSON file and protected by per-guild locks, so concurrent updates are safe.

### Middleware (cross-cutting concerns)

Middleware runs before every command, handling permission checks, logging, rate limits:

```python
from easycord.middleware import admin_only, guild_only, cooldown

@bot.slash(description="Admin command")
@admin_only()
@cooldown(1)  # 1 per user per second
async def admin_action(ctx):
    # ...
```

Or use middleware globally:

```python
bot.use(log_middleware())
bot.use(error_handler())
bot.use(rate_limit_middleware(10, 60))  # 10 calls per user per 60 seconds
```

### Tool Registry (for AI agents)

Expose commands and functions to AI for safe tool calling:

```python
from easycord import Plugin, ai_tool, ToolSafety

class AIToolsPlugin(Plugin):
    @ai_tool(
        description="Check if a user is in the server",
        safety=ToolSafety.SAFE,  # Read-only
    )
    async def check_member(self, ctx, user_id: int):
        try:
            await ctx.guild.fetch_member(user_id)
            return "Member found"
        except:
            return "Not a member"
    
    @ai_tool(
        description="Timeout a disruptive user",
        safety=ToolSafety.CONTROLLED,  # Validated action
        require_admin=True,
    )
    async def timeout_user(self, ctx, user_id: int, minutes: int = 10):
        member = await ctx.guild.fetch_member(user_id)
        await member.timeout(timedelta(minutes=minutes))
        return f"Timed out {member.name}"
```

Safety levels:
- **SAFE** — read-only (queries, lookups, member info)
- **CONTROLLED** — validated (moderation, database writes)
- **RESTRICTED** — never expose to AI (admin-only, destructive)

## Example: Building a Complete Bot

```python
from easycord import Bot, Orchestrator, FallbackStrategy
from easycord.plugins import (
    ModerationPlugin,
    AIModeratorPlugin,
    ReactionRolesPlugin,
    MemberLoggingPlugin,
    AutoResponderPlugin,
    StarboardPlugin,
    InviteTrackerPlugin,
)
from easycord.plugins._ai_providers import AnthropicProvider, GroqProvider

# Create bot
bot = Bot(default_prefix="!", auto_sync=True)

# Setup AI (optional)
orchestrator = Orchestrator(
    strategy=FallbackStrategy([
        AnthropicProvider(),  # Try Claude first
        GroqProvider(),       # Fallback to Groq
    ]),
    tools=bot.tool_registry,
)

# Add moderation plugins
bot.add_plugin(ModerationPlugin())
bot.add_plugin(AIModeratorPlugin(orchestrator=orchestrator))
bot.add_plugin(MemberLoggingPlugin())

# Add community features
bot.add_plugin(ReactionRolesPlugin())
bot.add_plugin(AutoResponderPlugin())
bot.add_plugin(StarboardPlugin())

# Add growth tracking
bot.add_plugin(InviteTrackerPlugin())

# Add basic commands
@bot.slash(description="Server stats")
async def stats(ctx):
    embed = await ctx.guild.fetch_widget()
    await ctx.respond(embed=embed)

@bot.on("member_join")
async def welcome(member):
    welcome_channel = member.guild.system_channel
    if welcome_channel:
        await welcome_channel.send(f"Welcome {member.mention}!")

# Run
bot.run("YOUR_TOKEN")
```

One bot file. 10+ features. Scalable to AI agents. That's the unified framework.

## How Plugins Interact

Plugins don't know about each other — they're isolated. But they work together:

1. **ModerationPlugin** logs actions (kicks, bans, timeouts)
2. **MemberLoggingPlugin** is independent — logs all member changes
3. **AIModeratorPlugin** can call ModerationPlugin's functions via tool calling
4. **ReactionRolesPlugin** auto-assigns roles without knowing about moderation

Each plugin:
- Has its own config (per-guild)
- Registers its own commands/events
- Exposes functions via `@ai_tool` if desired
- Can't break other plugins

This design scales. 2 plugins. 10 plugins. 100 plugins. No conflicts.

## Extending the Framework

### Custom plugins

```python
from easycord import Plugin, slash, on

class YourPlugin(Plugin):
    async def on_load(self):
        print("Loaded!")
    
    @slash(description="Your command")
    async def your_command(self, ctx):
        pass
    
    @on("member_join")
    async def on_join(self, member):
        pass

bot.add_plugin(YourPlugin())
```

### Custom middleware

```python
from easycord.middleware import MiddlewareFn

async def custom_middleware(ctx, proceed):
    # Before command
    print(f"Running {ctx.command_name}")
    await proceed()
    # After command
    print(f"Done {ctx.command_name}")

bot.use(custom_middleware)
```

### Custom providers (for AI)

```python
from easycord.plugins._ai_providers import AIProvider

class MyProvider(AIProvider):
    def _init_client(self):
        # Setup your LLM client
        pass
    
    async def query(self, prompt: str) -> str:
        # Call your LLM, return response
        pass

orchestrator = Orchestrator(
    strategy=FallbackStrategy([MyProvider()]),
    tools=bot.tool_registry,
)
```

## When to Use EasyCord

**Use EasyCord if you're building:**
- Moderation/community bots
- Bots with multiple features (commands, events, configuration)
- Bots that grow over time and need plugin architecture
- AI-powered agents with safe tool calling
- Bots that need multi-language support
- Bots with per-guild configuration

**EasyCord might be overkill if you're building:**
- A single-command webhook bot
- A bot that only responds to prefixed messages (no slash commands)
- A stateless bot with no configuration

## Next Steps

1. Read [`docs/getting-started.md`](getting-started.md) for a 5-minute walkthrough
2. Copy [`examples/full_featured_bot.py`](../examples/full_featured_bot.py) and customize
3. Split features into plugins as your bot grows
4. Use `@ai_tool` to expose functions to AI agents
5. Browse [`easycord/plugins/`](../easycord/plugins/) for plugin examples

Welcome to the unified bot framework.
