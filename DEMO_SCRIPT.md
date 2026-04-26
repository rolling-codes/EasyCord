# EasyCord v4.0 Demo Script

**Goal:** Prove that EasyCord makes role systems safe and reversible.

**Duration:** 5 minutes

---

## Setup (Before Demo)

1. Create test Discord server (or use dev server)
2. Have Python 3.10+ installed
3. Have Discord token ready
4. Have guild ID ready

---

## The Demo

### Minute 1: Installation

**Narration:** "Let's install EasyCord and get running."

```bash
pip install easycord
```

**Result:** Installation completes (should be fast).

---

### Minute 2: Quickstart

**Narration:** "Now let's start the interactive setup."

```bash
easycord quickstart
```

**Flow:**
1. Paste Discord token
2. Enter guild ID
3. Select "Community" preset
4. System generates bot file

**Result:** Bot is configured and ready.

---

### Minute 3: First Sync

**Narration:** "Now the bot is running. Let's initialize the role system."

In Discord:
```
/roles setup
```

**Result:** 4 roles are configured (Bot, Admin, Moderator, Member).

```
/roles debug
```

**Result:** Shows roles in "creation" state (not yet in Discord).

---

### Minute 4: Apply Changes

**Narration:** "Now we apply the roles to Discord. Let's preview first."

```
/roles simulate
```

**Result:** Shows changes:
```
+ CREATE Bot
+ CREATE Admin
+ CREATE Moderator
+ CREATE Member
```

**Narration:** "Now apply them."

```
/roles sync
```

**Result:** All 4 roles created in Discord.

```
/roles debug
```

**Result:** Shows ✅ all 4 roles created.

---

### Minute 5: Prove Safety

**Narration:** "Now comes the magic. Let's manually break something and watch it auto-correct."

In Discord:
1. Find the "Moderator" role
2. Rename it to "Mods"
3. Remove the "Kick Members" permission

Back to command line:
```
/roles simulate
```

**Result:** Detects both changes:
```
~ UPDATE_NAME Moderator: "Mods" → "Moderator"
~ UPDATE_PERMS Moderator: permissions changed
```

**Narration:** "EasyCord detected the changes. Now let's auto-correct them."

```
/roles sync
```

**Result:** Changes applied.

```
/roles debug
```

**Result:** Everything corrected back to blueprint state.

---

## The Talking Points

### Key Insight

> "The role system auto-corrects itself. Manual changes don't break anything—they're just temporary. Sync and you're back to the official state."

### Why This Matters

1. **Safe:** Policy prevents escalation, bad permissions
2. **Consistent:** Sync idempotency guarantees correctness
3. **Reversible:** Manual changes are always correctable
4. **Debuggable:** `/roles debug` shows exact state
5. **Extensible:** Other plugins use the API

### Comparison

| Scenario | Manual Setup | Other Bots | EasyCord |
|----------|---|---|---|
| Initial setup | 30 min | 5 min | <1 min |
| Someone renames a role | Redo | Redo | Auto-correct |
| Permission mismatch | Manual fix | Breaks | Auto-correct |
| New server | Start over | Start over | `/roles setup` |
| Trust level | Low | Medium | High |

---

## Follow-Up Questions (Audience)

### "Can I customize the roles?"

```
/roles export
→ Get JSON blueprints

# Edit locally

/roles import
→ Update system
```

### "What if I want to add a new role?"

```
# Edit blueprint, then:
/roles sync
→ New role is created
```

### "Can other plugins use this?"

```python
roles_plugin = bot.get_plugin(RolesPlugin)
await roles_plugin.api.assign(user_id, "moderator")
```

### "Is it production-ready?"

✅ 598 tests passing  
✅ MIT license  
✅ 100% discord.py compatible  
✅ Zero lock-in  

---

## Closing

> "This is what a Discord bot platform should be: smart, safe, and in your control."

---

## Technical Notes

- Bot must have "Manage Roles" permission
- Roles are ordered by position (hoist = top)
- Policy prevents dangerous permissions (administrator)
- All changes are logged via EventBus
- Config stored in `.easycord/server-config/<guild_id>.json`

---

## If Something Breaks

1. **Bot won't start:** Check Discord token
2. **Roles won't sync:** Bot missing "Manage Roles" permission
3. **Commands don't appear:** Wait 1 hour (global commands) or restart bot
4. **State is corrupted:** Run `/roles reset` to start over

---

## Recording Notes

- Record terminal + Discord side-by-side
- Show /roles output clearly
- Pause after each step to explain
- Total video: ~3 minutes
- Post to GitHub releases

---

## Timing Checklist

- [ ] Minute 1: Installation
- [ ] Minute 2: Quickstart
- [ ] Minute 3: First sync
- [ ] Minute 4: Apply changes
- [ ] Minute 5: Prove safety

---

## Success Criteria

Viewers should think:

> "This is the most thoughtful role system I've ever seen. And it's open source."
