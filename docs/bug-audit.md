# Bug Audit — Config-Schema Phase 1 (PR #86 + CodeQL)

## Overview

Full audit of the config-schema system shipped in v5.54. Four sources — Sourcery, CodeRabbit,
GitHub Advanced Security (CodeQL), and internal explore agent — produced a combined 18 findings.
All CRITICAL and HIGH issues are fixed on branch `fix/config-schema-followup` (PR #88).

---

## Fixed Bugs

### BUG-A: Vacuous `ok` flag in `_doctor_report` schema-health check

**File:** `easycord/cli.py` · **Line:** 557 · **Severity:** CRITICAL  
**Source:** Sourcery, CodeRabbit  
`ok = fix_configs and _fixed >= 0` is always `True` when `--fix-configs` is used since `_fixed`
(a count) can never be negative. The doctor command would report success even when no configs
were actually healed. Fixed to `(_fixed >= len(schema_issues)) if fix_configs else False`.
Also updated the detail message to `"N of M guild config(s) healed"`.

### BUG-B: Non-integer `_v` stamp silently skips migrations forever

**File:** `easycord/config_schema.py` · **Line:** 96 · **Severity:** HIGH  
**Source:** Sourcery, CodeRabbit, Explore agent  
When a stored section has `_v: "2"` (string) instead of `_v: 2` (int) — e.g. from manual
editing or a legacy serializer — the `isinstance(current_v, int)` guard returns `False`.
All migrations are skipped AND the corrupt stamp is left in place, so every future `apply()`
call also silently skips migrations. Fixed by adding an `elif not isinstance(current_v, int):`
branch that resets `current_v = 1` and records the correction in `changes`.

### BUG-C: Missing migration step stamps `_v` as fully migrated

**File:** `easycord/config_schema.py` · **Lines:** 98–103 · **Severity:** HIGH  
**Source:** CodeRabbit  
When a plugin author bumps `schema.version` by more than 1 without registering all intermediate
migrations (e.g. schema at v3 but only `from_version=2` registered, section at `_v=1`), the
`while` loop silently no-ops the missing step but still stamps `_v = self._version`. The section
is marked as fully migrated when the v1→v2 transform never ran. Fixed by adding an
`else: logger.warning(...)` branch inside the while loop.

### BUG-D: `--fix-configs` without a bot target silently no-ops

**File:** `easycord/cli.py` · **Lines:** 731–735 · **Severity:** MEDIUM  
**Source:** CodeRabbit  
`cmd_doctor` passed `args.fix_configs` to `_doctor_report` unconditionally. When `--fix-configs`
was used without a `target`, `_doctor_report` skipped the entire `if target:` block with no
feedback to the user. Fixed with an early-exit guard: if `fix_configs and not target`, print an
error and return 1.

### BUG-F: No warning that bot must be stopped before `--fix-configs`

**File:** `easycord/cli.py` · **Lines:** 402–429 · **Severity:** MEDIUM  
**Source:** CodeRabbit  
`_apply_schema_fixes` reads and rewrites guild JSON files directly. A concurrent live-bot write
could be lost even though the `.tmp` → rename swap is atomic. No CLI help text or docstring
warned about this. Fixed by adding to the `--fix-configs` help string.

### BUG-G: Missing tests for `ConfigSchema.apply()` `_v` edge cases

**File:** `tests/test_config_schema.py` · **Severity:** MEDIUM  
**Source:** Sourcery, CodeRabbit  
No tests existed for: (1) non-int `_v` stamp, (2) missing migration step gap, (3) section with
`_v > schema.version` (forward-version). Three new tests added:
`test_apply_resets_non_int_v_and_migrates`, `test_apply_warns_on_missing_migration_step`,
`test_apply_ignores_forward_version`.

### BUG-J: `update()` falsy check silently discards falsy-but-valid sections

**File:** `easycord/plugins/_config_manager.py` · **Line:** 48 · **Severity:** MEDIUM  
**Source:** Explore agent  
`section = cfg.get_other(key) or {}` treats any falsy stored value (`[]`, `False`, `0`, `{}`)
as missing and starts fresh. Fixed to `if section is None: section = {}`.

### BUG-K: `set_default()` falsy check overwrites explicitly stored `{}`

**File:** `easycord/plugins/_config_manager.py` · **Line:** 90 · **Severity:** MEDIUM  
**Source:** Explore agent  
`if not cfg.get_other(key):` incorrectly treats a stored empty dict as absent. A plugin that
initializes a section to `{}` explicitly would have its section overwritten by defaults on the
next `set_default()` call. Fixed to `if cfg.get_other(key) is None:`.

---

## Forward-Version Detection (New Behaviour)

### DETECT-FV: Forward-version sections now log a warning and pass through unchanged

**File:** `easycord/config_schema.py` · **Lines:** 96–103 · **Severity:** Enhancement  
**Source:** Explore agent  
A section with `_v > schema.version` (e.g. written by a newer plugin version) previously passed
through silently with no `changes` and no log output. The schema gave callers no signal that
stored data was ahead of the current schema. Now logs `logger.warning(...)` and returns early
with `changes == []`, preserving the section exactly as stored.

---

## Deferred Issues

### DEFER-E: Double I/O scan in drift detection + `_apply_schema_fixes`

**File:** `easycord/cli.py` · **Lines:** 520–563 · **Severity:** MEDIUM  
**Source:** CodeRabbit  
When `fix_configs=True`, the drift-detection scan inside `_doctor_report` parses every guild
JSON file once, then `_apply_schema_fixes` parses all the same files a second time. No data
loss; purely a performance issue. A shared `_scan_schema_guilds()` generator would eliminate
the double pass. Deferred — refactor risk exceeds benefit for now.

### DEFER-H: `suggestions.py` `SCHEMA.key` shares slot with submission-entry data

**File:** `easycord/plugins/suggestions.py` · **Line:** 25 · **Severity:** LOW  
**Source:** CodeRabbit  
`SCHEMA.key = "suggestions"` governs plugin settings, but submitted suggestion entries are also
stored under `cfg.get_other("suggestions", {})`. `schema.apply()` preserves unknown keys, so no
data is lost. The risk is that `--fix-configs` rewrites the entire (potentially large) entries
blob on each heal. Deferred to phase 2: a SCHEMA v2 migration should move entries to
`"suggestions_data"`.

---

## CodeQL Security Alerts

### ALERT-141: Bare `except: pass` in `_bot_plugins.py` — FALSE POSITIVE

**File:** `easycord/_bot_plugins.py` · **Line:** 152 · **Alert:** `py/empty-except`  
CodeQL flagged this as an empty except clause. The actual code is `except ValueError: pass`,
guarding a `_registries.remove(_entry)` call where `ValueError` means the entry was already
absent. Intentional and correct. Not a bare `except:`.

### ALERT-72–80,104,142: Unsafe cyclic imports — ARCHITECTURAL PATTERN

**Files:** `easycord/bot.py`, `_bot_commands.py`, `_bot_plugins.py`, `_bot_guild.py`,
`_bot_events.py`, `_bot_base.py`  
**Alert:** `py/unsafe-cyclic-import` (11 alerts) · **Severity:** error (CodeQL)  
EasyCord uses a mixin-based bot decomposition where each `_bot_*.py` module inherits from
`_BotBase` and is assembled in `bot.py`. The circular structure is resolved at runtime via
`TYPE_CHECKING` guards and careful import ordering. CodeQL cannot reason about
`if TYPE_CHECKING:` blocks and flags all of them. These are architectural false positives.
Fixing them would require restructuring the entire bot composition model — out of scope for
this audit.

### ALERT-134: Ineffectual statement in `_plugin_scanner.py`

**File:** `easycord/_plugin_scanner.py` · **Line:** 29 · **Alert:** `py/ineffectual-statement`  
**Severity:** note. Low priority hygiene fix.

### ALERT-82–86: Unnecessary lambda wrappers in `_bot_commands.py`

**File:** `easycord/_bot_commands.py` · **Lines:** 146–318 · **Alert:** `py/unnecessary-lambda`  
Five lambdas that wrap a callable directly (e.g. `lambda x: f(x)` instead of `f`).  
**Severity:** note. Low priority hygiene fix.

### ALERT-67–71,101–103,135–138: Unused imports

**Files:** Multiple test and source files  
**Alert:** `py/unused-import` · **Severity:** note  
`asyncio`, `re`, `threading`, `truncate`, `MagicMock`, `pytest`, `AsyncMock` imported but
unused. Low priority hygiene cleanup.

---

## Summary

| Category | Count | Status |
|----------|-------|--------|
| CRITICAL bugs fixed | 1 | ✅ PR #88 |
| HIGH bugs fixed | 2 | ✅ PR #88 |
| MEDIUM bugs fixed | 5 | ✅ PR #88 |
| MEDIUM deferred | 2 | 📋 Phase 2 |
| CodeQL false positives | 12 | 🔕 Won't fix |
| CodeQL hygiene (note) | 9 | 📋 Backlog |
