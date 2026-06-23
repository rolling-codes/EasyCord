# EasyCord v5.50.0 Release Notes

Architecture release — EventBus, HookRegistry, `@deprecated`, TTL cooldowns, bot permission validator, AI provider metrics, and 28 new tests.

---

## Added

### EventBus — async pub/sub between plugins

```python
# Plugin A publishes
await bot.event_bus.publish("user_leveled_up", user_id=ctx.user.id, level=new_level)

# Plugin B subscribes
async def on_level_up(user_id: int, level: int) -> None:
    await announce_channel.send(f"<@{user_id}> reached level {level}!")

bot.event_bus.subscribe("user_leveled_up", on_level_up)
```

Exceptions in one listener do not affect others — each subscriber is isolated.

---

### HookRegistry — lifecycle hooks

```python
async def log_before(ctx, name: str) -> None:
    print(f"/{name} invoked by {ctx.user}")

bot.hooks.register("before_command", log_before)
```

Four built-in hooks: `before_command`, `after_command`, `on_plugin_load`, `on_plugin_unload`.

---

### `@deprecated` and `@version_introduced`

```python
from easycord import deprecated, version_introduced

@deprecated("5.50.0", replacement="new_feature")
def old_feature():
    ...
# → DeprecationWarning: old_feature is deprecated since v5.50.0. Use new_feature instead.

@version_introduced("5.50.0")
def new_feature():
    ...
```

---

### Bot permission validator

At `on_ready`, EasyCord warns if the bot lacks a permission required by any loaded command:

```
WARNING easycord: Plugin 'ModerationPlugin' requires 'ban_members' permission but bot
lacks it in guild 'My Server' (ID: 123456789) — command /ban may not work as expected
```

---

### AI provider fallback metrics

```
DEBUG  easycord.orchestrator: AI request: trying provider ClaudeProvider (attempt 1/2)
WARNING easycord.orchestrator: AI provider ClaudeProvider failed (RateLimitError: …), falling back to next
DEBUG  easycord.orchestrator: AI request handled by provider OpenAIProvider
```

---

## Fixed

- `format_number`: O(n²) `list.insert(0, …)` replaced with O(n) append + reversed join
- Conversation summarization failures now log a WARNING instead of silently swallowing the exception
- Hot-reload watcher poll: 1 s → 3 s
- `BirthdayPlugin` role-removal tasks are now tracked in `_role_tasks` and cancelled on unload
- `asyncio.iscoroutinefunction` (deprecated in Python 3.16) replaced with `inspect.iscoroutinefunction`
- CodeQL "statement has no effect" finding in `test_hot_reload.py` resolved
- Release-drafter no longer re-triggers on version-bump commits to `main`

---

## Install

```bash
# Wheel
pip install "https://github.com/rolling-codes/EasyCord/releases/download/v5.50.0/easycord-5.50.0-py3-none-any.whl"

# Source distribution
pip install "https://github.com/rolling-codes/EasyCord/releases/download/v5.50.0/easycord-5.50.0.tar.gz"
```
