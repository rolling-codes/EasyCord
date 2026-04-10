# Fork and expand this project

This repo is a good starting point for a “real” bot codebase: commands live in their own modules and configuration is persisted per server.

## Recommended structure

```
my_bot/
├── easycord/                 # the framework source (vendored)
├── server_commands/          # your command plugins (per-feature modules)
│   ├── __init__.py
│   ├── fun.py
│   ├── moderation.py
│   ├── info.py
│   └── config.py             # (recommended) config commands
├── main.py                   # create bot, load plugins, run
├── requirements.txt
└── .easycord/
    └── server-config/        # auto-created by ServerConfigStore (JSON per guild)
```

## Add a new command module

1. Create a new file in `server_commands/`, for example `server_commands/music.py`.
2. Add a `Plugin` subclass and decorate methods with `@slash` / `@on`.
3. Export it from `server_commands/__init__.py` (optional but convenient).
4. Load it in your bot (`bot.add_plugin(...)`).

Example:

```python
from easycord import Plugin, slash

class MusicPlugin(Plugin):
    @slash(description="Confirm the music plugin is loaded")
    async def music(self, ctx):
        await ctx.respond("Music plugin loaded.")
```

## Add server-specific configuration

Use `ServerConfigStore` to persist roles/channels/other settings per guild:

```python
from easycord import ServerConfigStore

store = ServerConfigStore()

cfg = await store.load(guild_id)
cfg.set_role("moderator", 1234567890)
cfg.set_channel("logs", 9876543210)
cfg.set_other("prefix", "!")
await store.save(cfg)
```

Suggested keys:

- **roles**: `"moderator"`, `"admin"`, `"verified"`, `"muted"`
- **channels**: `"welcome"`, `"logs"`, `"announcements"`
- **other**: feature flags, rate limits, per-guild settings, etc.

## Production tips

- Put tokens/URLs in environment variables (never hardcode).
- Prefer **guild-only** commands during development (`guild_id=...`) to avoid global propagation delays.
- Add your own middleware for permission checks and audit logging.

