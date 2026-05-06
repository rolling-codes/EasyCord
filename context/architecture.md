# Architecture

EasyCord is a Discord bot framework (v5.1.0, Python 3.10+). Entry point: `easycord/__init__.py` is the stable public API — internal modules are prefixed `_`.

## Layers

**Bot core** — `bot.py` composes `discord.Client` + four mixins: `_bot_commands.py`, `_bot_events.py`, `_bot_guild.py`, `_bot_plugins.py`. New bot-level behavior goes into the relevant mixin.

**Context** — `context.py` + `_context_base.py`, `_context_channels.py`, `_context_moderation.py`, `_context_ui.py`. User-facing API inside handlers (`ctx.respond()`, `ctx.send_embed()`, etc.). Use `ctx.user` and `ctx.member` — `ctx.author` does not exist.

**Decorators** — `decorators.py`: `@slash`, `@on`, `@component`, `@modal`, `@message_command`, `@user_command`, `@task`, `@ai_tool`. Primary extension points for bot authors.

**Plugin system** — `plugin.py` defines `Plugin`. Bundled plugins in `plugins/`. Loaded via `bot.load_builtin_plugins()` (defined in `builtin_plugins.py`) or `bot.load_plugin()`.

**Registry** — `registry.py` tracks live slash commands, component handlers, and modal handlers. Commands accessible at `bot.registry.commands`.

**Database** — `database.py`: `SQLiteDatabase` and `MemoryDatabase` with per-guild namespacing. `GuildRecord` is the typed row abstraction.

**AI orchestration** — `orchestrator.py` routes across providers via `FallbackStrategy` (advances through providers on failure, raises `IndexError` on exhaustion). Provider adapters in `plugins/_ai_providers.py` — all provider classes are also exported directly from `easycord` via lazy imports (Anthropic, OpenAI, Gemini, Groq, Mistral, Hugging Face, Together AI, Ollama, LiteLLM). Tools registered in `tools.py` via `ToolRegistry`, gated by `ToolSafety`. Built-in tools in `builtin_tools.py`. Per-tool rate limiting in `tool_limits.py` — `ToolLimiter` methods are async, must be awaited.

**OpenClawPlugin** — `plugins/openclaw.py`: autonomous agent runner with per-guild task history and `/openclaw_task` / `/openclaw_stop` slash commands.

**Plugin AI tools** — `@ai_tool` on plugin methods can declare safety level, admin/guild requirements, role/user gates, timeouts, and rate limits; they register automatically into `bot.tool_registry`.

**Localization** — `i18n.py` (`LocalizationManager`): fallback chain (user → guild → system → default). Diagnostic modes: `SILENT`, `WARN`, `STRICT`.

**Middleware** — `middleware.py`: logging, auth, rate limiting applied around command dispatch.

**Composer** — `composer.py`: fluent builder API as an alternative to direct `Bot` instantiation.

**Managers** — `managers.py`: high-level setup presets for common configurations.

**Embed cards** — `embed_cards.py`: `EmbedCard` bundles a `discord.Embed` with an optional `discord.ui.View`.
