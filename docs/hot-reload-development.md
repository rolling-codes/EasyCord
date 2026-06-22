# Hot-Reload Development

## Quick Start

Add `reload=True` to `bot.run()` to enable hot-reload:

```python
bot.run(os.environ["DISCORD_TOKEN"], reload=True)
```

When a plugin file changes, you'll see:

```
DEBUG    easycord.bot:bot.py — Hot-reload triggered: plugins/greet.py
INFO     easycord.bot:bot.py — Plugin reloaded: GreetPlugin
```

---

## How It Works

- **Polls every 1 second** using `inspect.getfile()` + `os.path.getmtime()` for each registered plugin.
- **First pass seeds mtimes** — no reload fires on startup, only on subsequent changes.
- **On mtime change**, calls `importlib.reload(module)` to get the updated module.
- **Swaps the instance** — instantiates the new class, removes the old plugin, adds the new one.
- **Calls `on_reload()`** on the new instance so it can re-warm caches or reconnect resources.

---

## Safe Failure Modes

| Failure | Action |
|---------|--------|
| Syntax error or import error in the reloaded file | Keeps the old plugin running; logs the error |
| Class renamed or no longer present in the module | Keeps the old plugin running; logs the error |
| Module not resolvable (`inspect.getfile()` returns `None`) | Keeps the old plugin running; logs the error |

The bot never enters a broken state from a failed reload. Fix the file and save again — the next poll will retry.

---

## The on_reload() Hook

Override `on_reload()` on any `Plugin` subclass to run code after a successful hot-reload — re-fetching remote config, re-warming in-memory caches, or re-establishing connections that the plugin manages. It runs on the new instance, so `self.bot` is available.

```python
class GreetPlugin(Plugin):
    async def on_load(self):
        self._responses = await fetch_responses_from_db()

    async def on_reload(self):
        self._responses = await fetch_responses_from_db()
```

---

## Logging

| Level | When | Example message |
|-------|------|-----------------|
| `DEBUG` | Reload triggered by mtime change | `Hot-reload triggered: plugins/greet.py` |
| `INFO` | Reload completed successfully | `Plugin reloaded: GreetPlugin` |
| `ERROR` | Reload failed (any reason) | `Hot-reload failed for GreetPlugin: ...` |

---

## What Reloads vs. What Doesn't

**Reloads:**
- Plugin methods (`@slash`, `@on`, regular methods)
- Plugin `__init__` (re-instantiated from scratch)
- Imports at the top of the plugin file

**Doesn't reload:**
- Middleware registered via `bot.use()`
- Database connections opened at bot startup
- Bot-level `@slash` / `@on` decorators defined in `bot.py`
- Background tasks started by other plugins

---

## Production Safety

The watcher runs in a background asyncio task and adds measurable overhead from constant filesystem polling. Use an environment variable guard:

```python
bot.run(os.environ["DISCORD_TOKEN"], reload=os.environ.get("ENV") == "development")
```

Never ship `reload=True` hardcoded — it is a development-only feature.

---

## Troubleshooting

**Reload doesn't trigger after saving the file.**
Confirm the plugin was registered with `bot.add_plugin()` before `bot.run()` — the watcher only tracks files for plugins that were already loaded at startup.

**Plugin appears to reload (log shows INFO) but old code is still running.**
Python's module cache may have retained references to the old class. Ensure you're not storing plugin instances in module-level variables outside the plugin itself.

**`on_reload()` is never called.**
It only fires on a successful reload — check the logs for an ERROR preceding the missing INFO line. If the ERROR shows a class-not-found message, the class name changed between saves.

**Reload fails with an error but the old plugin keeps working.**
This is expected behavior. Fix the error in the plugin file and save again; the watcher will retry on the next poll.
