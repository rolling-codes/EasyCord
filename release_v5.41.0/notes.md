# EasyCord v5.41.0 Release Notes

**Release Date:** 2026-05-29

## Summary

EasyCord v5.41.0 completes the Discord admin-facing configuration UI for four previously stubbed plugins and adds a shop system to the economy plugin. All new features are backward-compatible; existing bots will continue to work without modification.

## What's New

### Economy Shop System

The economy plugin now supports a shop system:

- **`/shop`** — View shop items with prices and descriptions
- **`/buy <item>`** — Purchase items using in-game currency
- New helper methods: `_get_shop_items()` and `_set_shop_items()`

Configure shop items programmatically via the ServerConfigStore:
```python
cfg_obj = await plugin.config.store.load(guild_id)
shop = {
    "rare_sword": {"price": 500, "description": "Legendary blade"},
    "shield": {"price": 300, "description": "Strong defense"}
}
cfg_obj.set_other("shop_items", shop)
await plugin.config.store.save(cfg_obj)
```

### Plugin Admin Commands

Four plugins now have complete Discord admin-facing configuration commands:

**AutoResponderPlugin**
- `/responder_add <keyword> <response>` — Add literal keyword trigger
- `/responder_add_regex <pattern> <response>` — Add regex trigger
- `/responder_list` — View all triggers
- `/responder_remove <keyword>` — Remove trigger

**MemberLoggingPlugin**
- `/member_log_channel <#channel>` — Set log destination
- `/member_log_config` — View configuration

**InviteTrackerPlugin**
- `/invite_log_channel <#channel>` — Set log destination
- `/invite_tracker_config` — View configuration

**ReactionRolesPlugin**
- `/reaction_role_set <message_id> <emoji> <role>` — Create mapping
- `/reaction_role_list <message_id>` — View mappings
- `/reaction_role_remove <message_id> <emoji>` — Delete mapping

All 11 admin commands require the `manage_guild` permission and work only in guild contexts (via `@slash(guild_only=True)` decorator).

### LocalizationManager Path Support

The `LocalizationManager.register()` method now accepts file paths:

```python
from pathlib import Path

mgr = LocalizationManager()
# Register from file
mgr.register("es", Path("locales/es.json"))
# Or from string path
mgr.register("fr", "locales/fr.json")
# Still supports dict-like mappings
mgr.register("en", {"hello": "Hello!"})
```

JSON files must contain a root object (not arrays or scalars) and be valid UTF-8. Missing files, invalid JSON, and non-object roots raise clear exceptions.

## Breaking Changes

None. This is a minor version bump; all existing code is backward-compatible.

## Fixes

- **Economy leaderboard collision**: Renamed `/leaderboard` → `/economy_leaderboard` to avoid conflict with LevelsPlugin
- **Economy shop safety**: `/shop` and `/buy` now safely handle shop items with missing "price" keys
- **Localization error clarity**: File path errors now include the file path and distinguish between missing files, JSON syntax errors, and non-object roots

## Known Limitations

- Economy `/buy` is not atomic under concurrent access. Both purchasers might pass the balance check before either deduction writes. Recommend per-guild application locks if this affects your use case.

## Migration Notes

No action required. Existing bots will work unmodified.

If you were manually editing config files to configure these plugins, you can now use the `/` commands in Discord instead. For the economy shop, configure items programmatically or via a future admin UI.

## Assets

- **Wheel:** [easycord-5.41.0-py3-none-any.whl](https://github.com/rolling-codes/EasyCord/releases/download/v5.41.0/easycord-5.41.0-py3-none-any.whl)
- **Source:** [easycord-5.41.0.tar.gz](https://github.com/rolling-codes/EasyCord/releases/download/v5.41.0/easycord-5.41.0.tar.gz)

## Verification

- **Tested on:** Python 3.14.0rc3, 3.13.x, 3.12.x — all versions pass
- **544 tests pass** (27 new tests added for shop system, localization file-path loading, admin commands, and runtime validation; all existing 517 tests still pass)
- **New tests added:**
  - `tests/test_plugin_logic.py`: 21 new tests
    - TestEconomyShop: 11 tests (shop persistence, item display, purchase validation)
    - TestPluginAdminCommands: 6 tests (command existence, error handling)
    - TestV541RuntimeValidation: 4 tests (SQLite persistence, decorator validation, atomic operation risk)
  - `tests/test_i18n.py`: 6 new tests (file-path loading validation)
- `python -m compileall -q easycord tests scripts` — passed on all Python versions
- Release metadata check — passed
- **Runtime validation completed:**
  - ✅ Shop item persistence verified across reload cycles
  - ✅ Guild-only decorator applied to all 11 admin commands
  - ✅ Permission enforcement decorators verified
  - ✅ Concurrent balance operation race condition documented
