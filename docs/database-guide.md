# Production Database Readiness

This guide outlines the performance and scalability characteristics of the EasyCord database abstraction layer, specifically focusing on `SQLiteDatabase` and `MemoryDatabase`.

## Connection Lifecycle & Concurrency

* **SQLiteDatabase:** Uses the `aiosqlite` library which operates with an active connection pool. While SQLite itself uses file-level locking for writes, `aiosqlite` ensures that concurrent multi-guild write bursts are queued and processed asynchronously without blocking the main event loop. However, under heavy sustained write bursts across 100+ guilds, you may experience increased query latency.
* **MemoryDatabase:** Stores all records in standard Python dictionaries. It is entirely single-threaded and executes synchronously, making it extremely fast but volatile (data is lost on restart).

## Guild Sync Blocking Behaviors

When `db_auto_sync_guilds=True` is enabled, the bot synchronizes guild state during the `on_ready` gateway event.
* **Behavior:** This synchronization task is dispatched asynchronously. It does *not* block the core gateway `on_ready` loop.
* **Timeout Mitigation:** Because it runs in the background, a massive database synchronization task (e.g., syncing 5,000 guilds) will not trigger Discord's 30-second gateway timeout.

## Backend Agnosticism

The `EasyCordDatabase` interface enforces a strict abstraction layer.
* Plugins should **never** execute raw SQL queries.
* All data access must go through methods like `db.get_record()`, `db.set_record()`, and `db.delete_record()`.
* **Verification:** Built-in plugins have been audited and verified to safely execute on both `MemoryDatabase` and `SQLiteDatabase` variants without hardcoded engine assumptions.

## Exception Infrastructure

* **Disk Exhaustion (SQLite):** If the host disk runs out of space, `aiosqlite` will raise an `OperationalError`. EasyCord will propagate this exception up to the plugin layer. Plugins should implement `try/except` blocks for graceful failure.
* **Write-Locks (SQLite):** `aiosqlite` handles database locks implicitly via exponential backoff retries (up to a default timeout of 5 seconds). If the lock persists beyond the timeout, an exception is raised.
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
