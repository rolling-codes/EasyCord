# Task Scheduling

The `@task` decorator marks a plugin method as a repeating background task. Tasks start automatically when the plugin loads and stop when it unloads — no manual lifecycle management needed.

---

## Quick start

```python
from easycord import Plugin, task

class StatusPlugin(Plugin):

    @task(minutes=5)
    async def update_status(self):
        await self.bot.change_presence(activity=discord.Game("Running…"))
```

`/update_status` runs every 5 minutes from the moment the plugin loads.

---

## Scheduling parameters

```python
@task(seconds=0, minutes=0, hours=0, restart=False, backoff=1.0)
```

| Parameter | Type | Description |
|---|---|---|
| `seconds` | `float` | Seconds component of the interval |
| `minutes` | `float` | Minutes component |
| `hours` | `float` | Hours component |
| `restart` | `bool` | Restart the loop automatically if it raises an exception |
| `backoff` | `float` | Sleep multiplier applied after each error when `restart=True` |

The interval is the **sum** of all three time arguments. Use whichever combination is clearest:

```python
@task(hours=1, minutes=30)   # every 90 minutes
@task(seconds=30)            # every 30 seconds
@task(minutes=1, seconds=30) # every 90 seconds
```

At least one argument must be non-zero; the interval must be greater than zero.

---

## Task lifecycle

Tasks are tied to the plugin, not the bot:

- **Starts** when `bot.add_plugin(plugin)` completes
- **Stops** when `bot.remove_plugin(plugin)` is called or the bot shuts down
- **Survives hot-reload** — the new plugin instance gets a fresh task after `on_reload()` fires

You do not need to call `.start()` or `.stop()` yourself.

---

## Error handling

By default a task that raises an unhandled exception stops permanently. Use `restart=True` to restart automatically:

```python
@task(minutes=1, restart=True, backoff=2.0)
async def fetch_prices(self):
    data = await external_api.get_prices()
    self._prices = data
```

With `restart=True` and `backoff=2.0`: after each failure the task sleeps for `interval × backoff` before trying again, doubling each successive failure.

For transient errors you expect and want to swallow, use a try/except inside the task instead:

```python
@task(minutes=5)
async def sync_cache(self):
    try:
        self._data = await self.bot.db.fetch_all()
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning("Cache sync failed: %s", exc)
```

---

## Blocking I/O

Task methods must be `async`. Never call blocking I/O (file reads, `requests.get`, CPU-heavy loops) directly — they block the entire bot. Use `asyncio.to_thread` to offload:

```python
import asyncio

@task(minutes=10)
async def rebuild_index(self):
    result = await asyncio.to_thread(compute_heavy_thing)
    self._index = result
```

---

## Testing

Inject a `FakeBot` and call the task method directly — no need to advance real time:

```python
async def test_status_update(bot):
    plugin = StatusPlugin.__new__(StatusPlugin)
    plugin._bot = bot
    Plugin.__init__(plugin)

    await plugin.update_status()  # call directly, no asyncio.sleep needed

    assert bot.last_presence is not None
```

For tests that need to verify the task fires at the right interval, mock `asyncio.sleep` and assert the side effect.
