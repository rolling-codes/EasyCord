# EasyCord v5.52.0 Release Notes

**Date:** July 3, 2026

## Overview

Feature release adding the Plugin Power Pack: three structural additions that close gaps compared to hikari/lightbulb and production-grade Discord bots — safe plugin load ordering, zero-config command analytics, and per-guild plugin toggling.

## New Features

### 1. Plugin Dependency Declarations

Declare load-order requirements directly on a `Plugin` subclass:

```python
class InventoryPlugin(Plugin):
    requires = ("economy",)
```

`bot.add_plugin(InventoryPlugin())` raises `PluginDependencyError` if `"economy"` is not already loaded. The error carries `.missing` (list of unmet deps) and `.plugin_class` (the class name) for programmatic handling.

```python
from easycord import PluginDependencyError

try:
    bot.add_plugin(InventoryPlugin())
except PluginDependencyError as e:
    print(f"{e.plugin_class} needs: {e.missing}")
```

### 2. Analytics Middleware

Track command invocation counts with one line:

```python
from easycord import analytics_middleware

bot.use(analytics_middleware())

# Later:
print(bot.command_stats())           # all guilds
print(bot.command_stats(guild_id=123))  # single guild
```

`AnalyticsStore` is also available directly for pre-populating or sharing a store across bot instances.

### 3. Per-Guild Plugin Feature Flags

Disable a plugin for a specific guild without unloading it:

```python
bot.disable_plugin("economy", guild_id=123)
# Commands from the economy plugin now return an ephemeral
# "This feature is disabled in this server." in guild 123.

bot.enable_plugin("economy", guild_id=123)   # re-enable
bot.is_plugin_enabled("economy", guild_id=123)  # → True
```

DM invocations are never blocked. Flags are in-memory — pair with `ServerConfigStore.mutate()` for persistence.

## Test Coverage

- 1438 tests total (up from 1335); 35 new tests for the Plugin Power Pack
- All CI gates passing: ruff (blocking + advisory), pytest, plugin coverage, release metadata

## Installation

```bash
pip install --upgrade easycord==5.52.0
```

Distributed as:
- `releases/download/v5.52.0/easycord-5.52.0-py3-none-any.whl`
- `releases/download/v5.52.0/easycord-5.52.0.tar.gz`

## Upgrade Notes

No breaking changes. Drop-in update from v5.51.0.
