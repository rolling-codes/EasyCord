# Agent context map

> Read CLAUDE.md first. This file covers architecture and extension points.

## What it is

Decorator-first Python framework for Discord bots on `discord.py>=2.0`. Removes boilerplate: decorators register slash commands, middleware wraps every invocation, plugins group commands/events into classes.

Current roadmap state: database auto-configuration, bundled plugins, embed-card helpers, and a lightweight localization manager are now in place. `Context.t(...)` can resolve translated strings through `Bot.localization` / `Bot.i18n`.

Release notes now emphasize the practical uses of each feature, especially `Bot.db`, `bot.load_builtin_plugins()`, `EmbedCard`, and `LocalizationManager`, so they can guide the next implementation pass instead of only recording history.

## Layout

| Path | Purpose |
| --- | --- |
| `easycord/bot.py` | `Bot` — slash/event/middleware/plugin wiring |
| `easycord/context.py` | `Context` — assembles four `_context_*.py` mixins |
| `easycord/_context_base.py` | respond, defer, embed, dm, send_to, file, edit, properties |
| `easycord/_context_channels.py` | slowmode, lock/unlock, threads, reactions, messages |
| `easycord/_context_moderation.py` | kick, ban, timeout, unban, roles, nickname, voice |
| `easycord/_context_ui.py` | choose, paginate (select-menu UI) |
| `easycord/decorators.py` | `@slash` `@on` `@task` for Plugin methods |
| `easycord/plugin.py` | `Plugin` base class |
| `easycord/middleware.py` | built-in middleware factories |
| `easycord/composer.py` | fluent `Composer` builder |
| `easycord/server_config.py` | `ServerConfigStore` — per-guild atomic JSON |
| `easycord/audit.py` | `AuditLog` — embed logging to Discord channel |
| `easycord/group.py` | `SlashGroup` — slash subcommand groups |
| `easycord/plugins/levels.py` | `LevelsPlugin` — XP, leveling, ranks |
| `easycord/plugins/polls.py` | `PollsPlugin` |
| `easycord/plugins/welcome.py` | `WelcomePlugin` |
| `server_commands/` | example bot plugins — add new bot features here |
| `tests/` | pytest suite (`asyncio_mode = "auto"`) |
| `docs/api.md` | full API reference |

## Public API (`from easycord import ...`)

`Bot`, `Context`, `Plugin`, `SlashGroup`, `Composer`, `slash`, `on`, `task`, `ServerConfig`, `ServerConfigStore`, `AuditLog`

## Key mechanics

**Slash commands** — `Bot.slash(...)` registers an `app_commands.Command`. Internally: build `Context(interaction)` → run middleware chain → call handler with `ctx` + parsed options. Signature rewriting: first param swapped to `interaction: discord.Interaction` for discord.py, `ctx` stripped and forwarded.

**Middleware** — wraps slash commands only (not events). Runs in registration order. Short-circuit by not calling `await next()`.

**Events** — `Bot.on("message")` supports multiple handlers. Dispatched via `asyncio.create_task` — one failure doesn't block others.

**Plugins** — `add_plugin()` and `add_plugins()` scan attributes for `_is_slash` / `_is_event` / `_is_task` tags. `on_load()` awaited in `setup_hook` if pre-run; `create_task` if bot already ready.

**ServerConfigStore** — atomic writes (write-to-temp + rename), per-guild `asyncio.Lock`.

## Extension conventions

- New bot features → `server_commands/<feature>.py` plugin
- New bundled plugins → `easycord/plugins/<feature>.py`
- Keep secrets in env vars (`DISCORD_TOKEN`, etc.)
- Use `async` I/O; never block the event loop
- `auto_sync=True` by default — use `guild_id=` during development for instant command registration
