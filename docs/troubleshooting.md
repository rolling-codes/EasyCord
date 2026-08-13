# Master Troubleshooting Guide

Welcome to the EasyCord troubleshooting guide. This document proactively answers the top day-one development friction points you might encounter, providing diagnostic commands and fixes for each.

## 1. Missing Slash Commands

**Cause:** You've added new slash commands, but they aren't appearing in Discord. This is usually caused by having `auto_sync=False` in development or a mismatch with `sync_guild_id`.
**Fix:** 
During development, set `auto_sync=True` in your bot configuration, or manually sync the commands using the CLI:
```bash
easycord sync-plan
```

## 2. Volatile/Resetting Runtime State

**Cause:** Runtime state is being lost on local hot-reloads because you are using in-memory tracking structures (like dictionaries directly on the plugin) for data that should survive reloads.
**Fix:** 
Move persistent per-guild state to `PluginConfigManager` or `Bot.db`:
```python
# Instead of self.settings = {}
await self.config.update(ctx.guild.id, "settings", enabled=True)
```

## 3. Hot-Reload App Crashes

**Cause:** The bot crashes during a mid-lifecycle reload because a plugin's `__init__` constructor demands context arguments that are unavailable during the reload phase.
**Fix:** 
Refactor state migrations and context-dependent initialization into the `on_reload()` lifecycle hook instead of the constructor.
```python
class MyPlugin(Plugin):
    async def on_reload(self):
        # Perform context-dependent setup here
        pass
```

## 4. Silent AI Fallbacks

**Cause:** The AI orchestrator falls back silently, masking provider downtimes or invalid API keys due to silent exception handling inside `orchestrator.py`.
**Fix:** 
Enable explicit debug logging to reveal the raw orchestrator attempt streams. Run your bot with the `DEBUG` log level:
```bash
LOG_LEVEL=DEBUG python -m easycord.bot
```
Or configure it in code:
```python
import logging
logging.getLogger("easycord.orchestrator").setLevel(logging.DEBUG)
```

## 5. Production Database Amnesia

**Cause:** The bot is configured with `db_backend="memory"`, causing database-backed state to be lost when the bot restarts.
**Fix:** 
Use the default local SQLite database or configure an explicit volume-mapped path for production:
```python
bot = Bot(
    db_backend="sqlite",
    db_path="/data/bot.db"
)
```
