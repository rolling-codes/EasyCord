# v4.3.1 - Localization Auto-Translator & Type Checking Bug Fixes

**Release Date:** 2026-05-01  
**Status:** ✅ Current Stable Release

---

## What's in This Release

### Fixed 🐛

- **Localization auto-translator source priority** — Auto-translator now correctly uses canonical catalog translations instead of ad-hoc fallback strings, ensuring consistent, correct translations across all languages
- **Type checking for slash command groups** — Fixed F821 "Undefined name 'SlashGroup'" error that blocked CI pipeline, now full static type analysis works

### Changed 🔄

- `LocalizationManager._find_source_for_key()` lookup order reversed — now checks canonical catalog first, then caller-provided defaults (was backwards)
- `_bot_commands.py` now uses `TYPE_CHECKING` guard for `SlashGroup` import — enables static type checkers without runtime circular dependency
- No breaking API changes — existing applications work unchanged

### Added ✨

- Comprehensive release notes documenting root causes and migration guidance
- Enhanced CLAUDE.md with i18n best practices and architecture patterns
- v4.4.0 localization roadmap for future enhancements

### How It's Convenient 🚀

- **Drop-in fix** — Update to v4.3.1, no code changes needed for most applications
- **Better translations** — Auto-translated content now matches your canonical translations perfectly
- **Cleaner CI/CD** — Type checking now passes immediately, no more `# type: ignore` comments needed
- **Production confidence** — 117 regression tests passing, zero known issues
- **Clear upgrade path** — Migration notes included for edge cases

---

## Summary

v4.3.1 is a patch release addressing two critical bugs in the localization system and type checking infrastructure. The localization auto-translator now correctly prioritizes canonical catalog entries over caller-provided defaults, ensuring consistent translation behavior. Type checking now passes for slash command group operations via a TYPE_CHECKING guard, eliminating F821 undefined-name errors in CI.

---

## Fixed

### 1. Localization Auto-Translator Source Priority Bug

**Issue:** The `LocalizationManager._find_source_for_key()` method prioritized caller-supplied `default` text over canonical catalog entries. This caused auto-translation to use ad-hoc fallback strings instead of actual registered translations, bypassing the application's translation infrastructure and producing inconsistent or incorrect translations.

**Impact:**
- Auto-translated content could differ from canonical translations
- User-provided fallback strings overrode business translations
- Localization consistency degraded when auto-translation was enabled
- Difficult to trace which text was from the catalog vs. user fallback

**Root Cause:** The preference order in `_find_source_for_key()` checked the caller-supplied `default` parameter before checking the default locale catalog chain, inverting the intended lookup hierarchy.

**Fix:** Reordered lookup priority to:
1. **Canonical catalog** (default locale chain) — application-owned translations
2. **Caller-supplied default** — final fallback only if translation not found
3. **Any registered locale** — last-resort scan across all registered locales

**Code Change:**
```python
# Before (buggy)
def _find_source_for_key(self, key, *, default):
    if default is not None:  # ❌ Checked default FIRST
        return self.default_locale, default
    for candidate in self.resolve_chain(self.default_locale):
        if key in self._catalogs.get(candidate, {}):
            return candidate, ...
    ...

# After (fixed)
def _find_source_for_key(self, key, *, default):
    for candidate in self.resolve_chain(self.default_locale):  # ✓ Checked catalog FIRST
        if key in self._catalogs.get(candidate, {}):
            return candidate, ...
    if default is not None:
        return self.default_locale, default
    ...
```

**Behavior Change:** Auto-translator now uses canonical translations as source text, not caller defaults. This ensures:
- Consistent translation chains across all locales
- Proper sourcing when translating into additional languages
- Alignment with application translation policies
- Accurate conversation history and audit trails

**Migration:** No code changes required for existing applications. If your code relies on the old (buggy) behavior of prioritizing caller defaults, update your code to pass translations via `LocalizationManager(translations={...})` instead.

**Testing:**
- `test_auto_translator_uses_default_text_when_key_missing_everywhere` now validates correct priority order
- All 6 i18n tests pass (locale registration, fallback chain, formatting, auto-translation)
- All 25 composition tests pass (bot localization wiring, composer fluent API, embed helpers)

---

### 2. Ruff Type Checking F821 "Undefined Name" Error

**Issue:** `SlashGroup` type annotation in `_bot_commands.py` caused Ruff static analysis to fail with `F821 Undefined name 'SlashGroup'`. This error prevented the CI linter-and-test workflow from running pytest, blocking all PR validations.

**Impact:**
- CI could not run tests on any PR touching bot commands or groups
- Type checker (Ruff) could not statically analyze command registration
- Developers had to silence type errors with `# type: ignore[name-defined]`
- No static verification of group argument types

**Root Cause:** `SlashGroup` was imported at module level after the `_CommandsMixin` class definition to avoid circular import at class definition time. Static type checkers run before runtime, so they don't see the late-time import when analyzing annotations in the class.

**Fix:** Added `TYPE_CHECKING` guard to make `SlashGroup` available to static type checkers without creating runtime circular dependency:

```python
# Before (buggy)
from typing import Callable, Union
# ... class definition ...
from .group import SlashGroup  # Late import hides from type checkers

class _CommandsMixin:
    def add_group(self, group: "SlashGroup") -> None:  # ❌ F821
        ...

# After (fixed)
from typing import TYPE_CHECKING, Callable, Union

if TYPE_CHECKING:
    from .group import SlashGroup  # ✓ Available to type checkers

class _CommandsMixin:
    def add_group(self, group: "SlashGroup") -> None:  # ✓ Type-checkable
        ...
```

**Behavior Change:** None. This is a type-checking-only change. Runtime behavior is identical because the actual `SlashGroup` import still happens after class definition.

**Benefits:**
- Ruff can now validate `SlashGroup` type annotations
- No more `# type: ignore` comments needed
- Full static type coverage for command group operations
- Faster CI feedback loop (type checking passes immediately)

**Testing:**
- Ruff check now passes for `_bot_commands.py`
- All 86 bot and group tests pass (add_group, add_groups, group names, guild scoping, nsfw/guild_only forwarding)
- No runtime regressions

---

## Changed

### LocalizationManager Behavior
- `_find_source_for_key()` now prioritizes canonical catalog entries (point 1 above)
- Auto-translator callback receives canonical translation text, not caller defaults
- This is a **silent behavior change**; update code if you were relying on old behavior

### Type Checking
- Ruff and other static type checkers can now fully analyze `_bot_commands.py` without errors
- Removed `# type: ignore[name-defined]` comments

---

## Compatibility

### Breaking Changes
None. The fixes do not change public APIs or alter behavior in ways that would break existing applications.

### Migration Notes
If your application:
- **Passes `default=` to `LocalizationManager.get()`**: No change needed. Behavior is now more predictable.
- **Provides auto-translator callback**: Update if you relied on receiving `default` text as source. Now receives canonical catalog text or the actual missing key value.
- **Uses `SlashGroup`**: No change needed. Type checking now works correctly.

---

## Testing & Validation

Ran:
```bash
# Localization tests
pytest tests/test_i18n.py -v

# Composition/bot tests
pytest tests/test_bot_localization.py tests/test_composer.py tests/test_embed_cards.py -v

# Command/group tests
pytest tests/test_bot.py tests/test_group.py -v
```

Results:
- 6/6 i18n tests passed
- 25/25 composition tests passed
- 86/86 bot & group tests passed
- **Total: 117/117 tests passed**

No type checking issues in `_bot_commands.py`.

---

## Release Notes

- Type checking infrastructure now supports full static analysis of bot command registration
- Localization auto-translator provides consistent, predictable behavior across language chains
- Small, focused patch with zero public API changes or new features

---

## Technical Details

### Localization Resolution Chain (Post-Fix)

When `LocalizationManager.get(key, locale=..., guild_locale=..., default=..., **format_kwargs)` is called:

1. **Check requested locales** (highest priority)
   - Interaction locale (if provided)
   - Guild locale (if provided)
   - Each with progressive language fallback (e.g., pt-BR → pt)

2. **Auto-translate if missing** (if auto-translator configured)
   - Find source text: canonical catalog > caller default > any catalog
   - Call auto-translator(source_text, source_locale, target_locale)
   - Cache result in target locale

3. **Check default locale chain**
   - Default locale and language fallbacks

4. **Fall back to default** (final)
   - If default parameter provided, use it
   - Otherwise, return the key itself

### Type Checking Resolution

- Module imports: `TYPE_CHECKING` block is **only evaluated by static type checkers**, not at runtime
- At runtime: `SlashGroup` is imported after class definition (no circular import)
- At type-check time: `SlashGroup` is available in the `if TYPE_CHECKING:` scope

This allows:
- Static verification of argument types
- No runtime import cycles
- Clean codebase without `# type: ignore` comments

---

## Contributors

- Bug fix: Localization priority order
- Bug fix: Type checking guard for SlashGroup

---

## Next Steps

- Monitor production for any localization behavior changes
- Update any custom auto-translator implementations to account for new source-text behavior
- Consider removing any `# type: ignore` comments from code that uses `SlashGroup`
