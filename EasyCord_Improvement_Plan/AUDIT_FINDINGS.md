# Deep Forensic Audit: EasyCord Findings

## Undocumented Risks

### 1. **LocalizationManager NOT Thread-Safe** ⚠️ HIGH
**File:** `easycord/i18n.py:32-36`
```python
class LocalizationManager:
    """...
    Thread Safety:
    This class is NOT thread-safe. It assumes single-threaded access within
    a request/event scope. Metrics and diagnostics state use non-atomic counters.
    For concurrent access (e.g., sharded deployments, async locale providers),
    external synchronization is required.
    """
```

**Impact:** If a bot uses sharding or has multiple event loop instances, concurrent locale lookups will corrupt `_metrics` counters and potentially lose diagnostics data. No error is raised—data corruption is silent.

**Users affected:** Anyone deploying with `track_metrics=True` on sharded bots.

**Fix:** Add `asyncio.Lock` around metrics updates, or document that `track_metrics` is incompatible with sharding.

---

### 2. **Hot-Reload Command Dispatch Race** ⚠️ MEDIUM
**File:** `easycord/_bot_plugins.py:222-225`
```python
await self.remove_plugin(plugin)      # Unregisters all commands
self.add_plugin(new_instance)          # Re-registers commands
await new_instance.on_reload()         # Calls lifecycle hook
```

**Gap:** Between `remove_plugin` and `add_plugin`, if a user invokes a command, it's unregistered but still routable by Discord (Discord caches command tree). The interaction lands in the command router but the callback is missing → likely 500 error or silent fail.

**Test coverage:** `test_hot_reload.py` exists but doesn't test concurrent command invocation during reload window.

**Fix:** Add lock to serialize hot-reload with command dispatch, or defer `remove_plugin` until `on_reload` completes.

---

### 3. **Database.auto_sync_guilds Blocking on_ready** ⚠️ MEDIUM
**File:** `easycord/bot.py:354-357`
```python
async def setup_hook(self) -> None:
    await self.db.ensure_schema()
    if self.db.auto_sync_guilds:
        await self.db.sync_guilds([guild.id for guild in getattr(self, "guilds", [])])
```

**Gap:** If bot is in 1000+ guilds and syncs on startup, `sync_guilds` is a full table scan (all guild records). No timeout or progress reporting. `on_ready` waits for this to complete.

**Symptom:** Bot appears frozen for 30+ seconds on startup with large guild counts.

**Documented:** No warning in docs about this sync cost.

**Fix:** Async fire-and-forget, or add progress logging + configurable timeout.

---

### 4. **Permission Checks Don't Validate Bot Permissions** ⚠️ MEDIUM
**File:** `easycord/_command_callbacks.py:115-149`
```python
if effective_permissions:
    if not ctx.guild:
        # return guild-only error
    member = ctx.guild.get_member(ctx.user.id)
    if not member:
        # return permission unverified error
    missing = [p for p in effective_permissions if not getattr(member.guild_permissions, p, False)]
    if missing:
        # return missing permissions error
```

**Gap:** This checks **user permissions**, not **bot permissions**. A command marked `require_admin=True` will allow a non-admin to invoke it if the bot lacks admin perms (the command execution will fail silently or raise `Forbidden`).

**Example:**
```python
@bot.slash(require_admin=True)  # User must be admin
async def kick(ctx, member: discord.Member):  # Bot must have kick perm
    await member.kick()
```

If user is admin but bot lacks "kick_members", the command executes, `member.kick()` raises `Forbidden`, and error handler catches it.

**Fix:** Validate bot's own permissions at command registration (as done in Permission Validator at `on_ready`), not at dispatch time.

---

### 5. **Cooldown Stale Entry Pruning Is Conservative** ⚠️ LOW
**File:** `easycord/_command_callbacks.py:32-46`
```python
max_age = max(cooldown_window, _COOLDOWN_TTL)  # _COOLDOWN_TTL = 3600.0
# ...
if all(now - ts >= max_age for ts in timestamps):  # ALL timestamps old
    cooldown_last_used.pop(key, None)
```

**Gap:** For a user with `cooldown_rate=5` on a 10-second cooldown:
- After 1st invocation: `timestamps = [T]`
- After 5 invocations in 10s: `timestamps = [T, T+2s, T+4s, T+6s, T+8s]`
- An entry is pruned only when **all 5 timestamps** are >1 hour old

For high-rate commands (rate=50), stale buckets accumulate for 50+ hours.

**Impact:** Memory growth, especially for bots with 100+ commands and varying cooldowns.

**Mitigation:** Existing sweep loop handles this, but pruning is O(n) dict iteration every 10 minutes.

**Fix:** Use heap-based TTL queue or document expected memory footprint.

---

### 6. **EventBus and HookRegistry Are Unordered Collections** ⚠️ MEDIUM
**File:** `easycord/event_bus.py:14`, `easycord/hooks.py`
```python
self._listeners: dict[str, list[Callable[..., Any]]] = {}
```

**Gap:** Order of listener execution is **insertion order** (Python 3.7+ dict guarantee), but:
1. No documented guarantee that order is preserved
2. Plugin load order is not guaranteed to be deterministic across restarts (file system order varies)
3. If PluginA emits event that PluginB listens for, and PluginB loads after PluginA, PluginA's emits go unseen until reload

**Example:**
```python
class PluginA(Plugin):
    @on("ready")
    async def init(self):
        await self.bot.event_bus.publish("setup_complete")  # PluginB hasn't subscribed yet

class PluginB(Plugin):
    async def on_load(self):
        self.bot.event_bus.subscribe("setup_complete", self.configure)  # Subscribes after PluginA fired
```

**Fix:** Document plugin load order or add registration phase before event emission.

---

### 7. **Conversation Memory Eviction Is Unspecified** ⚠️ MEDIUM
**File:** `easycord/conversation_memory.py`
No clear documentation on:
- What happens when token count exceeds provider limit?
- Is it FIFO eviction or LRU?
- Does eviction trigger a callback to warn the user?

**User Risk:** Silent context truncation mid-conversation with no warning.

**Fix:** Add `ConversationMemory` config options for eviction strategy and add debug logging.

---

### 8. **ToolLimiter Is Async but Not Awaited Consistently** ⚠️ LOW
**File:** `easycord/tool_limits.py` and plugin usage
```python
allowed, _ = await limiter.check_limit(user_id, tool_name, limit)  # await required
```

But docs show:
```python
if not await limiter.check_limit(user_id, tool_name, limit):
    return False
```

**Gap:** If someone forgets `await`, they get a coroutine object, not a boolean. The check silently passes (coroutine is truthy).

**Fix:** Consider sync wrapper or add runtime validation in `check_limit`.

---

### 9. **Component TTL Boundary (FIXED in v5.50.2, But Document the Fix)**
**File:** `easycord/registry.py:379`
```python
return entry.expires_at is None or entry.expires_at > time.time()
```

**History:** v5.50.2 fixed off-by-one bug where `expires_at >= now` would return expired components on coarse-grained clocks (Windows ~15ms ticks).

**Current:** Strict boundary is correct. But this is a latent class of bugs: any TTL expiry logic is clock-sensitive.

**Recommendation:** Add test with mocked `time.time()` to catch regressions.

---

### 10. **Database Schema Assumptions Not Validated** ⚠️ MEDIUM
**File:** `easycord/database.py`
No validation that plugins' assumed tables actually exist before on_ready fires.

**Scenario:**
1. Bot starts with MemoryDatabase (default, no schema)
2. Plugins call `bot.db.load()` in `on_ready()` expecting SQLite schema
3. MemoryDatabase has empty storage → all queries fail silently or raise AttributeError

**Fix:** Add explicit schema init check, or document that DB backend must match plugin expectations.

---

## Performance Concerns

### 11. **Interaction Registry Regex Compilation Happens On-Demand**
**File:** `easycord/registry.py` component routing
```python
candidate.regex = re.compile(...)  # Compiled when first accessed
```

**Gap:** For 1000 component handlers with patterns, first call to `resolve_component()` compiles all regex lazily. Causes jitter on first button press.

**Fix:** Pre-compile at registration, not at resolution.

---

### 12. **EventBus.publish Uses asyncio.gather(..., return_exceptions=True)**
Every event publish creates a task list, gathers them, and checks for exceptions. For 100 listeners × 10 events/sec = 1000 gather calls/sec.

**Fix:** Profile under load; consider batch collection or task pooling.

---

## Undocumented Assumptions

| Assumption | Where Enforced | Risk |
|---|---|---|
| Plugin `__init__` takes no required args | `_hot_reload_plugin` auto-reject | Auto-reload fails silently if args needed |
| `ctx.guild` is never None in guild-only commands | Permission checks | BUG if guild is evicted mid-command |
| Database backend is consistent throughout bot lifetime | Bot.__init__ | Switching db_backend on running instance breaks all plugins |
| All plugins load before on_ready | `setup_hook` → `add_plugin` → `on_ready` | Late plugin add sees stale bot state |
| `member.guild_permissions` reflects current state | Cached on member fetch | Permission changes mid-session not reflected |

---

## Test Coverage Gaps

| Area | Current | Gap |
|---|---|---|
| Concurrent plugin load/unload | `test_stress.py` | Race condition during hot-reload + command dispatch not tested |
| Database consistency | `test_database.py` | No migration/upgrade scenario; no corruption recovery |
| Locale fallback chains | `test_i18n.py` | No test for concurrent metric updates on sharded bot |
| Component TTL with time.time() mocking | N/A | All TTL tests use real time; clock skew not tested |
| EventBus listener exception isolation | Partial | No test for exception in one listener blocking others |

---

## Recommendations Summary

**CRITICAL (Ship Blocking):**
- None currently

**HIGH (Next Release):**
1. Document LocalizationManager thread-safety requirement; add asyncio.Lock for metrics
2. Test hot-reload + concurrent command dispatch race
3. Add permission validator for bot's own perms, not just user perms

**MEDIUM (Nice to Have):**
1. Async fire-and-forget `auto_sync_guilds`, or configurable timeout
2. Document ConversationMemory eviction strategy
3. Pre-compile component regex patterns at registration
4. Test EventBus listener exception isolation
5. Mock time.time() in TTL tests to catch clock skew regressions

**LOW:**
1. Consider sync wrapper for ToolLimiter.check_limit() to catch forgotten await
2. Profile EventBus.publish under load (100+ listeners)
3. Document plugin load order assumptions
