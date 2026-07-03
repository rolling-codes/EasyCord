# Organizing Code

As your bot grows, you'll want to split commands and logic into separate modules. EasyCord provides **plugins** (the main organizational unit), **task scheduling** (for background work), and the **event bus** (for loose coupling between plugins).

---

## Plugins: Your First Organizational Tool

A **plugin** is a class that groups related commands and state. Instead of adding individual commands to the bot, you add plugins.

### Your First Plugin

```python
from easycord import Plugin, slash

class GreetingPlugin(Plugin):
    """Greeting commands."""
    
    @slash(description="Say hello to someone")
    async def hello(self, ctx, name: str):
        await ctx.respond(f"Hello, {name}!")
    
    @slash(description="Say goodbye")
    async def goodbye(self, ctx, name: str):
        await ctx.respond(f"Goodbye, {name}!")
```

Register it with the bot:

```python
bot.add_plugin(GreetingPlugin())
```

### When to Use Plugins

Use plugins to group:
- **Related commands** — all "shop" commands in one plugin, all "moderation" commands in another
- **Shared state** — if multiple commands need to access the same data, put them in the same plugin
- **Reusable features** — a plugin can be extracted into a package and shared across projects

Don't use a single plugin for everything — split by domain (economy, moderation, fun, etc.).

### Plugin Lifecycle

Plugins can respond to load and unload events:

```python
class ConfigPlugin(Plugin):
    async def on_load(self) -> None:
        """Called when the plugin is loaded."""
        self._config = await self.bot.db.get_config()
        print("ConfigPlugin loaded")
    
    async def on_unload(self) -> None:
        """Called when the plugin is unloaded (on bot shutdown or hot-reload)."""
        await self.bot.db.save_config(self._config)
        print("ConfigPlugin unloaded")
```

Use `on_load` to initialize state, register hooks, or subscribe to events.  
Use `on_unload` to clean up — unregister hooks, save data, close connections.

### Accessing Bot State

From any plugin method, `self.bot` gives you access to the bot instance and its database:

```python
class EconomyPlugin(Plugin):
    @slash(description="Check your balance")
    async def balance(self, ctx):
        user_id = ctx.user.id
        balance = await self.bot.db.get(user_id, "coins", default=0)
        await ctx.respond(f"Your balance: **{balance}** 💰", ephemeral=True)
    
    @slash(description="Give coins to someone")
    async def give(self, ctx, user: discord.User, amount: int):
        await self.bot.db.add(ctx.user.id, "coins", -amount)
        await self.bot.db.add(user.id, "coins", amount)
        await ctx.respond(f"Sent **{amount}** coins to {user.mention}", ephemeral=True)
```

---

## Task Scheduling: Background Work

The `@task` decorator marks a plugin method as a repeating background job. Tasks start when the plugin loads and stop when it unloads.

### Your First Task

```python
from easycord import Plugin, task
import discord

class StatusPlugin(Plugin):
    
    @task(minutes=5)
    async def update_status(self):
        """Update bot status every 5 minutes."""
        await self.bot.change_presence(
            activity=discord.Game("Run /help for commands")
        )
```

### Scheduling Parameters

```python
@task(seconds=0, minutes=0, hours=0, restart=False, backoff=1.0)
```

| Parameter | Description |
|-----------|-------------|
| `seconds` | Seconds component of interval |
| `minutes` | Minutes component |
| `hours` | Hours component |
| `restart` | Restart the loop if it raises an exception |
| `backoff` | Sleep multiplier after each error (when `restart=True`) |

The interval is the **sum** of all time arguments:

```python
@task(hours=1, minutes=30)   # every 90 minutes
@task(seconds=30)            # every 30 seconds
@task(minutes=1, seconds=30) # every 90 seconds
```

### Error Handling in Tasks

By default a task that raises an exception stops permanently. Use `restart=True` to recover:

```python
@task(minutes=5, restart=True, backoff=2.0)
async def sync_remote_data(self):
    """Sync data every 5 minutes. Restart on error, with exponential backoff."""
    data = await external_api.get_data()
    self._cache = data
```

With `restart=True` and `backoff=2.0`, the task sleeps for `interval × backoff` after each failure, doubling on each successive failure.

For transient errors you want to ignore, use try/except inside the task:

```python
@task(minutes=10)
async def clean_cache(self):
    try:
        await self.bot.db.delete_old_entries()
    except Exception as exc:
        logger.warning("Cache cleanup failed: %s", exc)
        # Task continues; no restart needed
```

### Blocking I/O

Tasks must be `async`. Never call blocking I/O directly — use `asyncio.to_thread`:

```python
import asyncio

@task(hours=1)
async def compute_stats(self):
    """Offload expensive computation to a thread."""
    result = await asyncio.to_thread(self._compute_expensive_stats)
    await self.bot.db.save_stats(result)

def _compute_expensive_stats(self):
    # This blocks, but in a separate thread
    return sum(x**2 for x in range(1_000_000))
```

### Task Lifecycle

- **Starts** when `bot.add_plugin(plugin)` completes
- **Stops** when `bot.remove_plugin(plugin)` is called or the bot shuts down
- **Survives hot-reload** — the new plugin instance gets a fresh task

You don't call `.start()` or `.stop()` yourself.

---

## Event Bus: Loose Coupling Between Plugins

The **event bus** lets plugins communicate without direct imports. One plugin publishes an event; any other plugin that subscribed receives it.

`bot.event_bus` is created automatically — no setup needed.

### Example: Levels and Rewards

When a user levels up (LevelsPlugin), the RewardsPlugin should grant a milestone role:

```python
# levels_plugin.py
class LevelsPlugin(Plugin):
    async def _on_message(self, message):
        new_level = self._maybe_level_up(message.author.id)
        if new_level:
            # Announce the level-up to other plugins
            await self.bot.event_bus.publish(
                "user_leveled_up",
                user_id=message.author.id,
                guild_id=message.guild.id,
                level=new_level,
            )

# rewards_plugin.py
class RewardsPlugin(Plugin):
    async def on_load(self) -> None:
        # Listen for level-ups from any plugin
        self.bot.event_bus.subscribe("user_leveled_up", self._grant_reward)
    
    async def on_unload(self) -> None:
        # Clean up when unloading
        self.bot.event_bus.unsubscribe("user_leveled_up", self._grant_reward)
    
    async def _grant_reward(self, user_id: int, guild_id: int, level: int) -> None:
        if level % 10 == 0:
            await self._assign_milestone_role(guild_id, user_id, level)
```

### Event Bus API

#### `subscribe(event, callback)`

Register a callback for an event:

```python
# Sync callback
bot.event_bus.subscribe("user_joined", lambda user_id, guild_id: print(f"User {user_id} joined"))

# Async callback
async def on_join(user_id: int, guild_id: int) -> None:
    print(f"User {user_id} joined guild {guild_id}")

bot.event_bus.subscribe("user_joined", on_join)
```

#### `unsubscribe(event, callback)`

Remove a previously registered callback. Always call this in `on_unload`:

```python
async def on_unload(self) -> None:
    self.bot.event_bus.unsubscribe("user_joined", self._handler)
```

#### `await publish(event, **kwargs)`

Fire an event. All subscribed callbacks are called with the provided keyword arguments:

```python
await bot.event_bus.publish("order_placed", order_id=42, user_id=ctx.user.id)
```

**Important**: Sync callbacks run in order; async callbacks run concurrently via `asyncio.gather`. An exception in one callback doesn't crash other callbacks — each failure is logged and the bus continues.

### Event Naming

Use snake_case, past-tense verbs describing what happened:

```
user_leveled_up
order_placed
plugin_config_changed
moderation_action_taken
```

Prefix with the emitting plugin's name to avoid collisions:

```
levels.user_leveled_up
shop.order_placed
```

### Exception Isolation

A crash in one subscriber won't crash the publisher or other subscribers:

```python
async def buggy_handler(user_id: int) -> None:
    raise RuntimeError("oops")

async def fine_handler(user_id: int) -> None:
    print(f"User {user_id} joined")

bot.event_bus.subscribe("user_joined", buggy_handler)
bot.event_bus.subscribe("user_joined", fine_handler)

await bot.event_bus.publish("user_joined", user_id=42)
# ERROR logged for buggy_handler, fine_handler still runs
```

---

## Building Larger Features: Patterns

### Pattern: Per-Guild State with Database

Store per-guild settings in the database, not on `self`:

```python
class ConfigPlugin(Plugin):
    @slash(description="Set the prefix", guild_only=True)
    async def set_prefix(self, ctx, prefix: str):
        await self.bot.db.set(ctx.guild_id, "prefix", prefix)
        await ctx.respond(f"Prefix set to `{prefix}`.", ephemeral=True)
    
    @slash(description="Get the prefix", guild_only=True)
    async def get_prefix(self, ctx):
        prefix = await self.bot.db.get(ctx.guild_id, "prefix", default="!")
        await ctx.respond(f"Current prefix: `{prefix}`.", ephemeral=True)
```

This way your settings survive bot restarts and are automatically consistent across multiple bots reading the same database.

### Pattern: Notifying Other Plugins

When something important happens (user banned, config changed, role awarded), publish an event:

```python
class ModerationPlugin(Plugin):
    @slash(description="Ban a member", guild_only=True)
    async def ban(self, ctx, member: discord.Member, reason: str = ""):
        await ctx.guild.ban(member, reason=reason)
        
        # Let other plugins (logging, notifications) react
        await self.bot.event_bus.publish(
            "member_banned",
            guild_id=ctx.guild_id,
            user_id=member.id,
            reason=reason,
            mod_id=ctx.user.id,
        )
        
        await ctx.respond(f"Banned {member.mention}.", ephemeral=True)
```

### Pattern: One Plugin Watching Many Events

A logging plugin can listen to all important events:

```python
class LoggingPlugin(Plugin):
    async def on_load(self) -> None:
        self.bot.event_bus.subscribe("member_joined", self._log_join)
        self.bot.event_bus.subscribe("member_banned", self._log_ban)
        self.bot.event_bus.subscribe("config_changed", self._log_config)
    
    async def on_unload(self) -> None:
        self.bot.event_bus.unsubscribe("member_joined", self._log_join)
        self.bot.event_bus.unsubscribe("member_banned", self._log_ban)
        self.bot.event_bus.unsubscribe("config_changed", self._log_config)
    
    async def _log_join(self, user_id: int, guild_id: int) -> None:
        await self.bot.db.insert_log_entry("join", user_id, guild_id)
    
    async def _log_ban(self, guild_id: int, user_id: int, reason: str) -> None:
        await self.bot.db.insert_log_entry("ban", user_id, guild_id, reason)
    
    async def _log_config(self, guild_id: int, key: str, value: str) -> None:
        await self.bot.db.insert_log_entry("config", None, guild_id, f"{key}={value}")
```

---

## Testing

### Testing Plugins in Isolation

```python
import pytest
from easycord import Bot, Plugin, slash
from easycord.testing import invoke

class TestEconomyPlugin(Plugin):
    @slash(description="Get balance")
    async def balance(self, ctx):
        balance = await self.bot.db.get(ctx.user.id, "coins", default=0)
        await ctx.respond(f"Balance: {balance}")

@pytest.mark.asyncio
async def test_balance_default():
    bot = Bot(auto_sync=False, db_backend="memory")
    try:
        bot.add_plugin(TestEconomyPlugin())
        
        ctx = await invoke(bot, "balance")
        assert "Balance: 0" in ctx.last_response
    finally:
        await bot.close()
```

### Testing Tasks

Call task methods directly — no need to advance real time:

```python
@pytest.mark.asyncio
async def test_status_update():
    plugin = StatusPlugin.__new__(StatusPlugin)
    plugin._bot = bot  # Inject a FakeBot
    Plugin.__init__(plugin)
    
    await plugin.update_status()  # Call directly
    
    assert bot.last_presence is not None
```

### Testing the Event Bus

```python
from easycord.event_bus import EventBus

@pytest.mark.asyncio
async def test_reward_granted_on_level_up():
    bus = EventBus()
    granted: list[int] = []
    
    async def reward_handler(user_id: int, **_) -> None:
        granted.append(user_id)
    
    bus.subscribe("user_leveled_up", reward_handler)
    await bus.publish("user_leveled_up", user_id=7, level=10)
    
    assert granted == [7]
```

---

## Plugin Packages: Distributing Your Work

To share a plugin as an installable package, expose an entry point in `pyproject.toml`:

```toml
[project.entry-points."easycord.plugins"]
greetings = "easycord_greetings.plugin:GreetingPlugin"
```

Other projects can then load it:

```python
from easycord import Bot, load_entrypoint_plugins

bot = Bot(auto_sync=False)
for plugin in load_entrypoint_plugins():
    bot.add_plugin(plugin)
```

Use the CLI to scaffold a plugin package:

```bash
easycord plugin create greetings
```

This generates a complete package structure with manifest, tests, and entry-point configuration ready to publish.

---

## Next Steps

- Need persistent storage? → [Storage & State](database-guide.md)
- Want to test your plugins? → [Testing Commands](testing.md)
- Building complex features? → [Advanced Development](advanced-development.md)
