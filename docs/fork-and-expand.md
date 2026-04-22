# Fork and expand this project

This framework works best when you split the bot into small feature files early.

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
from plugins.fun import FunPlugin
from plugins.info import InfoPlugin
from plugins.moderation import ModerationPlugin

bot = Bot()
bot.add_plugins(FunPlugin(), ModerationPlugin(), InfoPlugin())
bot.run(os.environ["DISCORD_TOKEN"])
```

## Add a new feature

1. Create a new plugin module in `plugins/`, for example `plugins/music.py`.
2. Put one related feature set in that file.
3. Use `@slash`, `@on`, `@component`, or `@modal` as needed.
4. Load the plugin from `bot.py`, or gather the always-on plugins in one small startup helper if several features should ship together.

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

