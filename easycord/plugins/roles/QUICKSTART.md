# RolesPlugin — 5-Minute Quickstart

Get from zero to role management in 5 minutes.

---

## 1. Install (1 min)

```bash
# Clone EasyCord
git clone https://github.com/rolling-codes/EasyCord.git
cd EasyCord

# Install with dev dependencies
pip install -e ".[dev]"
```

---

## 2. Create Bot (1 min)

Save as `bot.py`:

```python
import os
from easycord.api.v1 import Bot
from easycord.plugins.roles import RolesPlugin

bot = Bot()
bot.add_plugin(RolesPlugin())

@bot.slash(description="Ping")
async def ping(ctx):
    await ctx.respond("Pong!")

bot.run(os.getenv("DISCORD_TOKEN"))
```

---

## 3. Setup Discord

Create a test server (or use existing):
1. Create a Discord application at https://discord.com/developers/applications
2. Copy token → `DISCORD_TOKEN` environment variable
3. Invite bot to your server (need `Manage Roles` permission)

---

## 4. Run (1 min)

```bash
export DISCORD_TOKEN="your-token-here"
python bot.py
```

Bot logs in. Owner receives DM:

> 🎭 This server has no role structure configured.
> Run `/roles setup` to initialize...

---

## 5. Try It (1 min)

In Discord:

```
/roles setup
→ Creates 4 default roles (Bot, Admin, Moderator, Member)

/roles debug
→ Shows roles in creation state

/roles sync
→ Creates roles in Discord

/roles debug
→ Shows ✅ all roles created
```

---

## 6. Prove Safety

Manually rename a role in Discord.

Then:

```
/roles simulate
→ Detects the change

/roles sync
→ Auto-corrects it back

/roles debug
→ Everything back in sync
```

---

## Next: Extend

Now that it works, try:

```python
# Assign role from another plugin
roles_plugin = bot.get_plugin(RolesPlugin)
await roles_plugin.api.assign(user_id, guild_id, "moderator")

# Listen to role changes
@bot.events.on("roles.sync")
async def on_roles_sync(event):
    print(f"Roles synced!")
```

---

## Stuck?

- Check `/roles debug` for current state
- Run `/roles reset` to start over
- See [README.md](./README.md) for full docs
- Open issue: https://github.com/rolling-codes/EasyCord/issues

---

## What Just Happened?

You just built a **production-grade role system** in 5 minutes. With:

✅ Safe, idempotent syncing  
✅ Policy enforcement (no escalation)  
✅ Dry-run preview  
✅ Full extensibility  
✅ Zero lock-in  

This is what EasyCord makes easy.
