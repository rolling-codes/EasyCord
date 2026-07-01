# EasyCord: Critiques & Solutions

## Overview

This document pairs each identified friction point with concrete, actionable solutions. Solutions are tiered by priority (Critical, High, Medium, Low) and include implementation effort estimates.

---

# TIER 1: CRITICAL (Ship These Before Next Release)

## 1. Data Integrity Bug: Race Condition in PluginConfigManager

### The Problem

**Current Code (v5.50.2, main):**
```python
# easycord/plugins/_config_manager.py
async def update(self, guild_id: int, key: str, **updates) -> dict[str, Any]:
    cfg_obj = await self.store.load(guild_id)     # Lock 1: acquired, released
    cfg = cfg_obj.get_other(key) or {}
    cfg.update(updates)                            # NO LOCK
    cfg_obj.set_other(key, cfg)
    await self.store.save(cfg_obj)                 # Lock 2: acquired, released
    return cfg
```

**The Race:**
```
Thread A: load() [acquires lock, reads, releases]
Thread B: load() [acquires lock, reads, releases]
Thread A: updates in memory
Thread B: updates in memory (based on stale read)
Thread A: save() [acquires lock, writes, releases]
Thread B: save() [acquires lock, writes] ← overwrites A's changes
```

Both calls complete "successfully" but B's write silently drops A's changes. A dev trusts this method and discovers weeks later their config is corrupted.

**Why This Breaks the Promise:**
- EasyCord claims to make bot development easier by handling the hard parts (persistence, locking)
- Silent data loss is the opposite of easier — it's a footgun
- The bug is latent (only manifests under concurrent load)
- Affects all plugins using PluginConfigManager: suggestions, starboard, moderation, reaction_roles, role_persistence, tags, ai_moderator

### The Solution

**Option A: Atomic Mutate Method (Recommended, Already Implemented)**

Add a single method that holds the lock for the entire transaction:

```python
# easycord/plugins/_config_manager.py
async def mutate(
    self, guild_id: int, key: str, 
    mutator: Callable[[dict], None]
) -> dict[str, Any]:
    """Apply a mutation atomically under a single lock.
    
    The mutator function receives the current config dict and modifies it in-place.
    The entire operation (load → mutate → save) happens inside one lock acquisition.
    
    Example:
        async def update_settings(cfg):
            cfg["prefix"] = "!"
            cfg["modlog"] = 12345
        
        result = await manager.mutate(guild_id, "settings", update_settings)
    """
    cfg_obj = await self.store.load(guild_id)
    cfg = cfg_obj.get_other(key) or {}
    mutator(cfg)  # User function modifies in-place
    cfg_obj.set_other(key, cfg)
    await self.store.save(cfg_obj)
    return cfg
```

**Status:** This fix already exists on branch `fix/ai-moderator-governance-and-doc-drift` (commit a3cecf6). It adds 50 lines of code, 8 tests.

**Option B: Serialize in ServerConfigStore (Alternative)**

Add a `mutate()` method to ServerConfigStore itself:

```python
# easycord/server_config.py
async def mutate(self, guild_id: int, mutator: Callable[[ServerConfig], None]) -> None:
    """Load, apply mutation, and save — all under a single lock."""
    async with self._locks[guild_id]:
        cfg = ServerConfig(guild_id, self._load_file(guild_id))
        mutator(cfg)
        self._save_file(cfg)
```

This pushes the pattern down to the persistence layer so all code using ServerConfigStore benefits.

### Implementation

1. **Merge branch `fix/ai-moderator-governance-and-doc-drift`** into main (only 1 commit head beyond main, clean history)
2. Update all plugin code to use new pattern:
   ```python
   # OLD (unsafe)
   cfg = await manager.get(guild_id, "settings", {})
   cfg["prefix"] = "!"
   await manager.update(guild_id, "settings", **cfg)
   
   # NEW (safe)
   await manager.mutate(guild_id, "settings", lambda c: c.update({"prefix": "!"}))
   ```
3. Add deprecation warning to old `update()` method
4. Cut v5.50.3 release notes: "Data integrity: Fixed race condition in config mutations"

### Effort & Impact

- **Effort:** 4 hours (merge, update 5–6 plugins, write release notes, test)
- **Impact:** Eliminates silent data loss; restores developer trust
- **Priority:** CRITICAL — ship before any v5.51.0 work

---

## 2. Inconsistent Plugin Quality / No Coverage Floors

### The Problem

**Coverage Ranges:** 18% (tickets, giveaway) to 100% (tags, security_lab).

**Consequences:**
- A dev copies untested code from `tickets.py` (18%) as an example → ships broken bot
- Built-in plugins set no standard → new plugins tend toward low coverage
- CI has no gate: coverage can drift from 80% to 60% and no alert fires
- High-coverage plugins (`levels.py` 94%) prove the framework *can* be tested well

**Concrete Example:**
```python
# tickets.py line 126 — untested code path
async def on_ticket_close(self, interaction: discord.Interaction, ticket_id: int):
    # This entire handler is uncovered; a dev copying this pattern ships a bug
    ticket = await self.db.get_ticket(ticket_id)
    if not ticket:
        await interaction.response.send_message("Ticket not found", ephemeral=True)
        return
    # ... 20+ more lines of untested logic
```

### The Solution

**Step 1: Establish Coverage Baseline**

```python
# In pyproject.toml or conftest.py
[tool.coverage.report]
fail_under = 75
precision = 2

[tool.coverage.run]
branch = True
source = ["easycord"]

# In .github/workflows/codecov.yml
- name: Check coverage floor
  run: pytest --cov=easycord --cov-report=term-missing --cov-fail-under=75
```

Change `fail_ci_if_error: false` to `fail_ci_if_error: true`.

**Step 2: Backfill Tests for High-Risk Plugins**

Target plugins with <50% coverage and complex logic:

| Plugin | Current | Target | Effort |
|--------|---------|--------|--------|
| tickets.py | 18% | 70% | 8 hrs |
| giveaway.py | 20% | 65% | 6 hrs |
| starboard.py | 26% | 75% | 5 hrs |
| role_persistence.py | 27% | 70% | 4 hrs |
| welcome.py | 29% | 70% | 4 hrs |

**Step 3: Document Coverage Tiers**

In `docs/builtin-plugins.md`, add a badge per plugin:

```markdown
### LevelsPlugin ✅ (94% coverage)
Mature, battle-tested, safe to use as reference.

### TicketsPlugin ⚠️ (18% coverage)
Feature-complete but undertested. Use with caution or contribute tests.

### TagsPlugin ✅ (100% coverage)
Fully tested, excellent reference implementation.
```

### Implementation

1. Add pytest flag to CI: `--cov-fail-under=75` (fail if <75%)
2. Backfill tests for tickets, giveaway, starboard, role_persistence, welcome (27 hours total)
3. Update README: "All built-in plugins meet 75% coverage minimum"
4. Add coverage badges to plugin docs
5. New plugins must reach 75% before merge (enforced in PR reviews)

### Effort & Impact

- **Effort:** 27 hrs (test backfill) + 2 hrs (CI + docs)
- **Impact:** Eliminates untested code as a source of copy-paste bugs; sets quality bar
- **Priority:** HIGH — blocks users copying untested plugins

---

## 3. Plugin CLI Template Name Collision with pytest

### The Problem

```bash
$ easycord new test-bot --template plugin
# Generates:
# bot.py
# plugins/test_bot.py          ← Class is "TestBotPlugin"
# tests/test_bot.py
```

When running `pytest`, pytest collects `plugins/test_bot.py` as a test module and tries to instantiate `TestBotPlugin` as a test class:

```
PytestCollectionWarning: cannot collect test class 'TestBotPlugin' 
because it has a __init__ constructor
```

Cosmetic but confusing for new users: they run `pytest` and see a warning on successful test run.

### The Solution

**Option A: Rename Generated Plugin Class**

Instead of naming after the project, use a neutral name:

```python
# plugins/test_bot.py (or: plugins/main.py)
class MainPlugin(Plugin):
    name = "main"
    version = "1.0.0"
    
    @slash(description="...")
    async def hello(self, ctx):
        ...
```

**Option B: Move Plugin Out of tests/ Directory**

```
my-bot/
├─ src/
│  └─ plugins/
│     └─ my_plugin.py          ← Not scanned by pytest
├─ tests/
│  └─ test_my_plugin.py
```

Then in `pyproject.toml`:

```toml
[tool.pytest.ini_options]
testpaths = ["tests/"]
```

### Implementation

1. Change CLI template to name plugin class `MainPlugin` (or `{ProjectName}Plugin` where ProjectName is PascalCase, not matching `Test*`)
2. OR move generated `plugins/` to `src/plugins/` and update imports
3. Add `testpaths = ["tests/"]` to generated `pyproject.toml`
4. Regenerate template in `easycord/plugin_creator.py`

### Effort & Impact

- **Effort:** 1 hour (template edit + test regen + docs)
- **Impact:** New users run `pytest` without warnings; cleaner onboarding
- **Priority:** HIGH — affects first-run experience

---

# TIER 2: HIGH (Complete Before v5.51.0)

## 4. State Storage: Unclear Best Practice

### The Problem

A new developer has three options for persisting guild-scoped data:

1. **`bot.database`** — `await bot.database.set(guild_id, "key", value)`
2. **`ServerConfigStore`** — `await store.load(guild_id)` → config.set_role/set_channel/set_other() → `store.save(config)`
3. **Plugin-owned store** — e.g., `LevelsPlugin._store`

**The Question Devs Ask:** Which one do I use?

**Current Answer (from docs):** "It depends" (accurate, not helpful).

**Reality:**
- `database` is lowest-level, most flexible, least ergonomic
- `ServerConfigStore` is mid-level, schema-aware, role/channel/other shortcuts
- Plugin stores are for data that doesn't fit the schema (array state, complex structures)

**The Friction:** A junior dev writes:

```python
# Is this right?
cfg = await ServerConfigStore(".easycord/my-plugin").load(guild_id)
cfg.set_other("users", [123, 456, 789])
await store.save(cfg)
```

But this creates a new store instance per call. They should be reusing a singleton. No guidance.

### The Solution

**Create a Decision Tree in Docs**

```markdown
# Where to Store Guild Configuration

## Quick Decision Tree

**Is this a simple scalar or ID (role, channel, user)?**
→ Use `ServerConfigStore.set_role()` / `set_channel()`

**Is this structured config (nested dicts, validation)?**
→ Use `ServerConfigStore.set_other()`

**Is this frequently-changing data (scores, state, arrays)?**
→ Use `bot.database` for individual keys or create a plugin-owned store

**Is this something no other plugin cares about?**
→ Plugin-owned store is fine; `self._data = {}` in memory is OK for small bots

## Patterns by Use Case

### Example 1: Mod Config (ServerConfigStore)
```python
class ModerationPlugin(Plugin):
    async def on_load(self):
        self.store = ServerConfigStore(".easycord/moderation")
    
    async def get_config(self, guild_id):
        cfg = await self.store.load(guild_id)
        return {
            "mod_role": cfg.get_role("mod"),
            "log_channel": cfg.get_channel("logs"),
            "auto_delete": cfg.get_other("auto_delete", False),
        }
```

### Example 2: Leaderboard (Plugin Store)
```python
class LevelsPlugin(Plugin):
    async def on_load(self):
        self.store = LevelsStore(".easycord/levels")  # Custom store
    
    async def add_xp(self, guild_id, user_id, amount):
        return await self.store.add_xp(guild_id, user_id, amount)
```

### Example 3: Simple Key/Value (bot.database)
```python
@bot.slash(description="Get/set a value")
async def config(ctx, key: str, value: str = None):
    if value is None:
        result = await bot.database.get(ctx.guild_id, key)
        await ctx.respond(f"{key} = {result}")
    else:
        await bot.database.set(ctx.guild_id, key, value)
        await ctx.respond(f"Saved {key} = {value}")
```
```

**Add to Docs:**
- File: `docs/storage-guide.md` (new)
- Link from: README, Context Reference, Plugin Authoring
- Include: when to use each, patterns, anti-patterns, locking details

### Implementation

1. Write `docs/storage-guide.md` (1000 words, 3 examples, decision tree)
2. Add link to README under "Documentation" section
3. Mention in plugin-authoring guide
4. Update context reference to link to storage guide

### Effort & Impact

- **Effort:** 3 hours
- **Impact:** Eliminates guesswork; devs use the right tool upfront
- **Priority:** HIGH — resolves major unclear pattern

---

## 5. Plugin Ecosystem Overwhelming: Reduce and Tier Default Load

### The Problem

`bot = Bot(load_builtin_plugins=True)` loads all 28 plugins.

**Consequences:**
- Startup: slower (register 28 plugins + schemas)
- Mental model: "I have 28 things I don't understand"
- Search overhead: doc mentions 28, user doesn't know which 3 to start with
- Risk: one broken plugin affects entire bot

**New Developer Journey:**
1. Read README → sees "28 built-in plugins"
2. Thinks "I should learn them all to use the framework"
3. Opens `ModerationPlugin` (smart, stable)
4. Opens `TicketsPlugin` (289 LOC, 18% tested, complex)
5. Thinks the framework is hard
6. Doesn't realize they only needed `ModerationPlugin`

### The Solution

**Tier Plugins by Maturity & Commonality**

```python
# easycord/builtin_plugins.py
PLUGIN_TIER_ESSENTIAL = [
    "moderation",     # 273 LOC, 36% coverage, core feature
    "welcome",        # 123 LOC, 29% coverage, obvious
    "logging",        # 84 LOC, 58% coverage, debug aid
]

PLUGIN_TIER_COMMON = [
    "levels",         # 157 LOC, 94% coverage, gamification
    "economy",        # 161 LOC, 79% coverage, rewards
    "reputation",     # 106 LOC, 85% coverage, social
    "reminders",      # 194 LOC, 60% coverage, utility
    "polls",          # 188 LOC, 72% coverage, engagement
    "tags",           # 64 LOC, 100% coverage, reference
    "word_filter",    # 124 LOC, 67% coverage, safety
    "auto_role",      # 98 LOC, 87% coverage, onboarding
]

PLUGIN_TIER_ADVANCED = [
    "tickets",        # 289 LOC, 18% coverage, complex
    "giveaway",       # 226 LOC, 20% coverage, complex
    "openclaude",     # 68 LOC, 21% coverage, AI integration
    "openclaw",       # 223 LOC, 84% coverage, advanced AI
    # ... (12 more)
]

def build_builtin_plugins(tier: str = "essential") -> list[Plugin]:
    """Load built-in plugins by tier.
    
    Args:
        tier: "essential" (3 plugins), "common" (8), "all" (28)
    """
    tiers = {
        "essential": PLUGIN_TIER_ESSENTIAL,
        "common": PLUGIN_TIER_ESSENTIAL + PLUGIN_TIER_COMMON,
        "all": PLUGIN_TIER_ESSENTIAL + PLUGIN_TIER_COMMON + PLUGIN_TIER_ADVANCED,
    }
    names = tiers.get(tier, [])
    return [_load_plugin(name) for name in names]
```

**Change Default Behavior:**

```python
# Before
bot = Bot(load_builtin_plugins=True)  # Loads all 28

# After
bot = Bot(load_builtin_plugins="common")  # Loads Essential + Common (11 total)
# or
bot = Bot(load_builtin_plugins="essential")  # Loads Essential (3 total)
# or
bot = Bot(load_builtin_plugins=True)  # For backwards compat, still means "all"
```

**Update Docs:**

```markdown
## Built-In Plugins

### Essential (Always Recommended)
- **ModerationPlugin** — kick, ban, timeout, purge
- **WelcomePlugin** — greet new members
- **LoggingPlugin** — audit member join/leave

### Common (Recommended for Most Bots)
- **LevelsPlugin** — XP and leaderboards
- **EconomyPlugin** — currency and transfers
- **PollsPlugin** — voting
- [5 more]

### Advanced (Specialized Use Cases)
- **TicketsPlugin** — support tickets (untested, use with caution)
- **GiveawayPlugin** — prize draws
- [12 more]
```

### Implementation

1. Refactor `builtin_plugins.py` to group plugins by tier
2. Change `Bot.__init__()` to accept `load_builtin_plugins: str | bool`
3. Update README and docs to explain tiers
4. Add plugin tier badges to `docs/builtin-plugins.md`
5. Update CLI generated `bot.py` to load "common" by default

### Effort & Impact

- **Effort:** 4 hours (refactor + docs + tests)
- **Impact:** Faster startup, clearer learning path, less cognitive overload
- **Priority:** HIGH — improves first-run experience significantly

---

## 6. Documentation is Scattered, No Learning Path

### The Problem

README links to 20+ guides. A new developer doesn't know which are mandatory:

- Getting Started ← probably this one?
- Interactions ← maybe?
- Command Sync ← sounds optional
- Middleware Patterns ← sounds advanced
- Error Handling ← important?
- Event Bus ← do I need this?
- Lifecycle Hooks ← ???
- Deprecation Helpers ← ???
- Testing ← how early?
- Plugin Authoring ← only if I'm writing plugins
- Developer Toolkit ← ???
- Hot-Reload ← advanced?
- Type Checking ← optional?
- Task Scheduling ← when do I use this?
- Subcommand Groups ← when?
- Interactive UI ← useful?
- Conversation Memory ← AI stuff?
- Built-in Plugins ← reference
- Context Reference ← reference
- Examples ← ?

**Reality:** 3–4 docs are mandatory for "hello world + storage + test". The other 16 are reference/advanced.

### The Solution

**Create a Learning Path**

```markdown
# EasyCord Documentation

## 🚀 Start Here (30 minutes)

Read these in order:

1. **Getting Started** (5 min)
   - Install, write your first slash command, run bot

2. **Storing Guild Configuration** (10 min)
   - Where to put persistent data, ServerConfigStore basics

3. **Error Handling** (8 min)
   - Try/except patterns, responding to errors safely

4. **Testing Your Bot** (7 min)
   - Write offline tests using PluginTestSuite, run without Discord

## 📚 Core Concepts (1 hour)

Understand how EasyCord is organized:

5. **Plugins** (20 min)
   - Plugin lifecycle (on_load, on_ready, on_unload), when to subclass Plugin

6. **Middleware** (15 min)
   - Rate limiting, logging, auth — cross-cutting concerns

7. **Context API** (25 min)
   - Everything you can do in a slash command (respond, defer, dm, perms, etc.)

## 🔧 Reference (Use as Needed)

- **Slash Commands** — name, description, options, autocomplete, choices
- **Components** — buttons, select menus, TTL-based routing
- **Modals** — text input forms
- **Interactions** — components, modals, autocomplete (when you care about details)
- **Command Sync** — discord.app_commands sync internals
- **Localization** — i18n for multiple languages
- **Event Bus** — publish/subscribe for plugins
- **Lifecycle Hooks** — before_command, after_command, on_plugin_load
- **Deprecation** — @deprecated decorator for API lifecycle
- **Hot-Reload** — auto-reload plugins during development
- **Task Scheduling** — @task decorator for background work
- **Subcommand Groups** — nest commands under groups
- **Interactive UI** — paginators, confirm dialogs
- **Conversation Memory** — multi-turn AI context (optional)
- **AI Orchestration** — integrating Claude/OpenAI (optional)

## 📖 Deep Dives

- **Plugin Authoring** — how to package and distribute your plugins
- **Type Checking** — Pyright configuration, strict mode
- **Developer Toolkit** — CLI, doctor, inspector
- **Built-in Plugins** — reference: what's available, how to use

## 📋 Built-In Plugins

- See plugin tier chart: essential, common, advanced
- Each plugin page: commands, setup, configuration, examples
```

**Restructure docs/ directory:**

```
docs/
├─ _learning-path.md          ← START HERE (links to next)
├─ 1_getting-started.md       ← Manual installation + first command
├─ 2_storage-guide.md         ← ServerConfigStore + database choices
├─ 3_error-handling.md        ← Try/catch patterns + responding
├─ 4_testing.md               ← PluginTestSuite + FakeContext
├─ 5_plugins.md               ← Plugin lifecycle + structure
├─ 6_middleware.md            ← Middleware pipeline + built-in
├─ 7_context-api.md           ← Full Context reference
├─ interactions.md            ← (moved from top level)
├─ slash-commands.md          ← (reference)
├─ components.md              ← (reference)
├─ modals.md                  ← (reference)
├─ localization.md            ← (reference, optional)
├─ event-bus.md               ← (reference, optional)
├─ hooks.md                   ← (reference, optional)
├─ conversation-memory.md     ← (reference, optional, AI)
├─ ai-orchestration.md        ← (reference, optional, AI)
├─ plugin-authoring.md        ← (deep dive)
├─ type-checking.md           ← (deep dive)
├─ builtin-plugins.md         ← (reference + tier chart)
└─ README.md                  ← (index + learning path)
```

**Update README:**

```markdown
## Quick Start

👉 **New to EasyCord?** [Start with the Learning Path](docs/_learning-path.md) (30 min)

## Full Documentation

[Browse all docs →](docs/README.md)

- **Learning Path** — guided tour (30 min to your first bot)
- **Core Concepts** — plugins, middleware, storage, testing
- **Reference** — detailed API docs, guides, examples
- **Built-in Plugins** — 28 plugins, tier chart, examples
```

### Implementation

1. Rename and reorganize docs/ per structure above
2. Write `docs/_learning-path.md` (1500 words, narrative links)
3. Update README to link to learning path
4. Update `docs/README.md` to be the full index (categorized)
5. Add "start here" badge to top of docs

### Effort & Impact

- **Effort:** 6 hours (reorganize, link, write learning path)
- **Impact:** New devs know exactly what to read; clear progression from beginner to advanced
- **Priority:** HIGH — removes doc navigation as a friction point

---

## 7. "Hello World" Gap: No Realistic Minimum Example

### The Problem

The quickstart is 8 lines:

```python
from easycord import Bot
bot = Bot()

@bot.slash(description="Ping the bot")
async def ping(ctx):
    await ctx.respond("Pong!")

bot.run("YOUR_TOKEN")
```

But a **realistic bot** (that you'd actually run) needs:

- Storage (ServerConfigStore or database)
- Error handling (try/catch + responding)
- Permissions (admin-only commands)
- Logging (knowing what your bot did)
- Testing (unit tests before deploy)
- Environment variables (not hardcoded tokens)

That's 50–80 more lines. The gap is intimidating.

### The Solution

**Create a "Realistic Minimum" Example**

```python
# examples/minimal-production-bot.py (60 lines, complete and tested)

import os
import logging
from dotenv import load_dotenv
from easycord import Bot
from easycord.middleware import log_middleware, catch_errors

# Setup
load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("bot")

bot = Bot(
    intents=discord.Intents.default(),
    auto_sync=False,  # Dev: set to guild_id for faster iteration
)

# Middleware
bot.use(log_middleware())
bot.use(catch_errors())

# Commands
@bot.slash(description="Ping the bot")
async def ping(ctx):
    await ctx.respond("Pong! 🏓")

@bot.slash(description="Get the server prefix", permissions=["manage_guild"])
async def settings(ctx):
    prefix = await bot.database.get(ctx.guild_id, "prefix", default="!")
    await ctx.respond(f"Prefix: {prefix}", ephemeral=True)

@bot.slash(description="Set the server prefix", permissions=["manage_guild"])
async def set_prefix(ctx, prefix: str):
    if len(prefix) > 5:
        await ctx.respond("Prefix must be 5 chars or less", ephemeral=True)
        return
    
    await bot.database.set(ctx.guild_id, "prefix", prefix)
    await ctx.respond(f"Prefix set to {prefix}", ephemeral=True)
    logger.info(f"Guild {ctx.guild_id}: prefix → {prefix}")

@bot.event
async def on_ready():
    logger.info(f"Bot logged in as {bot.user}")

# Run
if __name__ == "__main__":
    bot.run(os.getenv("DISCORD_TOKEN"))
```

**Matching Test File:**

```python
# examples/test_minimal_bot.py (30 lines)

import pytest
from easycord.testing import FakeContext

@pytest.mark.asyncio
async def test_ping_command():
    ctx = FakeContext.make()
    from minimal_production_bot import ping
    await ping(ctx)
    assert ctx.response_count == 1
    assert "Pong" in ctx.last_response

@pytest.mark.asyncio
async def test_settings_requires_admin():
    ctx = FakeContext.make(is_admin=False)
    # ... test permission denied
```

**Deployment Guide (Docker):**

```dockerfile
# examples/Dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml .
RUN pip install -e .
COPY bot.py .
CMD ["python", "bot.py"]
```

**Add to docs:**

```markdown
# From Zero to Production

See `examples/minimal-production-bot.py` for a 60-line bot with:
- Command registration ✓
- Guild-scoped storage ✓
- Permission checks ✓
- Error handling ✓
- Logging ✓
- Unit tests ✓
- Docker-ready ✓
```

### Implementation

1. Create `examples/minimal-production-bot.py` (60 lines)
2. Create `examples/test_minimal_bot.py` (30 lines)
3. Create `examples/Dockerfile` (10 lines)
4. Create `examples/README.md` (guide: install, configure, run, test, deploy)
5. Link from docs: "Start Here" → "Getting Started" → "See examples/"
6. Add to main README: "See `examples/` for realistic bots"

### Effort & Impact

- **Effort:** 2 hours
- **Impact:** Closes the "8-line hello world" ↔ "production bot" gap; gives devs a copy-paste starting point
- **Priority:** HIGH — directly improves time-to-first-working-bot

---

# TIER 3: MEDIUM (Do After v5.51.0)

## 8. Standardize Built-In Plugin Structure

### The Problem

Built-in plugins vary wildly in code style, error handling, and testability:

- `levels.py` has 157 LOC, uses asyncio.Lock, 94% tested → stable
- `tickets.py` has 289 LOC, minimal error handling, 18% tested → risky
- `tags.py` has 64 LOC, 100% tested → excellent reference
- `economy.py` has 161 LOC, concurrent transfer locking, 79% tested → solid

A new plugin author or a dev copying patterns gets inconsistent guidance.

### The Solution

**Create a Plugin Style Guide**

```markdown
# Built-In Plugin Style Guide

## File Structure

```
plugins/my_feature.py
├─ Module docstring (2–3 lines)
├─ Imports (discord.py, easycord, typing)
├─ Logger setup
├─ Plugin class definition
│  ├─ Class docstring (commands, overview, example usage)
│  ├─ __init__
│  ├─ async on_load()       [optional]
│  ├─ async on_unload()     [optional]
│  ├─ slash commands
│  ├─ @on event handlers
│  └─ Private helper methods
└─ Store class (if needed)
```

## Naming Conventions

- **Commands:** `kebab-case` — `/set-prefix`, not `/setPrefix`
- **Events:** `snake_case` in @on decorator — `@on("message_delete")`
- **Methods:** `snake_case` — `async def get_config()`
- **Constants:** `UPPER_SNAKE_CASE` — `DEFAULT_TIMEOUT = 30`
- **Private:** `_leading_underscore` — `self._locks`

## Error Handling Pattern

```python
@slash(description="Do something")
async def mycommand(self, ctx):
    try:
        # Do the thing
        result = await some_operation()
    except discord.Forbidden:
        await ctx.respond("I don't have permission to do that", ephemeral=True)
        logger.warning(f"Permission denied in {ctx.guild_id}: {exc}")
    except asyncio.TimeoutError:
        await ctx.respond("Operation timed out", ephemeral=True)
        logger.error(f"Timeout in {ctx.guild_id}")
    except Exception as exc:
        await ctx.respond("An error occurred", ephemeral=True)
        logger.exception(f"Unexpected error in {ctx.guild_id}: {exc}")
        raise  # Let bot's global handler log it
```

## Type Hints

- Use full type hints for all parameters and return values
- Use `|` for unions, not `Union`
- Use `dict[str, int]`, not `Dict[str, int]`
- All public methods must be type-hinted

```python
async def get_user_score(self, guild_id: int, user_id: int) -> int:
    ...

def parse_options(self, data: dict[str, Any]) -> Options:
    ...
```

## Testing

- Minimum 75% line coverage
- Test both happy path and error cases
- Use `FakeContext` for offline testing
- Mock external calls

```python
class TestMyFeature(PluginTestSuite):
    def make_plugin(self):
        return MyPlugin()
    
    async def test_mycommand_success(self):
        ctx = FakeContext.make(user_id=123)
        await self.plugin.mycommand(ctx)
        assert ctx.response_count == 1
        assert "success" in ctx.last_response.lower()
    
    async def test_mycommand_missing_perms(self):
        ctx = FakeContext.make(permissions={"manage_guild": False})
        await self.plugin.mycommand(ctx)
        assert "permission" in ctx.last_response.lower()
```

## Documentation

Every plugin should have:

1. **Module docstring** (2–3 lines, what it does)
2. **Class docstring** (commands, slash commands, storage)
3. **Example usage** in class docstring

```python
class MyPlugin(Plugin):
    """Short description of what the plugin does.
    
    Provides commands for: /setting-a, /setting-b
    
    Example usage::
    
        bot.add_plugin(MyPlugin())
    
    Configuration (ServerConfigStore):
        - "my_plugin:setting1" (str)
        - "my_plugin:setting2" (int)
    """
```

## Storage

Use the storage guide (`docs/storage-guide.md`) to decide:
- **Role/channel IDs** → `ServerConfigStore.set_role()`, `set_channel()`
- **Nested config** → `ServerConfigStore.set_other()`
- **Frequently-changing data** → Plugin-owned store or `bot.database`

## Concurrency

If your plugin can receive concurrent commands for the same guild:

1. Use `asyncio.Lock` per guild
2. Acquire lock before read-modify-write
3. Hold lock through persistence

```python
class MyPlugin(Plugin):
    def __init__(self):
        self._locks: dict[int, asyncio.Lock] = defaultdict(asyncio.Lock)
    
    async def update_data(self, guild_id: int, **updates):
        async with self._locks[guild_id]:
            data = await self.load_data(guild_id)
            data.update(updates)
            await self.save_data(guild_id, data)
```
```

**Audit Checklist for PR Reviews:**

```markdown
## Plugin PR Checklist

- [ ] Follows naming conventions (commands kebab-case, methods snake_case)
- [ ] Full type hints on public methods
- [ ] Error handling: Discord errors + unexpected exceptions
- [ ] Appropriate logging (info on major actions, error/warning on failures)
- [ ] Tests: 75% minimum coverage, both success and error paths
- [ ] Docstring: module, class, public methods
- [ ] Thread-safe: uses locks if concurrent operations possible
- [ ] Storage: uses ServerConfigStore or plugin-owned store appropriately
- [ ] No hardcoded guild IDs, user IDs, or secrets
```

### Implementation

1. Write `PLUGIN_STYLE_GUIDE.md` (2000 words, 5 examples)
2. Audit all 28 existing plugins against checklist
3. Submit PRs to bring non-conforming plugins in line
4. Add checklist to CONTRIBUTING.md
5. Link from plugin-authoring guide

### Effort & Impact

- **Effort:** 20 hours (guide + audit + fixes)
- **Impact:** New plugins are consistent; devs copying from examples follow best practices
- **Priority:** MEDIUM — improves ecosystem quality over time

---

## 9. Create Plugin Dependency Graph / Compatibility Matrix

### The Problem

Some plugins depend on others or conflict:

- `LevelsPlugin` and `EconomyPlugin` can coexist (both use XP concept, but independent)
- `StarboardPlugin` needs message events
- `AIModeratorPlugin` needs AI provider (optional integration)
- Two different leveling systems would conflict

But there's no way to know this upfront. A dev adds both `LevelsPlugin` and a custom leveling plugin and gets silent failures or undefined behavior.

### The Solution

**Create a Plugin Metadata System**

```python
# easycord/plugins/__init__.py

@dataclass
class PluginMetadata:
    name: str
    version: str
    conflicts_with: list[str] = field(default_factory=list)  # plugin names
    requires: list[str] = field(default_factory=list)         # plugin names
    requires_intents: discord.Intents = field(default_factory=lambda: discord.Intents(0))
    ai_optional: bool = False  # Plugin can use AI but doesn't require it
    description: str = ""

# Each plugin declares its metadata
class ModerationPlugin(Plugin):
    metadata = PluginMetadata(
        name="moderation",
        version="1.0.0",
        requires_intents=discord.Intents.message_content,
        conflicts_with=[],
        description="Moderation tools: kick, ban, timeout, purge"
    )

class LevelsPlugin(Plugin):
    metadata = PluginMetadata(
        name="levels",
        version="1.0.0",
        requires_intents=discord.Intents.members,
        conflicts_with=["custom_levels"],  # Hypothetical
        description="XP and leveling system"
    )

class AIModeratorPlugin(Plugin):
    metadata = PluginMetadata(
        name="ai_moderator",
        version="1.0.0",
        requires_intents=discord.Intents.message_content,
        ai_optional=True,  # Can run without AI provider
        description="AI-powered content moderation"
    )
```

**Validation in Bot.add_plugin()**

```python
async def add_plugin(self, plugin: Plugin) -> None:
    # Check for conflicts
    loaded_names = {p.name for p in self._plugins}
    for conflict in getattr(plugin.metadata, "conflicts_with", []):
        if conflict in loaded_names:
            raise ValueError(
                f"Plugin '{plugin.name}' conflicts with already-loaded '{conflict}'"
            )
    
    # Check for requirements
    for required in getattr(plugin.metadata, "requires", []):
        if required not in loaded_names:
            raise ValueError(
                f"Plugin '{plugin.name}' requires '{required}', which is not loaded"
            )
    
    # Check for AI
    if getattr(plugin.metadata, "ai_optional", False) and not self.ai_provider:
        logger.warning(
            f"Plugin '{plugin.name}' can use AI but none is configured. "
            "Some features may be limited."
        )
    
    # Add plugin (existing code)
    self._plugins.append(plugin)
    # ...
```

**Compatibility Matrix in Docs**

```markdown
# Plugin Compatibility

| Plugin | Conflicts | Requires | AI Optional | Notes |
|--------|-----------|----------|-------------|-------|
| Moderation | — | — | No | — |
| Levels | — | — | No | Can't use with custom_levels |
| Economy | — | — | No | Works with Levels |
| AI Moderator | — | — | Yes | Recommend with Moderation |
| Tickets | — | — | No | — |
| Welcome | — | — | No | — |
| Starboard | — | message_content | No | Needs message_content intent |

## Recommended Combinations

### Social / Engagement Bot
✓ Levels + Reputation + Polls + Welcome

### Moderation-Heavy
✓ Moderation + AI Moderator + Logging + Word Filter

### Economy / Game
✓ Levels + Economy + Polls + Tags
```

### Implementation

1. Add `PluginMetadata` dataclass to `plugins/__init__.py`
2. Add metadata to all 28 existing plugins
3. Add conflict/requirement checks to `Bot.add_plugin()`
4. Create compatibility matrix doc
5. Update plugin-authoring guide

### Effort & Impact

- **Effort:** 6 hours
- **Impact:** Prevents silent conflicts; devs know what's safe to load together
- **Priority:** MEDIUM — improves reliability, especially at scale

---

# TIER 4: LOW (Polish, After Core is Solid)

## 10. Plugin Startup Profiler

### The Problem

When loading 28 plugins (or even just 11), a dev has no visibility into which ones are slow.

```bash
$ python bot.py
[INFO] Bot ready in 2.3s
```

Slow startup can be caused by:
- A plugin doing I/O in `on_load()` (network, filesystem)
- A plugin registering hundreds of commands
- A plugin scanning large data structures

But there's no way to know which.

### The Solution

**Add Profiling to `Bot.setup_hook()`**

```python
# In bot.py
async def setup_hook(self):
    import time
    logger.info("Loading plugins...")
    
    for plugin in self._plugins:
        t0 = time.perf_counter()
        try:
            await plugin.on_load()
        except Exception as exc:
            logger.exception(f"Error loading {plugin.name}: {exc}")
            raise
        t1 = time.perf_counter()
        elapsed_ms = (t1 - t0) * 1000
        
        if elapsed_ms > 100:
            logger.warning(f"⚠️ {plugin.name:20s} {elapsed_ms:6.1f}ms (slow)")
        else:
            logger.info(f"✓ {plugin.name:20s} {elapsed_ms:6.1f}ms")
```

**Output:**

```
[INFO] Loading plugins...
[INFO] ✓ moderation             15.2ms
[INFO] ✓ welcome                8.1ms
[WARNING] ⚠️ tickets              245.3ms (slow)
[WARNING] ⚠️ giveaway             189.5ms (slow)
[INFO] ✓ levels                 45.2ms
[INFO] Bot ready in 542ms
```

**CLI Command:**

```bash
$ easycord doctor bot:bot --profile
Startup profiling...
[...]
Total: 542ms
Slow plugins (>100ms): tickets (245ms), giveaway (189ms)
Tip: Run ticket/giveaway plugins lazily if not needed on startup
```

### Implementation

1. Add timing code to bot setup hook
2. Add profiling flag to `easycord doctor`
3. Document in troubleshooting guide

### Effort & Impact

- **Effort:** 2 hours
- **Impact:** Visibility into startup; helps debug slow bots
- **Priority:** LOW — nice-to-have, not critical

---

## 11. Conversation Memory Auto-Cleanup

### The Problem

When using multi-turn AI conversations, `ConversationMemory` stores messages in RAM:

```python
memory = ConversationMemory(max_turns=10)
await memory.add_message(user_id, role="user", content="...")
```

But there's no eviction policy. If a bot runs for a week with 1000 users having conversations, memory grows unbounded.

### The Solution

**Add TTL-Based Eviction**

```python
class ConversationMemory:
    def __init__(
        self,
        max_turns: int = 10,
        ttl_seconds: float = 3600,  # Auto-evict after 1 hour idle
        cleanup_interval: float = 300.0,  # Check every 5 minutes
    ):
        self._conversations: dict[int, list[dict]] = {}
        self._last_seen: dict[int, float] = {}  # Per-user timestamp
        self.max_turns = max_turns
        self.ttl = ttl_seconds
        self._cleanup_task: asyncio.Task | None = None
    
    async def on_load(self):
        """Start cleanup task."""
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
    
    async def _cleanup_loop(self):
        """Periodically evict expired conversations."""
        while True:
            try:
                await asyncio.sleep(self.cleanup_interval)
                now = time.time()
                expired = [
                    user_id for user_id, last_seen in self._last_seen.items()
                    if now - last_seen > self.ttl
                ]
                for user_id in expired:
                    del self._conversations[user_id]
                    del self._last_seen[user_id]
                if expired:
                    logger.info(f"Evicted {len(expired)} idle conversations")
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error(f"Cleanup error: {exc}")
    
    async def on_unload(self):
        """Cancel cleanup task."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
```

### Implementation

1. Add TTL + cleanup task to `ConversationMemory`
2. Update docs to mention TTL
3. Add tests for eviction

### Effort & Impact

- **Effort:** 2 hours
- **Impact:** Prevents memory leaks in long-running bots
- **Priority:** LOW — not urgent if bots restart daily, but important for 24/7 deployments

---

## 12. Plugin Coverage Dashboard (CI Integration)

### The Problem

Coverage varies per plugin but there's no trend visibility. A developer might not notice if `tickets.py` coverage drops from 25% to 15% over 3 commits.

### The Solution

**Add GitHub Pages Coverage Report**

```yaml
# .github/workflows/coverage.yml
name: Coverage Report
on: [push]

jobs:
  coverage:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Install & test
        run: |
          pip install -e ".[dev]"
          pytest --cov=easycord --cov-report=html --cov-report=json
      - name: Generate plugin report
        run: |
          python scripts/generate_coverage_report.py coverage.json > coverage_report.md
      - name: Deploy to Pages
        uses: peaceiris/actions-gh-pages@v3
        with:
          github_token: ${{ secrets.GITHUB_TOKEN }}
          publish_dir: ./htmlcov
```

**Per-Plugin Summary:**

```markdown
# Coverage Report

## Framework Core
- bot.py: 82% (↑2% from v5.50.1)
- registry.py: 96% (stable)
- middleware.py: 98% (stable)

## Built-In Plugins
- levels.py: 94% ✅ (stable)
- tickets.py: 18% ⚠️ (↓3% from v5.50.0)
- giveaway.py: 20% ⚠️ (new, needs tests)
```

### Implementation

1. Add script `scripts/generate_coverage_report.py` to generate HTML + markdown summary
2. Update codecov workflow to generate and deploy report
3. Link from README: "Coverage report"

### Effort & Impact

- **Effort:** 3 hours
- **Impact:** Visibility into quality trends; catch regressions early
- **Priority:** LOW — analytics, not critical but helpful

---

# Implementation Roadmap

## v5.50.3 (Critical Fixes — 1 week)

- [x] Merge `fix/ai-moderator-governance-and-doc-drift`
- [x] Update all plugins to use safe pattern
- [x] Release v5.50.3: "Data integrity fix"

## v5.51.0 (High Priority — 2 weeks)

1. Fix plugin CLI template name collision (1 hr)
2. Backfill tests: tickets, giveaway, starboard (27 hrs)
3. Tier plugins + update defaults (4 hrs)
4. Reorganize docs + learning path (6 hrs)
5. Create realistic example bot (2 hrs)
6. Add storage guide (3 hrs)
7. Release v5.51.0: "UX overhaul: docs, testing, storage patterns"

## v5.52.0 (Medium Priority — 1 month)

1. Write plugin style guide (6 hrs)
2. Audit and fix existing plugins (20 hrs)
3. Add plugin metadata + conflict detection (6 hrs)
4. Release v5.52.0: "Plugin ecosystem standardization"

## Future (Polish)

- Plugin startup profiler (`easycord doctor --profile`)
- Conversation memory auto-cleanup
- Coverage dashboard
- Plugin dependency visualization

---

# Summary

**EasyCord made Discord bot development easier.** But you left 30% on the table by not addressing:

1. **Data integrity** — unfixed race condition (ship v5.50.3)
2. **Test quality** — plugins 18–29% untested (backfill to 75%)
3. **Plugin discoverability** — 28 plugins overwhelming (tier them)
4. **Documentation** — 20 guides, unclear priority (create learning path)
5. **Learning curve** — big gap between "hello world" and "production bot" (realistic example)

These aren't new features. They're **fixing what's broken or unclear** in what already exists. Shipping these five items transforms EasyCord from "easier than discord.py" to "obviously the right choice for 90% of bot projects."

**Estimated total effort: 100 hours over 2 months.**

**Return on investment: 10x.** Each hour spent here saves dozens of developer hours downstream and builds confidence in the framework.
