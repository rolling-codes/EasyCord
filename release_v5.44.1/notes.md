## EasyCord v5.44.1 - 2026-06-14

Maintenance/patch release.

### Fixed
- Realigned in-repo version metadata (`pyproject.toml`, `easycord.__version__`, README badge/links, and `docs/getting-started.md`) with the published release line, which had drifted while still reporting `5.43.0`.

### Assets
- https://github.com/rolling-codes/EasyCord/releases/download/v5.44.1/easycord-5.44.1-py3-none-any.whl
- https://github.com/rolling-codes/EasyCord/releases/download/v5.44.1/easycord-5.44.1.tar.gz

### Verification
- `python scripts/check_release_metadata.py` - passed.
- `pytest tests/` - passed.
- `ruff check easycord tests --select E9,F63,F7,F82` - passed.
