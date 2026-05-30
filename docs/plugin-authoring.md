# Plugin Authoring Helpers

EasyCord's plugin authoring helpers create, validate, and discover plugin
projects without connecting to Discord. Prefer the Python API for automation;
the CLI commands are thin wrappers around the same helpers.

## Python API first

```python
from pathlib import Path

from easycord import (
    check_plugin_project,
    create_package_plugin,
    load_plugin_manifest,
    validate_plugin_manifest,
)

result = create_package_plugin(
    name="greetings",
    target=Path("easycord-greetings"),
    author="EasyCord Developer",
)

manifest = load_plugin_manifest(result.manifest_path)
report = validate_plugin_manifest(manifest)
assert report.ok, report.to_dict()

check = check_plugin_project(result.target)
assert check.ok, check.to_dict()
```

The public helper types are:

- `PluginManifest`: normalized metadata loaded from the plugin manifest.
- `PluginScaffoldOptions`: scaffold settings such as name, scaffold mode, and
  target path.
- `PluginScaffoldResult`: generated file paths and manifest location returned
  by scaffold helpers.
- `PluginCheck`: one validation finding with severity, code, and message.
- `PluginCheckReport`: grouped checks, summary, and `ok` status for validation.

The public helper functions are:

- `create_in_project_plugin(...)`: create a plugin module inside an existing
  bot project.
- `create_package_plugin(...)`: create a distributable plugin package.
- `create_plugin_scaffold(...)`: lower-level scaffold helper used by both
  creation modes.
- `load_plugin_manifest(...)`: read and normalize plugin manifest metadata.
- `validate_plugin_manifest(...)`: validate manifest fields before packaging.
- `check_plugin_project(...)`: run manifest, import, and layout checks.
- `discover_plugins(...)`: list installed plugin entry-point metadata without
  importing plugin code.
- `load_entrypoint_plugins(...)`: load installed plugins from entry points.

Generated plugin projects include a JSON manifest by default. Keep it
committed: `check_plugin_project(...)` and package publishing use it as the
source of truth for plugin name, class, import path, version, and description.

## Runtime defaults

Generated runnable bots use EasyCord's default local storage when no database
backend is configured. That means a bot can start with local SQLite storage and
does not require an external database connection. Generated tests stay
disposable and use memory storage:

```python
from easycord import Bot

bot = Bot(auto_sync=False, db_backend="memory")
```

`auto_sync=False` prevents local imports, checks, and tests from syncing
commands to Discord. `db_backend="memory"` keeps test runs from writing local
data files.

## Package discovery

Distributable plugins should expose entry points in the `easycord.plugins`
group:

```toml
[project.entry-points."easycord.plugins"]
greetings = "easycord_greetings.plugin:GreetingsPlugin"
```

Applications can load installed package plugins with:

```python
from easycord import Bot, load_entrypoint_plugins

bot = Bot(auto_sync=False)
for plugin in load_entrypoint_plugins():
    bot.add_plugin(plugin)
```

## CLI wrappers

Use the CLI for quick local work:

```bash
easycord plugin create greetings
easycord plugin check .
easycord plugin discover --json
```

These commands call the same scaffold, check, and discovery helpers described
above. Use the Python API when you need custom paths, CI integration, or richer
report handling.
