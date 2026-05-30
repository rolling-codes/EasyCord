# EasyCord v5.42.0 Release Notes

## What's New

### Plugin Configuration Management (14 New Admin Commands)

All bundled plugins now have dedicated Discord commands for configuration:

- **Suggestions**: `/set_suggestions_channel` — configure where suggestions are posted
- **Moderation**: `/set_audit_channel`, `/set_mute_role`, `/clear_warnings` — audit logging and warning management
- **AI Moderator**: `/set_mod_review_channel`, `/set_mod_audit_channel` — review channel configuration
- **Levels**: `/remove_level_role`, `/set_levelup_channel` — level role and announcement channel management
- **Role Persistence**: `/saved_roles`, `/clear_saved_roles` — visibility and cleanup for saved roles
- **Economy**: `/shop_add`, `/shop_remove` — populate shop items from Discord (previously required database edits)
- **Starboard**: `/starboard_toggle` — enable/disable message archival

### Auto-Healing Configurations

Plugins now self-heal when channels are deleted or members are banned:

- Deleted log channels are automatically cleared from config (no more persistent warnings)
- Deleted starboard channels clean up orphan posts
- Banned members' roles are no longer auto-restored

### Observability Enhancements

- **Full tracebacks** logged when OpenClaw tasks fail (debug with stack traces, not just error strings)
- **Smart logging** in InviteTrackerPlugin (permission denied warnings log once per guild, not on every member join)
- **Live poll counters** in PollsPlugin (Discord native relative timestamp `<t:...:R>` replaces static "Closes in X seconds")
- **DM failure logging** in AIModeratorPlugin (notifies when user has DMs disabled)
- **Conversation history API** for multi-turn AI interactions (`ctx.conversation_messages()`)

### Atomicity & Safety

- **Economy `/buy` is now atomic per-guild** (asyncio.Lock prevents balance race conditions on concurrent purchases)
- **Moderation audit logging now consistent** (auto-mute from `/warn` logs to audit channel like manual `/mute`)

## Testing

- All 544 tests pass
- No breaking changes
- Compile check passed (`python -m compileall -q easycord tests scripts`)
- All new commands require `manage_guild` permission

## Upgrade Instructions

### Download

Download the release assets:
- **Wheel**: https://github.com/rolling-codes/EasyCord/releases/download/v5.42.0/easycord-5.42.0-py3-none-any.whl
- **Source**: https://github.com/rolling-codes/EasyCord/releases/download/v5.42.0/easycord-5.42.0.tar.gz

### Install

```bash
pip install --upgrade easycord
```

Existing bots work without changes. Optionally use new admin commands to configure plugins via Discord instead of config files.

## Known Limitations

- Economy shop still lacks global transactional guarantees (balance read-check-deduct are atomic per-guild only)

---

**Questions?** See [docs/](../docs/), [CLAUDE.md](../CLAUDE.md), or [examples/](../examples/).
