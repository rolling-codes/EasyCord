# RolesPlugin — Why You Should Use EasyCord

**Status:** Production-ready | **Flagship reference** | **No lock-in guarantee**

---

## The Problem

You want safe, consistent role systems. But:

❌ Manual setup is error-prone  
❌ Discord's UI doesn't prevent escalation  
❌ Changes are destructive (no preview)  
❌ Other bots lock you in  

---

## The Solution

RolesPlugin guarantees safe, consistent role systems **without taking control away from you**.

Every change:
- ✅ Can be previewed (dry-run)
- ✅ Cannot escalate permissions (policy enforced)
- ✅ Is automatically corrected (idempotent sync)
- ✅ Can be rolled back (reset to defaults)

---

## How It Works

### 1. Define (Once)

```python
blueprints = {
    "admin": RoleBlueprint(
        name="Admin",
        permissions=["ban_members", "kick_members"],
    ),
    "moderator": RoleBlueprint(
        name="Moderator",
        inherits="admin",  # Inherit parent perms
        permissions=["kick_members", "manage_messages"],
    ),
}
```

### 2. Preview

```
/roles simulate

→ Shows exact changes (create, update, delete)
→ No actual changes applied
```

### 3. Apply (Safely)

```
/roles sync

→ Policy checks prevent escalation
→ Changes applied idempotently
→ Full audit trail (EventBus events)
```

### 4. Verify

```
/roles debug

→ Shows which roles are managed
→ Shows which Discord roles are unmanaged
→ Shows permission mismatches
```

---

## Why This Matters

### Without RolesPlugin

```
Manual setup:
1. Create roles manually
2. Set permissions manually
3. Rename a role? Manual sync again.
4. Accidentally grant admin? 💥

Result: Inconsistent, error-prone, dangerous.
```

### With RolesPlugin

```
1. Define blueprints (once)
2. Preview changes
3. Apply idempotently
4. Any manual change is auto-corrected
5. Policy enforcement prevents mistakes

Result: Consistent, safe, reversible.
```

---

## Quick Comparison

| Feature | EasyCord Roles | Manual Setup | Other Bots |
|---------|---|---|---|
| Dry-run preview | ✅ | ❌ | ❌ |
| Idempotent sync | ✅ | ❌ | ❌ |
| Anti-escalation | ✅ | ❌ | ⚠️ |
| Reversible | ✅ | ❌ | ❌ |
| Plugin extensible | ✅ | ❌ | ❌ |
| No lock-in | ✅ | ✅ | ❌ |

---

## Reference Implementation

RolesPlugin is the **reference implementation** for EasyCord v4.0. It demonstrates:

- ✅ **Declarative blueprints** — role definitions as typed config
- ✅ **Deterministic reconciliation** — idempotent diff + apply
- ✅ **Safety policies** — prevent self-escalation, protect admin roles
- ✅ **EventBus integration** — all state changes emit events
- ✅ **Capability enforcement** — fine-grained permission control
- ✅ **Cross-plugin API** — other plugins integrate cleanly
- ✅ **Full observability** — debug commands, audit trails
- ✅ **Zero lock-in** — escape hatches to raw discord.py

Every design choice here is a template for v4.0 plugins.

---

## Quick Start

### Installation

```python
from easycord.api.v1 import Bot
from easycord.plugins import RolesPlugin

bot = Bot()
bot.add_plugin(RolesPlugin())
bot.run("TOKEN")
```

### Setup

In Discord:

```
/roles setup       # Create default roles (Bot, Admin, Moderator, Member)
/roles sync        # Apply blueprint to guild
/roles debug       # Inspect current state
```

---

## Architecture

### 1. Blueprint System

Source of truth for all role definitions. Typed, validated, versioned.

```python
from easycord.plugins.roles.blueprint import RoleBlueprint, BlueprintSet

admin = RoleBlueprint(
    name="Admin",
    permissions=["ban_members", "kick_members"],
    color=0xFF0000,
    hoist=True,
    inherits=None,
)

moderator = RoleBlueprint(
    name="Moderator",
    permissions=["kick_members", "manage_messages"],
    inherits="admin",  # Inherit from Admin
)

blueprint_set = BlueprintSet(
    guild_id=12345,
    blueprints={"admin": admin, "moderator": moderator}
)
```

**Features:**
- Permission inheritance
- Explicit deny overrides
- Color, hoist, mentionable control
- Full validation (names, perms, cycles)

### 2. Diff Engine

Compare desired state (blueprint) to actual state (Discord). Produce minimal change set.

```python
from easycord.plugins.roles.diff import DiffEngine

engine = DiffEngine()
diff = await engine.compute_diff(guild, blueprint_set, stored_ids)

# diff.summary() → human-readable output
# diff.is_clean() → check if sync needed
# diff.changes → list of RoleDiff objects
```

**Change types:**
- `CREATE` — role doesn't exist yet
- `UPDATE_PERMS` — permissions mismatch
- `UPDATE_COLOR` — color mismatch
- `UPDATE_HOIST` — hoist status mismatch
- `UPDATE_MENTIONABLE` — mentionable mismatch
- `DELETE` — remove unmanaged roles (optional)

### 3. Policy Engine

Enforce safety rules before applying changes.

```python
from easycord.plugins.roles.policy import PolicyEngine, PolicyConfig

config = PolicyConfig(
    prevent_self_escalation=True,  # User can't upgrade own role
    protect_admin_role=True,        # Warn on admin changes
    prevent_dangerous_perms=True,   # Block administrator perm
)

engine = PolicyEngine(config)
violations = await engine.validate(guild, diff_result, ctx.member)

if violations:
    # Handle policy violations
    pass
```

### 4. Reconciliation Engine

Apply changes idempotently to Discord.

```python
from easycord.plugins.roles.reconcile import ReconciliationEngine

engine = ReconciliationEngine()

# Dry-run (preview)
result = await engine.apply_diff(guild, diff_result, dry_run=True)

# Apply changes
result = await engine.apply_diff(guild, diff_result, dry_run=False)

if result.success:
    print(f"Applied {result.changes_applied} changes")
else:
    for error in result.errors:
        print(f"Error: {error}")
```

**Properties:**
- Non-destructive by default
- Partial failure tolerant
- Full error logging

### 5. Storage Layer

Persist blueprints and role ID mappings via ServerConfigStore.

```python
from easycord.plugins.roles.storage import RoleStorage

storage = RoleStorage(config_store)

# Save blueprints
await storage.save_blueprints(blueprint_set)

# Load blueprints
blueprints = await storage.load_blueprints(guild_id)

# Track role IDs
await storage.set_role_id(guild_id, "admin", 999)
role_ids = await storage.load_role_ids(guild_id)
```

### 6. Public API

Other plugins use this to assign/remove roles.

```python
from easycord.plugins.roles.plugin import RolesPlugin

roles_plugin = bot.get_plugin(RolesPlugin)
api = roles_plugin.get_api()

# Assign role to user
await api.assign(user_id, guild_id, "moderator")

# Remove role
await api.remove(user_id, guild_id, "moderator")

# Check if user has role
has_mod = await api.has(user_id, guild_id, "moderator")

# Get Discord role object
role = await api.get_role(guild_id, "admin")

# List all managed roles
roles = await api.list_roles(guild_id)
```

---

## Execution Pipeline

All actions flow through the **v4.0 execution pipeline**:

```
Command
  ↓
EventBus (emit "interaction.received")
  ↓
Middleware (run plugins, log, rate limit)
  ↓
Capability Check (user has required permission)
  ↓
Policy Engine (safety validation)
  ↓
Handler (execute command logic)
  ↓
Response + Event Emission
```

**In code:**

```python
# User invokes command
@slash(description="Sync roles", capabilities=["roles.manage"])
async def roles_sync(self, ctx: Context) -> None:
    # EventBus already emitted "interaction.received"
    # Capabilities already checked
    
    # Load and validate
    blueprint_set = await self.storage.load_blueprints(ctx.guild_id)
    diff = await self.diff_engine.compute_diff(guild, blueprint_set)
    
    # Policy validation
    violations = await self.policy_engine.validate(guild, diff, ctx.member)
    if violations:
        await ctx.respond("Policy violation")
        return
    
    # Apply
    result = await self.reconcile_engine.apply_diff(guild, diff)
    
    # Emit audit event
    await self.bot.events.emit(
        self._event("sync", {"changes_applied": result.changes_applied})
    )
    
    await ctx.respond("✅ Synced")
```

---

## Observability

### Debug Command

```
/roles debug
```

Output:
```
Managed Roles:
  ✅ `admin` → Admin (ID: 999)
  ✅ `moderator` → Moderator (ID: 998)
  ⚠️ `bot` → Bot (not created)
```

### Simulation

```
/roles simulate
```

Preview all changes without applying:
```
Changes for guild 12345:
  + CREATE Bot
  ~ UPDATE_PERMS Admin: permissions changed
  ~ UPDATE_COLOR Moderator: color changed

⚠️ Unmanaged roles (not in blueprint):
  - Legacy (ID: 997)
```

### Events

All state changes emit EventBus events. Other plugins listen:

```python
@bot.events.on("roles.sync")
async def on_role_sync(event):
    print(f"Roles synced: {event.data}")
```

Event names:
- `roles.plugin_loaded` — plugin initialized
- `roles.plugin_ready` — bot ready
- `roles.sync` — roles synchronized
- `roles.plugin_unloaded` — plugin removed

---

## Capabilities

Plugin defines five granular capabilities:

```python
"roles.manage"   # Sync blueprints, reset config
"roles.create"   # Create new roles (future)
"roles.assign"   # Assign roles to members
"roles.simulate" # Dry-run preview
"roles.debug"    # View state
```

Commands check capabilities:

```python
@slash(description="Sync roles", capabilities=["roles.manage"])
async def roles_sync(self, ctx):
    # User lacks `roles.manage` → ephemeral error, handler skipped
    ...
```

---

## Commands

### `/roles setup`

Initialize default blueprints:
- `bot` — send messages, manage roles, manage channels
- `admin` — ban members, kick members, manage messages
- `moderator` — kick members, manage messages (inherits from member)
- `member` — send messages, read history

### `/roles sync`

Apply blueprint changes to this guild. Policy-gated.

```
✅ Sync completed:
  + CREATE Bot
  ~ UPDATE_PERMS Admin: permissions changed

Use `/roles debug` to inspect state.
```

### `/roles simulate`

Dry-run. Show what would change without applying.

### `/roles debug`

Inspect current state. Show managed vs unmanaged roles.

### `/roles export`

Export blueprints as JSON (for backup or sharing).

```json
{
  "version": "1.0",
  "blueprints": {
    "admin": {
      "name": "Admin",
      "permissions": ["ban_members"],
      ...
    }
  }
}
```

### `/roles reset`

Delete all blueprints (confirmation required).

---

## Testing

Run tests:

```bash
pytest tests/test_roles_plugin.py -v
```

Test coverage:
- ✅ Blueprint validation (names, permissions, cycles)
- ✅ Diff computation (create, update, delete detection)
- ✅ Policy enforcement (self-escalation, dangerous perms)
- ✅ Reconciliation idempotency (apply twice = same result)
- ✅ Storage persistence (save/load)
- ✅ Public API (assign, remove, has, list)
- ✅ Integration (plugin lifecycle, capability registration)

---

## Design Decisions

### Why Blueprints?

- **Declarative** — define intent, not imperative steps
- **Reviewable** — diffs show exactly what will change
- **Versionable** — track config changes in git
- **Safe** — can preview before applying

### Why Idempotent Reconciliation?

- **Recoverable** — crash during apply? Just run sync again
- **Non-destructive** — never deletes unless explicitly enabled
- **Observable** — can diff without applying
- **Testable** — predictable, deterministic behavior

### Why Policy Enforcement?

- **Prevent escalation** — user can't upgrade own permissions
- **Protect admin** — require confirmation for admin changes
- **Block dangerous** — prevent granting `administrator` perm
- **Audit** — all decisions logged and reversible

### Why EventBus?

- **Decoupled** — other plugins listen without knowing implementation
- **Observable** — every state change is traceable
- **Extensible** — plugins can react to role changes
- **Non-blocking** — listeners run concurrently

### Why Public API?

- **No coupling** — other plugins don't call internals
- **Stable contract** — API is versioned, can change internals
- **Type-safe** — full type hints for IDE autocomplete
- **Capability-gated** — can't bypass permissions

---

## v4.0 Design Template

This plugin exemplifies the v4.0 design:

1. **Modular** — separate blueprint, diff, policy, reconcile, storage
2. **Deterministic** — no hidden state or magic
3. **Observable** — EventBus events, debug commands, audit trails
4. **Safe** — policy enforcement, non-destructive defaults
5. **Capable** — fine-grained capability system
6. **Testable** — comprehensive unit + integration tests
7. **Documented** — every class/method has docstrings
8. **Type-safe** — full type hints, dataclasses
9. **Escape-hatchable** — can drop to discord.py anytime
10. **Removable** — plugin can be unloaded cleanly

Every v4.0 plugin should follow this pattern.

---

---

## Developer Integration

### Assign Roles from Other Plugins

```python
from easycord.plugins.roles import RolesPlugin

class ModerationPlugin(Plugin):
    async def warn_user(self, ctx, user):
        # Assign "warned" role via roles plugin
        roles_plugin = self.bot.get_plugin(RolesPlugin)
        await roles_plugin.api.assign(user.id, ctx.guild_id, "moderator")

        await ctx.respond(f"Assigned moderator role to {user.mention}")
```

### Check Role Membership

```python
# Other plugins can check if user has a role
has_mod = await roles_plugin.api.has(user.id, guild_id, "moderator")
if has_mod:
    print("User is moderator")
```

### List Managed Roles

```python
# Get all roles managed by blueprint
roles_dict = await roles_plugin.api.list_roles(guild_id)
for key, discord_role in roles_dict.items():
    print(f"{key}: {discord_role.mention}")
```

### Listen to Role Events

```python
# Other plugins react to role changes
@bot.events.on("roles.sync")
async def on_roles_sync(event):
    print(f"Roles synced! Changes: {event.data['changes_applied']}")
```

### Extend with Custom Policies

```python
from easycord.plugins.roles.policy import PolicyConfig

custom_policy = PolicyConfig(
    prevent_self_escalation=True,
    protect_admin_role=True,
    prevent_dangerous_perms=True,
)

bot.add_plugin(RolesPlugin(policy=custom_policy))
```

---

## Demo Script

Quick proof-of-concept for presentations:

### Step 1: Install

```bash
pip install -e ".[dev]"
```

### Step 2: Create Bot

```python
from easycord.api.v1 import Bot
from easycord.plugins.roles import RolesPlugin

bot = Bot()
bot.add_plugin(RolesPlugin())
bot.run(os.getenv("DISCORD_TOKEN"))
```

### Step 3: Initial Setup

```
/roles setup
→ Creates: Bot, Admin, Moderator, Member

/roles debug
→ Shows 4 managed roles in creation state
```

### Step 4: Sync

```
/roles sync
→ Creates all 4 roles in Discord
→ Sets permissions, colors, hoist

/roles debug
→ Shows ✅ all 4 roles created
```

### Step 5: Manual Change (Prove Safety)

In Discord, manually:
- Rename "Moderator" role to "Mods"
- Remove a permission from "Admin" role

### Step 6: Detect & Correct

```
/roles simulate
→ Shows:
  ~ UPDATE_NAME Moderator: "Mods" → "Moderator"
  ~ UPDATE_PERMS Admin: permissions mismatch

/roles sync
→ Auto-corrects both changes
→ Proves idempotency

/roles debug
→ Shows everything corrected
```

**Talking points:**
- "Roles are always in sync with blueprint"
- "Manual changes are auto-corrected"
- "Zero loss of control (dry-run before apply)"
- "Works with other plugins via API"

---

## Presets

RolesPlugin comes with opinionated presets:

### Community Server

- **Member** — basic chat
- **Moderator** — kick, manage messages
- **Admin** — ban, manage channels

### Gaming Server

- **Player** — basic chat
- **VIP** — highlighted, priority
- **Moderator** — moderation
- **Admin** — server control

### Developer Server

- **Contributor** — basic access
- **Maintainer** — channel management
- **Admin** — full control

### Minimal

- **Bot** — technical permissions
- **Admin** — server control

Use `/roles setup` to choose preset on first run.

---

## Why EasyCord?

RolesPlugin proves EasyCord is a **real platform**, not just a framework:

1. **Comprehensive** — blueprint, diff, policy, reconcile, storage, API all in one
2. **Safe** — policy enforced, non-destructive, reversible
3. **Observable** — EventBus events, debug output, full audit trail
4. **Extensible** — other plugins integrate cleanly via public API
5. **No lock-in** — can escape to discord.py anytime
6. **Testable** — 20+ tests proving correctness

Every v4.0 plugin will follow this template. If you can build RolesPlugin-quality systems easily, why use anything else?

---

## License

MIT. See LICENSE file.
