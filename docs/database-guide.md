# Production Database Readiness

This guide outlines the performance and scalability characteristics of the EasyCord database abstraction layer, specifically focusing on `SQLiteDatabase` and `MemoryDatabase`.

## Connection Lifecycle & Concurrency

* **SQLiteDatabase:** Uses a `sqlite3` connection protected by an asynchronous lock. Database operations run with `asyncio.to_thread`; there is no connection pool. Work on that connection is serialized, so measure latency against your expected workload before choosing deployment capacity.
* **MemoryDatabase:** Stores all records in standard Python dictionaries. It is entirely single-threaded and executes synchronously, making it extremely fast but volatile (data is lost on restart).

## Guild Sync Blocking Behaviors

When `db_auto_sync_guilds=True`, initial guild synchronization runs during
`setup_hook`. `guild_sync_timeout` bounds how long startup waits (30 seconds by
default). If that wait expires, startup continues and the shielded synchronization
task keeps running in the background. Passing `None` or a nonpositive timeout
opts out of the bound.

`setup_hook` runs before the WebSocket connects, so the guild cache can still be
empty and guild rows may not exist yet when plugin `on_load` hooks run. The same
synchronization runs again in `on_ready`, once guilds are cached, under the same
`guild_sync_timeout`; if that wait expires it is abandoned and continues in the
background.

## Backend Agnosticism

The `EasyCordDatabase` interface enforces a strict abstraction layer.
* Plugins should **never** execute raw SQL queries.
* All data access must go through methods like `db.get()`, `db.set()`, and `db.delete()`.
* Some built-in plugins persist their own JSON files independently of `Bot.db`. Setting `EASYCORD_DB_BACKEND=memory` does not make those files temporary. Generated community starters separate offline and live plugin directories, and generated tests change to a temporary working directory.

## Exception Infrastructure

* **Disk Exhaustion (SQLite):** If the host disk runs out of space, `sqlite3` can raise an `OperationalError`. EasyCord will propagate this exception up to the plugin layer. Plugins should implement `try/except` blocks for graceful failure.
* **Write-Locks (SQLite):** SQLite waits for a database lock up to its connection timeout; EasyCord does not implement an exponential-backoff retry policy. If the lock persists beyond the timeout, an exception is raised.
* **Connection Loss:** As SQLite is an embedded database, network connection loss is not applicable unless the database is stored on a disconnected network mount (which is heavily discouraged).

## Production Deployment Setup

For a production environment, use the following database configuration:
```python
import os
from easycord import Bot

bot = Bot(
    db_backend="sqlite",
    db_path="/data/bot.db", # Volume-mapped persistent storage
    db_auto_sync_guilds=True
)

bot.run(os.environ["DISCORD_TOKEN"])
```
Always ensure `/data` is backed up regularly.
