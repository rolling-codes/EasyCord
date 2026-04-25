# Documentation

EasyCord is a **unified Discord bot framework** — not just a decorator layer or command handler. It provides a complete system for building production bots with commands, events, moderation, configuration, plugins, and AI orchestration all integrated.

The documentation is organized around one beginner-friendly path: install the package, make one command, then grow into plugins, features, and AI agents.

## Start here

1. [`getting-started.md`](getting-started.md) — create a bot, run it, and organize the first files (5 minutes).
2. [`framework.md`](framework.md) — understand EasyCord as a unified system, not just slash commands (philosophy + architecture).
3. [`concepts.md`](concepts.md) — learn slash commands, events, middleware, and plugins.
4. [`examples.md`](examples.md) — copy smaller patterns into your own bot.
5. [`fork-and-expand.md`](fork-and-expand.md) — turn a starter bot into a real project structure.
6. [`api.md`](api.md) — reference signatures when you already know what you want to build.
7. [`release-notes.md`](release-notes.md) — summary of the latest refactor and feature update.

## What this removes

| Beginner pain | This framework answer |
| --- | --- |
| Building and syncing a command tree | `@bot.slash(...)` |
| Writing the same permission checks repeatedly | Permission guards on the decorator |
| Repeating rate-limit and logging setup | Middleware once for the whole bot |
| Wiring buttons and selects by hand | `@bot.component(...)` |
| Growing from one file into a larger bot | Plugins and a simple folder layout |
| Building moderation from scratch | `ModerationPlugin` + `AIModeratorPlugin` |
| Managing per-guild config without a database | `ServerConfigStore` or `PluginConfigManager` |
| Handling member events, logging, welcome messages | `MemberLoggingPlugin`, `WelcomePlugin`, etc. |
| Scaling to AI agents with safe tool calling | `Orchestrator`, `@ai_tool`, tool registry |

## Suggested learning order

- Make the starter bot in [`getting-started.md`](getting-started.md)
- Copy [`examples/basic_bot.py`](../examples/basic_bot.py)
- Add one plugin from [`examples/plugin_bot.py`](../examples/plugin_bot.py)
- Read [`concepts.md`](concepts.md) only after you have a bot running

## Design goals

1. **Make the first bot obvious.** One command should take 10 lines. Slash commands, events, and responses should feel natural.
2. **Unified system, not framework sprawl.** Commands, events, moderation, configuration, and AI orchestration should integrate seamlessly — no "pick your own middleware" or "choose your config store" paralysis.
3. **Plugins as first-class architecture.** As bots grow, plugins should feel like the natural way to organize features. Plugins shouldn't need to know about each other.
4. **Production-ready out of the box.** Moderation, logging, role assignment, leveling — ship with solid plugins you can use immediately, not tutorials on how to build them.
5. **Scale to AI agents.** Once a bot is useful, let it become intelligent. Tool calling, multi-provider LLMs, permission gates — all built-in.
