# EasyCord v5.44.3 — Release Notes

**Date:** 2026-06-14

## Summary

Patch release resolving all outstanding Pylance type errors surfaced after v5.44.2 and expanding test coverage by 110 tests.

## Bug Fixes

### `easycord/context_builder.py`
- `ContextMenu` commands have no `description` attribute. `_format_commands` now uses `getattr(cmd, 'description', None)` to avoid `AttributeError` at runtime.

### `easycord/i18n.py`
- `_metrics` dictionary contains a `locale_frequency` key whose value is a nested `dict`, not an `int`. The annotation has been updated from `dict[str, int]` to `dict[str, Any]`.
- `_chain_cache` uses `(str|None, str|None, bool)` tuples as keys, not plain strings. The annotation has been corrected from `dict[str, list[str]]` to `dict[tuple, list[str]]`.

### `easycord/plugins/invite_tracker.py`
- `discord.Invite.uses` is typed `int | None`. Both write sites now use `invite.uses or 0` to produce a plain `int`.
- `guild.get_channel()` can return a `ForumChannel` or `CategoryChannel` which have no `.send()` method. Added `isinstance(channel, (TextChannel, Thread, VoiceChannel, StageChannel))` guard before calling `.send()`.

### `easycord/plugins/member_logging.py`
- Same `isinstance` narrowing applied before `channel.send()`.

## Test Expansion (+110 tests, total 744)

| File | Tests | Coverage target |
|------|-------|-----------------|
| `tests/test_new_stress.py` | 19 | Concurrency/load: `rate_limit`, `ConversationMemory`, `LocalizationManager` |
| `tests/test_plugins_new.py` | 54 | 8 plugins: starboard, suggestions, reaction_roles, moderation, polls, tags, invite_tracker, member_logging |
| `tests/test_core_gaps.py` | 38 | Core modules: `EmbedCard`, formatters, `ContextBuilder`, `SlashGroup`, `SecurityManager`, `FrameworkManager`, `AuditLog` |

## Assets

- `dist/easycord-5.44.3-py3-none-any.whl`
- `dist/easycord-5.44.3.tar.gz`

## Install

```bash
pip install "https://github.com/rolling-codes/EasyCord/releases/download/v5.44.3/easycord-5.44.3-py3-none-any.whl"
```
