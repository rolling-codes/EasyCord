## EasyCord v5.40.1 - 2026-05-27

### Fixed
- Updated the runtime dependency to `discord.py>=2.7.1,<3`.
- Verified current Discord app-command metadata paths including allowed contexts, allowed installs, install-type helpers, context menus, groups, app context, entitlements, locale, and guild locale.
- Added non-SQL memory database startup paths via `Bot(db_backend="memory")`, `Bot(database=MemoryDatabase())`, and `EASYCORD_DB_BACKEND=memory`.
- Updated generated starter/test templates to use memory storage where persistence is unnecessary.
- Closed SQLite test fixtures cleanly so strict `ResourceWarning` checks stay quiet.
- Stabilized level-up tests on fresh CI runners by resetting XP cooldowns with an expired sentinel.
- Repaired the i18n performance regression workflow by adding `scripts/benchmark_i18n.py` and fixing benchmark baseline cache paths.
- Added release-readiness checks for the real GitHub wheel and source distribution asset names.

### Compatibility
- SQLite remains the persistent default database backend.
- Memory storage is recommended for tests, generated projects, and ephemeral bots.
- Python support remains `>=3.10`.

### Assets
- https://github.com/rolling-codes/EasyCord/releases/download/v5.40.1/easycord-5.40.1-py3-none-any.whl
- https://github.com/rolling-codes/EasyCord/releases/download/v5.40.1/easycord-5.40.1.tar.gz

### Verification
- Python 3.11.9 via `py -3.11`.
- `discord.py 2.7.1` in `.venv311`.
- `ruff check easycord tests --select E9,F63,F7,F82` - passed.
- `pytest tests/` - 515 passed.
- `scripts/benchmark_i18n.py` - passed under thresholds.
- `python -m build` - passed.
- `python -m twine check dist/*` - passed.
- Earlier Python environment checks also passed:
  - `pytest tests/` - 515 passed.
  - `pytest tests/ -W error::ResourceWarning` - 515 passed.
  - `python -X tracemalloc=10 -m pytest tests/ -W always::ResourceWarning` - 515 passed, no warnings.
  - `ruff check .` - passed.
  - `compileall` - passed.
  - `git diff --check` - passed.
  - CodeRabbit review - 0 issues.
