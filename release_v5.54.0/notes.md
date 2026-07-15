# EasyCord v5.54.0 Release Notes

## Config-Schema Phase 2 (Edge Cases & Migration Repair)

### Fixed Bugs

**BUG-A (CRITICAL):** Vacuous `ok` flag in `_doctor_report` now correctly reflects healing success.

**BUG-B (HIGH):** Non-integer `_v` stamps now reset to v1 with correction logged.

**BUG-C (HIGH):** Missing migration steps now logged as warnings instead of silently skipped.

**BUG-D (MEDIUM):** `--fix-configs` without bot target exits with error.

**BUG-F (MEDIUM):** Added warning that bot must be stopped before `--fix-configs`.

**BUG-G (MEDIUM):** Three new edge-case tests for `_v` handling.

**BUG-J,K (MEDIUM):** Falsy-but-valid config values now preserved in `update()` and `set_default()`.

### Hygiene & CodeQL Cleanup

- Removed 3 unnecessary lambda wrappers in `_bot_commands.py`
- Hoisted inline import in `test_config_schema.py`
- Dismissed 19 CodeQL false positives (bare except, unused imports, ineffectual statement)

### Cyclic Import Resolution

Promoted `_BotBase` to runtime import in 4 mixin files:
- `_bot_commands.py`
- `_bot_events.py`
- `_bot_guild.py`
- `_bot_plugins.py`

This resolves all 11 py/unsafe-cyclic-import CodeQL alerts (72–80, 104, 142). `_BotBase` is a pure annotation stub, safe to add to the MRO with no runtime impact.

## Test Coverage

- **Total tests:** 1535 (no regressions)
- **MRO verified:** Bot → _EventsMixin → _GuildMixin → _PluginsMixin → _CommandsMixin → _BotBase → discord.Client
- **All core functionality passes**

## Breaking Changes

None.

## Installation

```bash
pip install "https://github.com/rolling-codes/EasyCord/releases/download/v5.54.0/easycord-5.54.0-py3-none-any.whl"
```

Or update:

```bash
pip install --upgrade easycord
```
