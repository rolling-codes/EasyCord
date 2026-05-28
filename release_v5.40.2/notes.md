## EasyCord v5.40.2 - 2026-05-28

### Fixed
- Added a release metadata checker that treats `pyproject.toml` as the canonical version source.
- Enforced consistency across `easycord.__version__`, README release links, CHANGELOG top heading, project URLs, and expected GitHub release asset names.
- Added focused tests for release metadata drift and connected the checker to GitHub Actions.
- Cleaned package manifest rules so published artifacts exclude tests, local caches, workflow files, release prep folders, scripts, and contributor-only files.

### Assets
- https://github.com/rolling-codes/EasyCord/releases/download/v5.40.2/easycord-5.40.2-py3-none-any.whl
- https://github.com/rolling-codes/EasyCord/releases/download/v5.40.2/easycord-5.40.2.tar.gz

### Verification
- `python scripts/check_release_metadata.py` - passed.
- `pytest -o cache_dir=.pytest_cache_codex tests/` - 517 passed.
- `python -m compileall -q easycord tests scripts` - passed.
