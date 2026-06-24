# EasyCord v5.50.1 Release Notes

Bugfix release. Closes a governance gap in `AIModeratorPlugin` where the live moderation path bypassed the plugin's own rate limiting and error handling, corrects two documentation mismatches, and adds the plugin's first behavioral test coverage.

---

## Fixed

### AIModeratorPlugin — destructive actions now run through the governed path

`AIModeratorPlugin` defined a `_execute_action` helper that owns per-user rate limiting (warn / timeout) and `discord.Forbidden` handling — but the live `on_message` handler never called it. It performed inline Discord calls instead, so warnings/timeouts were never rate-limited and an `auto_delete` could raise a failed `message.delete()` straight into the event dispatcher.

The event path now routes every destructive action through `_execute_action`:

```python
# A failed delete (message already gone, missing permission) is now contained,
# not raised into the dispatcher:
if action_level == "auto_delete" and confidence >= 0.95:
    await self._execute_action(message, "delete", reason)

# Warnings/timeouts are subject to the per-user limiters that were bypassed before:
elif action_level == "warn" or action_level == "auto_delete":
    await self._execute_action(message, "warn", reason)
```

**Behavior change:** a warning is now posted **in-channel** (rate-limited) instead of a best-effort DM, matching the governed action path.

### Documentation drift

- `docs/builtin-plugins.md` listed a `/purge` command for `ModerationPlugin` that is not implemented — removed.
- `context/architecture.md` listed the OpenClaw commands as `/openclaw_task` / `/openclaw_stop`; the registered names are `/openclaw`, `/openclaw-task`, `/openclaw-status`, `/openclaw-stop`, `/openclaw-history` — corrected.

---

## Tests

Added [`tests/test_ai_moderator.py`](https://github.com/rolling-codes/EasyCord/blob/main/tests/test_ai_moderator.py) — the plugin's first behavioral coverage (7 tests): auto-delete guarding, warn rate-limiting, timeout rate-limiting and `discord.Forbidden` handling, and malformed-model-output resilience.

```python
async def test_warn_blocked_when_limiter_exhausted(tmp_path):
    plugin = _make_plugin(tmp_path, _orchestrator("warn", 0.9))
    await plugin._update_config(GUILD, enabled=True, action_level="warn")
    msg = _make_message()

    limit = RateLimit(max_calls=10, window_minutes=60)
    for _ in range(10):
        await plugin.warn_limiter.check_limit(AUTHOR, "warn", limit)

    await plugin._on_message(msg)

    # No warn is delivered once the per-user budget is spent.
    assert msg.author.send.call_count == 0
    assert msg.channel.send.call_count == 0
```

---

## Install

```bash
# Wheel
pip install "https://github.com/rolling-codes/EasyCord/releases/download/v5.50.1/easycord-5.50.1-py3-none-any.whl"

# Source distribution
pip install "https://github.com/rolling-codes/EasyCord/releases/download/v5.50.1/easycord-5.50.1.tar.gz"
```
