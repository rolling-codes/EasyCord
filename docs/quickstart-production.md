# Production Bot Quickstart

Build a complete, deployable Discord bot from scratch in one file. This guide shows the canonical EasyCord pattern end-to-end.

## The goal

A bot that:
- Responds to slash commands
- Logs member joins/leaves
- Moderates with AI (detect spam/abuse)
- Persists per-guild settings
- Handles errors gracefully
- Scales with plugins

**Result:** 150 lines of code. All production-ready.

## Step 1: Environment

```bash
# Create project
mkdir my_bot && cd my_bot

# Virtual environment
python3 -m venv venv
source venv/bin/activate  # macOS/Linux
# OR
venv\Scripts\activate  # Windows

# Install dependencies
pip install "easycord @ git+https://github.com/rolling-codes/EasyCord.git@v4.3.1"
pip install python-dotenv anthropic

# Create .env
echo "DISCORD_TOKEN=your_token_here" > .env
echo "ANTHROPIC_API_KEY=your_key_here" >> .env
echo ".env" >> .gitignore
```

## Step 2: Core bot file

Create `bot.py`:

```python
import os
import logging
from datetime import timedelta

import discord
from dotenv import load_dotenv

from easycord import Bot, Composer, Plugin, slash, on, ServerConfigStore
from easycord.plugins import ModerationPlugin, AIModeratorPlugin, MemberLoggingPlugin
from easycord.plugins._ai_providers import AnthropicProvider
from easycord.orchestrator import Orchestrator, FallbackStrategy

# Setup
load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================================
# 1. PLUGINS — Reusable features with lifecycle management
# ============================================================================

class CustomPlugin(Plugin):
    """Your bot-specific commands and logic."""
    
    def __init__(self):
        super().__init__()
        self.config = ServerConfigStore(".easycord/config")
    
    async def on_load(self):
        logger.info("CustomPlugin loaded")
    
    @slash(description="Check your server rank")
    async def rank(self, ctx):
        # Get member's level from config
        cfg = await self.config.load(ctx.guild_id)
        level = cfg.get_other("user_level", {}).get(str(ctx.user.id), 0)
        await ctx.respond(f"You are level {level}")
    
    @slash(description="Get server info")
    async def server_info(self, ctx):
        await ctx.defer()
        member_count = len(ctx.guild.members)
        await ctx.respond(
            f"**{ctx.guild.name}**\n"
            f"Members: {member_count}\n"
            f"Owner: {ctx.guild.owner.mention if ctx.guild.owner else 'Unknown'}"
        )
    
    @on("member_join")
    async def on_member_join(self, member):
        # Send welcome message
        welcome_channel = member.guild.system_channel
        if welcome_channel:
            try:
                await welcome_channel.send(
                    f"Welcome {member.mention}! 👋\n"
                    f"Account created: <t:{int(member.created_at.timestamp())}:R>"
                )
            except discord.Forbidden:
                logger.warning(f"Can't send to {welcome_channel.name}")

# ============================================================================
# 2. BOT SETUP — Compose intents, middleware, plugins
# ============================================================================

orchestrator = Orchestrator(
    strategy=FallbackStrategy([
        AnthropicProvider(api_key=os.getenv("ANTHROPIC_API_KEY")),
    ]),
    tools=None,  # Populated after bot creation
)

bot = (
    Composer()
    .with_members()         # For member join/leave events
    .with_messages()        # For AI moderation
    .auto_sync(True)        # Sync commands on startup
    .log(level="INFO")      # Log all commands
    .catch_errors("An error occurred. Admins notified.")  # Global error handler
    .rate_limit(limit=10, window=60)  # 10 commands/user/minute
    .add_plugin(CustomPlugin())
    .add_plugin(ModerationPlugin())
    .add_plugin(MemberLoggingPlugin())
    .add_plugin(AIModeratorPlugin(orchestrator=orchestrator))
    .build()
)

# Populate orchestrator tool registry after bot creation
orchestrator.tools = bot.tool_registry

# ============================================================================
# 3. TOP-LEVEL COMMANDS — Global functionality
# ============================================================================

@bot.slash(description="Ping the bot")
async def ping(ctx):
    """Quick health check."""
    await ctx.respond(f"Pong! ({ctx.bot.latency*1000:.0f}ms)")

@bot.slash(description="Get help", ephemeral=True)
async def help(ctx):
    """Show available commands."""
    embed = (
        EmbedBuilder()
        .title("EasyCord Bot Help")
        .field("Commands", "/ping, /rank, /server_info, /help")
        .field("Moderation", "Handled automatically by AI and manual commands")
        .field("Logging", "All member changes logged to designated channel")
        .build()
    )
    await ctx.respond(embed=embed)

# ============================================================================
# 4. ERROR HANDLING — Graceful failures
# ============================================================================

@bot.on_error
async def on_error(ctx, error):
    """Global error handler — called on unhandled exceptions."""
    logger.exception(f"Unhandled error in {ctx.command_name}", exc_info=error)
    
    # Notify admins (optional)
    # audit_channel = bot.get_channel(YOUR_AUDIT_CHANNEL_ID)
    # if audit_channel:
    #     await audit_channel.send(f"❌ Error in `{ctx.command_name}`: {error}")

# ============================================================================
# 5. STARTUP & SHUTDOWN
# ============================================================================

@bot.on("ready")
async def on_ready():
    """Called when bot connects and is ready to receive events."""
    logger.info(f"Logged in as {bot.user}")
    logger.info(f"Serving {len(bot.guilds)} guilds")
    
    # Optional: Set custom status
    await bot.set_status(
        status="online",
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name="your server"
        )
    )

# ============================================================================
# 6. RUN
# ============================================================================

if __name__ == "__main__":
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        logger.error("DISCORD_TOKEN not set in .env")
        exit(1)
    
    bot.run(token)
```

Wait, you need one more import:

```python
from easycord import EmbedBuilder
```

Add to the imports at the top:

```python
from easycord import Bot, Composer, Plugin, slash, on, ServerConfigStore, EmbedBuilder
```

## Step 3: Test locally

```bash
# Run
python bot.py

# In Discord, test:
/ping
/rank
/server_info
/help

# Also test:
# - Member joins (logs to channel if MemberLoggingPlugin configured)
# - Spam message (AI moderator analyzes)
# - Any command errors (logged, admin notified)
```

## Step 3b: Watch failure modes

EasyCord is designed to contain failures. Test this:

```python
# In your test server:

# Test 1: Command timeout
# Use /rank with a very large user_id that causes a slow lookup
# Expected: defer → 3 sec wait → response. Bot doesn't crash.

# Test 2: AI tool fails
# Have AI try to kick the server owner (guardrail prevents it)
# Check logs: "AI tool: timeout failed — can't kick server owner"
# User sees: "AI tool failed, logged"
# Bot continues normally.

# Test 3: Permission denied
# Have non-admin try /ai_analyze (requires admin permission)
# Expected: Ephemeral error, logged, bot unaffected.

# Test 4: Database locked
# (Rare) If two plugins write to same guild_id simultaneously
# Expected: Queued writes, no lost data (ServerConfigStore async locks)
# You won't see this in testing but it prevents data corruption.
```

**Log output looks like:**

```
INFO - customcmd /ping invoked by @user
INFO - Ping: 45ms
INFO - ai_moderator analyzed 15 messages, found 1 spam
WARNING - AI tool: timeout failed — user not found
ERROR - Unhandled error in /rank: Discord API returned 403
  Traceback (most recent call last): ...
  [admin notified]
```

Bot stays online. Commands queue. Errors surface. Nothing cascades.

That's the robustness guarantee.

## Step 4: Deployment checklist

### Before pushing to production:

- [ ] Token in `.env`, NOT in code
- [ ] `.env` in `.gitignore`
- [ ] Bot invited with correct scopes (`applications.commands`, `bot`)
- [ ] Bot role above members it will moderate
- [ ] Error channel configured (optional but recommended)
- [ ] Rate limits appropriate for your guild size
- [ ] Intents enabled in Discord Developer Portal match code (usually auto-detected)
- [ ] Dependencies pinned: `pip freeze > requirements.txt`

### Production deployment:

```bash
# VPS / Docker / Cloud function — pick one

# Option 1: Simple VPS
ssh user@your-server
git clone your-repo
cd your-repo
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
# Set env vars (via systemd, .env, or secrets manager)
nohup python bot.py > bot.log 2>&1 &

# Option 2: Docker
# See docs/fork-and-expand.md for Dockerfile template

# Option 3: Managed (Replit, Railway, Heroku)
# git push to trigger deployment
```

### Monitoring

```python
# Add to on_ready()
@bot.on("ready")
async def on_ready():
    logger.info(f"Logged in as {bot.user}")
    
    # Log to file
    import sys
    print(f"{bot.user} is ready", file=sys.stderr)
    
    # Optional: Send to uptime monitor
    # requests.get("https://uptime-monitor.example.com/ping?id=bot_1")
```

## The EasyCord Pattern

What you just built demonstrates the framework philosophy:

### 1. **Plugins, not monoliths**
- `CustomPlugin` — your commands
- `ModerationPlugin` — manual moderation
- `AIModeratorPlugin` — AI moderation
- `MemberLoggingPlugin` — audit trail

Each plugin:
- Owns its own commands/events
- Doesn't know about other plugins
- Can be added/removed independently
- Has lifecycle hooks (`on_load`, `on_unload`)

### 2. **Declarative composition**
```python
bot = (
    Composer()
    .with_members()
    .add_plugin(...)
    .build()
)
```

No "choose your own middleware" or config sprawl. One way to do it.

### 3. **Context, not Interaction**
All your commands receive `ctx` with:
- Response methods (respond, defer, edit)
- Moderation (kick, ban, timeout)
- Configuration (access ServerConfigStore)
- UI helpers (confirm, choose, paginate)

No plumbing, just `await ctx.respond(...)`.

### 4. **AI as a primitive**
- `@ai_tool` decorator exposes functions
- `Orchestrator` routes across LLM providers
- Tools sandbox to `ToolSafety.SAFE/CONTROLLED/RESTRICTED`
- Plugins can call AI without knowing details

### 5. **Fail gracefully**
```python
@bot.on_error
async def on_error(ctx, error):
    logger.exception(...)
    # Bot doesn't crash, user gets message
```

## Expanding from here

Once running, add features by subclassing `Plugin`:

```python
class GamingPlugin(Plugin):
    @slash(description="Roll dice")
    async def roll(self, ctx, sides: int = 6):
        ...

bot.add_plugin(GamingPlugin())
```

Each plugin can:
- Register slash commands (`@slash`)
- Listen to events (`@on`)
- Run background tasks (`@task`)
- Expose tools to AI (`@ai_tool`)
- Store per-guild config (`ServerConfigStore`)

## Common next steps

### Add persistence
```python
# In plugin's on_load()
self.config = ServerConfigStore(".easycord/config")
cfg = await self.config.load(ctx.guild_id)
cfg.set_other("my_setting", value)
await self.config.save(cfg)
```

### Add AI tool calling
```python
@ai_tool(description="Check if user is admin", safety=ToolSafety.SAFE)
async def is_admin(self, ctx, user_id: int) -> str:
    member = await ctx.guild.fetch_member(user_id)
    return "Yes" if member.guild_permissions.administrator else "No"

# AI can now call this via orchestrator
```

### Add scheduled tasks
```python
@task(hours=24)
async def daily_cleanup(self):
    # Runs every 24 hours, auto-starts/stops with plugin
    ...
```

### Add error recovery
```python
try:
    await ctx.kick(member)
except discord.Forbidden:
    await ctx.respond("I don't have permission to kick", ephemeral=True)
except discord.NotFound:
    await ctx.respond("Member no longer in server", ephemeral=True)
```

## What you didn't have to write

- Slash command tree management
- Intent negotiation
- Response state machine (first vs followup)
- Permission checking plumbing
- Modal form scaffolding
- Per-guild config file handling + async locks
- Rate limit tracking
- Error handler boilerplate
- Plugin lifecycle wiring

That's the value: **working bot, no ceremony**.

## See also

- [`docs/api.md`](api.md) — complete reference
- [`docs/fork-and-expand.md`](fork-and-expand.md) — grow this into a bigger project
- [`docs/security-best-practices.md`](security-best-practices.md) — before going to production
- [`docs/troubleshooting.md`](troubleshooting.md) — when things break
