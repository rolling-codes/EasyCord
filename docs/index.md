# EasyCord documentation

EasyCord is a decorator-first framework for building Discord bots on top of `discord.py>=2.0`.

The documentation is organized around one beginner-friendly path: install the package, make one command, then grow into plugins and shared helpers.

## Start here

1. [`getting-started.md`](getting-started.md) — create a bot, run it, and organize the first files.
2. [`concepts.md`](concepts.md) — learn slash commands, events, middleware, and plugins.
3. [`examples.md`](examples.md) — copy smaller patterns into your own bot.
4. [`fork-and-expand.md`](fork-and-expand.md) — turn a starter bot into a real project structure.
5. [`api.md`](api.md) — reference signatures when you already know what you want to build.
6. [`release-notes.md`](release-notes.md) — summary of the latest refactor and feature update.

## What EasyCord removes

| Beginner pain | EasyCord answer |
| --- | --- |
| Building and syncing a command tree | `@bot.slash(...)` |
| Writing the same permission checks repeatedly | Permission guards on the decorator |
| Repeating rate-limit and logging setup | Middleware once for the whole bot |
| Wiring buttons and selects by hand | `@bot.component(...)` |
| Growing from one file into a larger bot | Plugins and a simple folder layout |

## Suggested learning order

- Make the starter bot in [`getting-started.md`](getting-started.md)
- Copy [`examples/basic_bot.py`](../examples/basic_bot.py)
- Add one plugin from [`examples/plugin_bot.py`](../examples/plugin_bot.py)
- Read [`concepts.md`](concepts.md) only after you have a bot running

## Design goal

EasyCord exists to make the first useful Discord bot feel obvious. If a feature does not help beginners ship faster or keep their project organized, it should stay out of the way.
