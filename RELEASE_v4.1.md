# v4.1.0 — Localization Auto-Translate + Release Alignment

**Release Date:** 2026-04-28

## Summary

v4.1.0 introduces an optional automatic translation workflow for missing locale entries, adds fluent localization wiring in `Composer`, and aligns release metadata/documentation for the 4.1 line.

## What Changed

### Localization auto-translate

- `LocalizationManager` supports an optional `auto_translator` callback.
- Missing locale keys can now be translated on demand from a source locale and cached into the target locale catalog.
- Lookup order now prioritizes requested locale/guild locale, then auto-translation, then default locale fallback.

### Bot + Composer wiring

- `Bot(...)` now accepts `auto_translator=...` and can create a localization manager when either translations or an auto translator is configured.
- `Composer` gained fluent localization methods:
  - `.localization(manager)`
  - `.default_locale(locale)`
  - `.translations(catalogs)`
  - `.auto_translator(translator)`

### Release and license alignment

- Package version updated to **4.1.0** in `pyproject.toml`.
- README version badge updated to **v4.1.0**.
- README licensing text clarified for this release line: **MIT only**, no dual-license rollout in this release.

## Testing

- ✅ `pytest tests/test_i18n.py`
- ✅ `pytest tests/test_composer.py`
