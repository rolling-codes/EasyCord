## EasyCord v5.44.1 - 2026-06-14

Patch release: economy concurrency hardening, plugin type-safety fixes, and version-metadata realignment.

### Fixed
- Economy: transfers now load once, mutate both balances in memory, and persist with a single save under the per-guild lock, so a failed write can never leave a half-applied transfer (no lost currency).
- Economy: `/daily` records its outcome under the lock and replies only after releasing it, so Discord response latency no longer stalls the guild; `_get_config` is now a pure read that cannot clobber a concurrent balance update.
- Plugin type-safety: `guild_only` handlers assert `ctx.guild`/`ctx.user`, `suggestions` narrows the target channel to `TextChannel`/`Thread` before sending, and `reaction_roles` guards `self.bot.user` before reading its id.
- Starboard: removed duplicate archived-message helpers and fixed a misplaced slash import.
- Realigned in-repo version metadata (`pyproject.toml`, `easycord.__version__`, README badge/links, and `docs/getting-started.md`) with the published release line, which had drifted while still reporting `5.43.0`.

### Changed
- Public API: `PluginConfigManager` is now exported from `easycord.plugins`.

### Assets
- https://github.com/rolling-codes/EasyCord/releases/download/v5.44.1/easycord-5.44.1-py3-none-any.whl
- https://github.com/rolling-codes/EasyCord/releases/download/v5.44.1/easycord-5.44.1.tar.gz

### Verification
- `python scripts/check_release_metadata.py` - passed.
- `pytest tests/` - 540 passed.
- `ruff check easycord tests --select E9,F63,F7,F82` - passed.
