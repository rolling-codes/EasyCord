# EasyCord

![PyPI](https://img.shields.io/pypi/v/easycord)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)

> EasyCord helps beginners build Discord bots faster by removing boilerplate around slash commands, components, plugins, and moderation helpers.

## Start here

1. Install the package: `pip install easycord`
2. Create a bot with one slash command.
3. Split features into plugins once the bot grows.

```python
from easycord import Bot

bot = Bot()

@bot.slash()
async def ping(ctx):
    await ctx.respond("Pong!")

bot.run("YOUR_TOKEN")
```

If you want the shortest possible path to a working bot, open [`docs/getting-started.md`](docs/getting-started.md).

## Why EasyCord exists

EasyCord was built for the moment a bot stops being a weekend project and starts becoming the thing you actually rely on. The goal is simple: let beginners ship features without spending their first hour learning Discord plumbing.

| Task | Raw `discord.py` | EasyCord |
| --- | --- | --- |
| Slash commands | Build a command tree and sync it | `@bot.slash(...)` |
| Permission checks | Repeat manual checks in each command | Declare permissions on the decorator |
| Cooldowns | Track timestamps yourself | `cooldown=...` |
| Components | Handle interactions by hand | `@bot.component(...)` |
| Shared behavior | Rebuild it per command | Middleware once, applied everywhere |
| Reusable features | Custom `Cog` wiring | Small `Plugin` classes |

## Recommended first project layout

```text
my_bot/
├── bot.py
├── plugins/
│   ├── fun.py
│   └── moderation.py
└── pyproject.toml
```

- Keep `bot.py` for startup and wiring.
- Put each feature in its own plugin.
- Move shared config into `ServerConfigStore` when you need it.

## Core pieces

- `Bot` for slash commands, events, components, and plugin loading
- `Plugin` for reusable feature bundles
- `Composer` for a fluent setup style
- `Context` for the common reply, DM, embed, and moderation actions
- Middleware for logging, error handling, rate limiting, and guards
- `ServerConfigStore` for per-guild settings without a database

## Best beginner path

1. Read [`docs/getting-started.md`](docs/getting-started.md) to make your first bot.
2. Read [`docs/concepts.md`](docs/concepts.md) to understand the pieces.
3. Copy [`examples/basic_bot.py`](examples/basic_bot.py) and make one change.
4. Move a command into a plugin once the file starts feeling crowded.

## Examples and docs

- [`examples/basic_bot.py`](examples/basic_bot.py): the smallest practical starter bot
- [`examples/plugin_bot.py`](examples/plugin_bot.py): a feature split across plugins
- [`examples/group_bot.py`](examples/group_bot.py): grouped slash commands with `SlashGroup`
- [`docs/index.md`](docs/index.md): documentation home
- [`docs/examples.md`](docs/examples.md): patterns and snippets
- [`docs/fork-and-expand.md`](docs/fork-and-expand.md): how to grow a real bot project
- [`server_commands/__init__.py`](server_commands/__init__.py): one place to load the bundled plugins

## Project backstory

EasyCord started as a way to cut down the repetitive work of Discord bot development for a school server. That original goal still drives the project: make the first command easy, then make the second and third commands feel just as simple.

## License

MIT
