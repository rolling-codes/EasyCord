# EasyCord v4.0.0 — Platform Release

**Release Date:** 2026-04-26  
**Status:** Stable. Production ready. Zero breaking changes.

---

## Overview

v4.0.0 is the **platform release** for EasyCord. Not just a framework—a complete system for building Discord bots safely, fast, and without lock-in.

**What changed:** Everything. And nothing breaks.

---

## 🚀 What's New

### 1. Complete Plugin System

Modular, extensible plugins with clean APIs:

```python
from easycord.api.v1 import Plugin, slash

class MyPlugin(Plugin):
    @slash(description="My command", capabilities=["my_capability"])
    async def my_command(self, ctx):
        await ctx.respond("Hello!")

bot.add_plugin(MyPlugin())
```

### 2. RolesPlugin (Flagship)

Production-grade role orchestration system. The proof that EasyCord is a platform.

**Features:**
- Declarative blueprints (define roles once)
- Idempotent reconciliation (safe, reversible syncs)
- Policy enforcement (prevent self-escalation, dangerous perms)
- Cross-plugin API (other plugins integrate cleanly)
- Full observability (EventBus events, debug commands)

**Try it:**
```bash
/roles setup
/roles sync
/roles debug
```

### 3. 60-Second Quickstart

Get a working bot in under a minute:

```bash
pip install easycord
easycord quickstart
```

Interactive wizard:
- Ask for Discord token
- Ask for server
- Choose role preset (Community, Gaming, Developer, Minimal)
- Done. Bot is running.

### 4. CLI Suite

```bash
easycord quickstart    # Get running in 60 seconds
```

More coming in v4.1+.

### 5. Anti-Lock-In Architecture

**Direct escape hatches to discord.py:**

```python
# High-level
await ctx.ban(user, reason="spam")

# Drop to raw discord.py
await ctx.client.http.ban(user.id, ctx.guild.id, reason="spam")

# Both work. Your choice.
```

Properties:
- `ctx.client` — raw discord.Client
- `ctx.raw_interaction` — raw discord.Interaction
- All config is plain JSON
- All plugins are plain Python
- No proprietary formats

### 6. Capability System

Fine-grained permissions without Discord limitations:

```python
@slash(capabilities=["roles.manage"])
async def sync_roles(ctx):
    # User must have "roles.manage" capability
    ...

bot.capability_registry.define("roles.manage", "Manage role system")
```

### 7. EventBus (v3.9 feature, now proven)

Async pub/sub event system with priority ordering:

```python
@bot.events.on("roles.sync", priority=10)
async def on_roles_sync(event):
    print(f"Roles synced: {event.data}")
```

All state changes emit events. Decouple plugins cleanly.

---

## 📊 Comparison

| Feature | EasyCord 4.0 | discord.py | Other Bots |
|---------|---|---|---|
| Install time | <1 min | 5 min | 5 min |
| Quickstart | ✅ `easycord quickstart` | ❌ DIY | ❌ No |
| Role system | ✅ RolesPlugin | ❌ Manual | ⚠️ Limited |
| Role safety | ✅ Policy enforced | ❌ None | ⚠️ Depends |
| Reversible syncs | ✅ Idempotent | ❌ Destructive | ❌ Destructive |
| Plugin extensibility | ✅ Clean API | ❌ No platform | ❌ Proprietary |
| Lock-in | ❌ None | ❌ None | ❌ Yes |

---

## 🎭 RolesPlugin: The Proof

RolesPlugin is the flagship plugin proving EasyCord is a real platform.

**Problem:** Role systems are fragile, manual, error-prone.

**Solution:** Declarative blueprint + idempotent reconciliation.

**Proof:**

1. **Define once:**
   ```python
   blueprints = {
       "admin": RoleBlueprint(name="Admin", permissions=["ban_members"]),
       "moderator": RoleBlueprint(name="Moderator", inherits="admin"),
   }
   ```

2. **Preview changes:**
   ```
   /roles simulate
   → Shows exactly what will change
   → No actual changes applied
   ```

3. **Apply safely:**
   ```
   /roles sync
   → Policy enforces safety
   → Changes applied idempotently
   → Full audit trail (EventBus events)
   ```

4. **Verify state:**
   ```
   /roles debug
   → Shows managed vs unmanaged roles
   → Shows permission mismatches
   → Shows everything in sync
   ```

**Why this matters:**

- ✅ Safe (policy enforced before execution)
- ✅ Reversible (dry-run preview, reset anytime)
- ✅ Consistent (idempotent—apply twice = same result)
- ✅ Observable (EventBus events, debug output, audit trail)
- ✅ Extensible (clean API for other plugins)

No other bot platform offers this.

---

## 🔓 No Lock-In Guarantee

**You are not locked in. Ever.**

- Direct access to raw `discord.Client` via `ctx.client` or `bot`
- Direct access to raw `discord.Interaction` via `ctx.raw_interaction`
- All configuration is plain JSON
- All plugins are plain Python
- Drop to discord.py directly anytime

This is not marketing. It's how the system works.

---

## 📦 Installation

### From GitHub

```bash
pip install git+https://github.com/rolling-codes/EasyCord.git@v4.0.0
```

### Quick Setup

```bash
pip install easycord
easycord quickstart
```

### With Dev Dependencies

```bash
pip install -e ".[dev]"
pytest
```

---

## 📚 Documentation

**Getting Started:**
- [README.md](README.md) — overview + quickstart
- [QUICKSTART.md](easycord/plugins/roles/QUICKSTART.md) — 5-minute guide
- [DEMO_SCRIPT.md](DEMO_SCRIPT.md) — live demo walkthrough

**Architecture:**
- [docs/EXECUTION_PIPELINE.md](docs/EXECUTION_PIPELINE.md) — 6-stage flow
- [docs/PLUGIN_V2_SPEC.md](docs/PLUGIN_V2_SPEC.md) — plugin system design
- [docs/ROLES_DIFFERENTIATOR.md](docs/ROLES_DIFFERENTIATOR.md) — why EasyCord matters

**API Reference:**
- [docs/api.md](docs/api.md) — full API reference

---

## 🧪 Testing

**All 598 tests passing.**

```bash
pytest
# 598 passed in 1.36s
```

Test coverage:
- ✅ Plugin lifecycle (on_load, on_ready, on_unload)
- ✅ Slash commands (permissions, cooldowns, ephemeral)
- ✅ Middleware (execution, error handling)
- ✅ EventBus (priority ordering, wildcards, concurrency)
- ✅ CapabilityRegistry (permission gates, overrides)
- ✅ RolesPlugin (blueprint, diff, policy, reconcile, storage, API)
- ✅ CLI (quickstart flow, presets)

---

## ✅ Backwards Compatibility

**100% compatible with v3.9 and v3.8.**

All v3.8 code works unchanged. No migration needed.

| Feature | v3.8 | v4.0 | Breaking? |
|---------|------|------|-----------|
| `from easycord import Bot` | ✅ | ✅ | ❌ No |
| `@bot.use(mw)` | ✅ | ✅ | ❌ No |
| `@bot.on("event")` | ✅ | ✅ | ❌ No |
| `@bot.slash(permissions=[...])` | ✅ | ✅ | ❌ No |
| All plugins | ✅ | ✅ | ❌ No |
| All commands | ✅ | ✅ | ❌ No |
| Config persistence | ✅ | ✅ | ❌ No |

Zero breaking changes. Pure addition.

---

## 🚀 What's Next (v4.1+)

Intentionally deferred:

- ❌ Plugin v2 (explicit isolation, dependency resolution, hot reload)
- ❌ TypedStore (per-guild typed config with migrations)
- ❌ Storage adapter system (pluggable backends)
- ❌ AI decoupling (separate `easycord[ai]` extra)
- ❌ CLI tools (init, dev, migrate, etc.)
- ❌ Distributed event bus (Redis/gRPC)

v4.0 is the *platform foundation*. v4.1+ adds power users features.

---

## 📣 The Pitch

Use EasyCord when:

- ✅ You want a working bot in 60 seconds
- ✅ You care about safety (policy enforcement)
- ✅ You want reversible changes (dry-run, reset)
- ✅ You want to extend plugins cleanly (public API)
- ✅ You don't want lock-in (escape to discord.py anytime)

Don't use EasyCord when:

- ❌ You want discord.py raw (use discord.py directly)
- ❌ You want a full-featured bot (use MEE6, Dyno, etc.)
- ❌ You want AI automation (that's coming in future)

EasyCord is for developers who want to build bots smart, safe, and free.

---

## 🙏 Credits

Built by the EasyCord team.  
Powered by [discord.py](https://github.com/Rapptz/discord.py).

---

## 📄 License

MIT. See LICENSE file.

---

## 🔗 Links

- **GitHub:** https://github.com/rolling-codes/EasyCord
- **Issues:** https://github.com/rolling-codes/EasyCord/issues
- **Discussions:** https://github.com/rolling-codes/EasyCord/discussions

---

## Summary

**EasyCord v4.0 is the complete platform release.**

Try it in 60 seconds:

```bash
pip install easycord
easycord quickstart
```

Then ask yourself: *"Why wouldn't I use this?"*
