# Fork and expand this project

EasyCord works best when you split the bot into small feature files early.

## Recommended structure

```text
my_bot/
├── bot.py
├── plugins/
│   ├── __init__.py
│   ├── fun.py
│   ├── moderation.py
│   └── info.py
├── config/
│   └── server_config.py
└── pyproject.toml
```

## Keep `bot.py` tiny

Use `bot.py` only for startup and plugin loading:

```python
import os
from easycord import Bot
from server_commands import load_default_plugins

bot = Bot()
load_default_plugins(bot)
bot.run(os.environ["DISCORD_TOKEN"])
```

## Add a new feature

1. Create a new plugin module in `plugins/`, for example `plugins/music.py`.
2. Put one related feature set in that file.
3. Use `@slash`, `@on`, `@component`, or `@modal` as needed.
4. Load the plugin from `bot.py` or add it to `server_commands/__init__.py` if it should be part of the default bot setup.

```python
from easycord import Plugin, slash

class MusicPlugin(Plugin):
    @slash(description="Confirm the music plugin is loaded")
    async def music(self, ctx):
        await ctx.respond("Music plugin loaded.")
```

## Add server-specific configuration

Use `ServerConfigStore` when a guild needs settings:

```python
from easycord import ServerConfigStore

store = ServerConfigStore()

cfg = await store.load(guild_id)
cfg.set_role("moderator", 1234567890)
cfg.set_channel("logs", 9876543210)
cfg.set_other("prefix", "!")
await store.save(cfg)
```

## Beginner-friendly rules

- Start with one command before introducing plugins.
- Prefer guild-only commands while testing.
- Keep shared setup in middleware instead of repeating it in commands.
- Put each feature in the file where a beginner would expect to find it later.

