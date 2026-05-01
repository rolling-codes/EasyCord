# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Quick Start

Install dev dependencies once:
```bash
pip install -e ".[dev]"
```

Common commands:
```bash
pytest                           # Run all tests
pytest tests/test_foo.py         # Run single test file
pytest tests/test_foo.py::test_x # Run specific test
python -m pytest -k "pattern"    # Run tests matching pattern
```

**Pytest config:** `asyncio_mode = "auto"` is set in `pyproject.toml` — async tests need no `@pytest.mark.asyncio` decorator.

---

## Architecture Overview

EasyCord is a modular Discord bot framework built on four core patterns:

### 1. Bot as Mixin Composition
`Bot` (`easycord/bot.py`) inherits from multiple mixins, each adding a capability:
- `_CommandsMixin` — slash command registration (`@bot.slash`)
- `_EventsMixin` — event handlers (`@bot.on`)
- `_PluginsMixin` — plugin lifecycle (load, ready, unload)
- `_GuildMixin` — guild-scoped operations
- `discord.Client` — Discord connection

This keeps concerns isolated while avoiding a god object.

### 2. Plugin Architecture
Plugins (`easycord/plugin.py`, `easycord/plugins/`) encapsulate features:
```python
class MyPlugin(Plugin):
    async def on_load(self):
        # Called once when plugin is added to bot
    
    async def on_ready(self):
        # Called on bot startup (+ reconnects)
    
    @slash(description="My command")
    async def mycmd(self, ctx):
        await ctx.respond("Hello")
    
    @on("message")
    async def onmsg(self, msg):
        # Handle events
```

Plugins register themselves via decorators; `bot.add_plugin()` handles wiring.

### 3. Middleware Chain (Slash Commands Only)
Middleware wraps slash command execution for cross-cutting concerns (logging, rate limits, permission checks). Built-in middleware in `easycord/middleware.py` includes:
- `log_middleware()` — Log each command
- `catch_errors()` — Global error handler
- `rate_limit()` — Per-user rate limiting
- `guild_only()` / `dm_only()` — Channel scope
- `allowed_roles()` — Role-based access

**Key:** Middleware only wraps *slash commands*, not events. `bot.use(fn)` has no effect on `@bot.on(...)`.

### 4. Context Mixin Pattern (Response Helpers)
`Context` (`easycord/context.py`) delegates to four mixin modules:
- `_context_base.py` — respond, defer, embeds, DMs, confirmations
- `_context_channels.py` — slowmode, lock/unlock, threads, message operations
- `_context_moderation.py` — kick, ban, timeout, roles, voice
- `_context_ui.py` — select menus, pagination

This avoids a 1000-line Context class; edit the specific `_context_*.py` you need.

---

## Key Files & Patterns

| Task | File(s) |
|------|---------|
| **Slash commands & events** | `easycord/decorators.py` — `@slash`, `@on`, `@task` |
| **Plugin system** | `easycord/plugin.py`, `easycord/plugins/` |
| **Bot core** | `easycord/bot.py` |
| **Response methods** | `easycord/context.py` → `_context_*.py` mixins |
| **Middleware** | `easycord/middleware.py` |
| **Slash groups** | `easycord/group.py` |
| **Per-guild config** | `easycord/server_config.py` |
| **Rate limiting** | `easycord/tool_limits.py` |
| **Embeds & builders** | `easycord/embed_cards.py`, `easycord/builders/` |
| **i18n/localization** | `easycord/i18n.py` |
| **Example plugins** | `easycord/plugins/` (bundled) |
| **Example bots** | `server_commands/`, `examples/` |

---

## Non-Obvious Patterns

### Timing: on_load() vs on_ready()
- **Plugins added before `bot.run()`:** `on_load()` awaited in `Bot.setup_hook()` (during startup).
- **Plugins added after bot starts:** `on_load()` scheduled via `asyncio.create_task()`.
- **`on_ready()`:** Called every time bot becomes ready (startup + reconnects).

### Slash Command Registration
- **`auto_sync=True` by default** syncs ALL commands globally on startup.
- **Global commands take ~1 hour to appear in Discord.**
- **During development, use `guild_id=YOUR_SERVER_ID`** for instant registration:
  ```python
  @bot.slash(description="...", guild_id=1234567890)
  async def cmd(ctx):
      ...
  ```

### ServerConfigStore (Per-Guild Config)
- All writes are **atomic** (write-to-temp + rename, protected by async locks).
- Don't edit `server_config.json` directly; use the API.
- Example:
  ```python
  store = bot.server_config
  store.update(guild.id, lambda cfg: {...})  # Atomic update
  ```

### Moderation Plugins Compose
Use independently or together:
- `ModerationPlugin` — Manual commands (kick, ban, timeout, warn, mute)
- `AIModeratorPlugin` — LLM-powered message analysis
- `ReactionRolesPlugin` — Auto-assign roles via emoji
- `MemberLoggingPlugin` — Audit trail for joins, leaves, role changes

All use `ServerConfigStore` for per-guild config.

### Context Split
`Context` is not a single file. It's assembled from:
- `context.py` → imports from `_context_base.py`, `_context_channels.py`, etc.

When adding a new context method, edit the appropriate `_context_*.py` file, not `context.py`.

---

## Bundled Plugins (`easycord/plugins/`)

| Plugin | Purpose |
|--------|---------|
| `moderation.py` | Manual moderation: kick, ban, timeout, warn, mute |
| `ai_moderator.py` | LLM-powered message analysis (spam, abuse, NSFW) |
| `reaction_roles.py` | Self-assign roles via emoji reactions |
| `member_logging.py` | Audit trail: joins, leaves, nicknames, roles, timeouts |
| `auto_responder.py` | Keyword/regex-triggered responses |
| `starboard.py` | Archive popular messages to a channel |
| `invite_tracker.py` | Track which invite code brought members |
| `levels.py` | XP, leveling, ranks |
| `polls.py` | Simple poll creation |
| `welcome.py` | Welcome messages for new members |

---

## Directory Structure

```
easycord/                     # Framework package
  bot.py                      # Bot class + setup_hook + lifecycle
  composer.py                 # Fluent builder for Bot
  plugin.py                   # Plugin base class
  decorators.py               # @slash, @on, @task
  context.py                  # Aggregates _context_*.py
  _context_base.py            # Respond, embeds, DMs, confirmations
  _context_channels.py        # Channel operations, threads, reactions
  _context_moderation.py      # Kick, ban, timeout, roles
  _context_ui.py              # Select menus, pagination
  middleware.py               # log_middleware, catch_errors, etc.
  group.py                    # SlashGroup for command groups
  server_config.py            # Per-guild atomic JSON config
  audit.py                    # Embed logging to Discord
  i18n.py                     # LocalizationManager for translations
  tool_limits.py              # Rate limiting + per-user tool limits
  tools.py                    # ToolRegistry, ToolDef, ToolCall
  orchestrator.py             # LLM orchestration (multi-provider)
  conversation_memory.py      # Conversation history for AI
  database.py                 # DatabaseConfig, memory/SQLite backends
  builders/                   # UI builders (embeds, buttons, modals, selects)
  plugins/                    # Bundled reusable plugins
    moderation.py
    ai_moderator.py
    reaction_roles.py
    ...
  helpers/                    # Helper utilities
  utils/                      # EasyEmbed, Paginator
  managers.py                 # FrameworkManager, SecurityManager
  builtin_plugins.py          # Load all bundled plugins at once
  builtin_tools.py            # Register built-in AI tools

server_commands/              # Example bot-specific plugins (not packaged)
examples/                     # Example bots

tests/                        # pytest suite (mirrors easycord/ structure)

docs/                         # User-facing documentation
  api.md                      # API reference
  concepts.md                 # Conceptual overview
  getting-started.md          # Quick start
  examples.md                 # Example patterns

model.md                      # AI context: architecture + extension guide
README.md                     # User-facing overview
CHANGELOG.md                  # Version history
RELEASE_v4.3.md               # Latest release notes
```

---

## Testing Strategy

- **Unit tests:** Isolated logic (utilities, helpers)
- **Integration tests:** Service interactions (plugins + middleware)
- **Async tests:** Use standard `async def test_*()` (no decorator needed; `asyncio_mode = auto`)

Example:
```python
@pytest.mark.asyncio
async def test_middleware_chain():
    ctx = create_mock_context()
    called = []
    
    async def mw1(ctx, proceed):
        called.append("mw1_before")
        await proceed()
        called.append("mw1_after")
    
    async def invoke():
        called.append("handler")
    
    chain = build_chain(ctx, invoke, [mw1])
    await chain()
    
    assert called == ["mw1_before", "handler", "mw1_after"]
```

Run tests with:
```bash
pytest                              # All tests
pytest tests/test_moderation.py -v  # Moderation tests
pytest -k "test_middleware"         # Tests matching pattern
```

---

## Validation & Quality

Before finishing work:
1. **Run targeted tests:** `pytest tests/test_<feature>.py -v`
2. **Run full suite:** `pytest`
3. **Check imports:** Ensure no circular dependencies (types in `TYPE_CHECKING` blocks)
4. **Review diff:** Confirm only intended changes are included

---

## Localization (i18n)

`LocalizationManager` in `easycord/i18n.py` provides:
- Register translations per locale
- Fallback chain (user locale → guild locale → default locale)
- Language-only fallback (pt-BR → pt)
- Auto-translator callback for missing translations (with caching)

Example:
```python
from easycord import LocalizationManager

l10n = LocalizationManager(
    default_locale="en-US",
    translations={
        "en-US": {"greeting": "Hello {name}!"},
        "es-ES": {"greeting": "¡Hola {name}!"},
    }
)

# Lookup with fallback
msg = l10n.get("greeting", locale="es-ES", default="Welcome")
formatted = l10n.format("greeting", locale="es-ES", name="Alice")

# Auto-translate missing keys
def translate_fn(source_text, source_locale, target_locale):
    # Your LLM call here
    return translated_text

l10n_with_auto = LocalizationManager(
    translations={...},
    auto_translator=translate_fn
)
```

**Bug fix in v4.3.1:** `_find_source_for_key()` now prioritizes canonical catalog entries over caller-provided defaults, ensuring registered translations are used for auto-translation.

---

## Common Pitfalls

1. **Middleware doesn't wrap events:** Only slash commands go through middleware. Events bypass it.
2. **Context split is confusing:** Add methods to the right `_context_*.py` file.
3. **on_load() timing:** Plugins added before `bot.run()` vs after have different timing.
4. **global auto_sync is slow:** Use `guild_id` for dev.
5. **ServerConfigStore is not a dict:** Don't mutate directly; use `update(guild_id, fn)`.
6. **Circular imports:** Use `TYPE_CHECKING` guards if importing `Bot` in type hints.

---

## Further Reading

- `model.md` — Deep architecture + extension guide
- `docs/api.md` — Complete API reference
- `docs/getting-started.md` — Beginner tutorial
- `CHANGELOG.md` — Version history and breaking changes
- `examples/` — Working example bots
