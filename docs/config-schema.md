# Plugin Config Schemas

EasyCord v5.53+ includes a versioned config schema system that eliminates the
`cfg.get("enabled", True)` defensive-default pattern. Once a plugin declares a
`ConfigSchema`, every call to `get_schema()` guarantees all expected keys are
present and all migrations have been applied.

## Declaring a schema

```python
from easycord.config_schema import ConfigSchema

_DEFAULTS = {
    "enabled": True,
    "channel_id": None,
    "threshold": 3,
}

# Module-level — one schema per plugin, reused across all guilds.
SCHEMA = ConfigSchema(key="myplugin", version=1, defaults=_DEFAULTS)
```

The `key` must match the string your plugin passes to
`PluginConfigManager.get()` / `update()`.

## Reading config through a schema

Replace `config.get(guild_id, key, _DEFAULTS)` with `config.get_schema(guild_id, SCHEMA)`:

```python
class MyPlugin(Plugin):
    def __init__(self):
        super().__init__()
        self.config = PluginConfigManager(".easycord/myplugin")

    async def _get_config(self, guild_id: int) -> dict:
        return await self.config.get_schema(guild_id, SCHEMA)
```

`get_schema` guarantees:

- All keys from `_DEFAULTS` are present (missing ones are backfilled).
- A `_v` version stamp is maintained automatically.
- The fast path (section already valid) is a pure read — no lock, no write.

## Schema migrations

When you add or rename fields, increment `version` and register a migration:

```python
SCHEMA = ConfigSchema(key="myplugin", version=2, defaults={
    **_DEFAULTS,
    "new_field": "default_value",
})

@SCHEMA.migration(from_version=1)
def _v1_to_v2(section: dict) -> dict:
    # Rename an old key, set a computed default, etc.
    return {**section, "new_field": section.pop("old_field", "default_value")}
```

Migrations are run step-wise: a guild at v1 reaching a v3 schema runs both
`_v1_to_v2` then `_v2_to_v3`. A section with no `_v` stamp is treated as
pre-schema version 1.

## Checking and healing configs

`easycord doctor` reports config drift without modifying files:

```bash
easycord doctor mybot:bot
```

To apply healing to all guild configs for plugins that expose `SCHEMA`:

```bash
easycord doctor --fix-configs mybot:bot
```

Healing writes are atomic (`.tmp` → rename), so an interrupted heal leaves a
`.tmp` file that `doctor` also detects and reports.

## apply() contract

`ConfigSchema.apply(section)` is a pure function — it never writes to disk.
It returns `(healed_section, changes)`:

| Input | Result |
|---|---|
| `None` or `{}` | Deep copy of defaults + `_v` stamp |
| Non-dict value | Replaced with defaults; reported in `changes` |
| Valid section (all keys, correct `_v`) | Returned as-is; `changes == []` |
| Partial section | Missing keys backfilled; `changes` lists each one |
| Outdated `_v` | Migrations run step-wise; `_v` updated |

Unknown keys (live data stored alongside settings) are always preserved.
