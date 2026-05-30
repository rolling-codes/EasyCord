## EasyCord v5.43.0 - 2026-05-30

### Added
- Python-first plugin authoring helpers in `easycord.plugin_creator`.
- Manifest validation for generated plugins using `easycord-plugin.json` schema version `1`.
- Reusable package scaffolds with `easycord.plugins` entry points.
- CLI wrappers: `easycord plugin create`, `easycord plugin check`, and `easycord plugin discover`.
- Plugin authoring documentation with local-safe testing defaults.

### Changed
- Config-driven bots now default to local SQLite storage when no database backend is configured.
- Generated runnable bot scaffolds keep command sync disabled by default; generated tests use memory storage.

### Assets
- https://github.com/rolling-codes/EasyCord/releases/download/v5.43.0/easycord-5.43.0-py3-none-any.whl
- https://github.com/rolling-codes/EasyCord/releases/download/v5.43.0/easycord-5.43.0.tar.gz

### Verification
- `python scripts/check_release_metadata.py` - passed.
- `pytest -o cache_dir=.pytest_cache_codex tests/` - 534 passed.
- `python -m compileall -q easycord tests scripts` - passed.
