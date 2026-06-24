# Architecture

EasyCord is a Discord bot framework (Python 3.10+, depends on `discord.py>=2.7.1,<3`). Entry point: `easycord/__init__.py` is the stable public API — internal modules are prefixed `_`. Current version lives in `pyproject.toml`/`easycord/__init__.py.__version__`, not here — don't hardcode it in this doc.

## Layers

**Bot core** — `bot.py` composes `discord.Client` + four mixins: `_bot_commands.py`, `_bot_events.py`, `_bot_guild.py`, `_bot_plugins.py`. New bot-level behavior goes into the relevant mixin. Each mixin inherits `_bot_base.py`'s `_BotBase` only under `TYPE_CHECKING` (via a per-module `_MixinBase` alias) so static checkers see the full composed `Bot` surface without creating a real runtime import cycle — `_BotBase` is never instantiated.

**Context** — `context.py` + `_context_base.py`, `_context_channels.py`, `_context_moderation.py`, `_context_ui.py`. User-facing API inside handlers (`ctx.respond()`, `ctx.send()`, `ctx.send_embed()`, etc.). Use `ctx.user` and `ctx.member` — `ctx.author` does not exist.

**Decorators** — `decorators.py`: `@slash` / `@slash_command`, `@autocomplete`, `@on`, `@component`, `@modal`, `@message_command`, `@user_command`, `@task`, `@ai_tool`, `@cooldown`, `@require_permissions`, `@install_type`, and `@premium_required`. Primary extension points for bot authors.

**Interaction registry** — `registry.py`: authoritative EasyCord inventory for slash commands, context menus, components, modals, and autocomplete callbacks. Discord sync still goes through `discord.app_commands.CommandTree`.

**Plugin system** — `plugin.py` defines `Plugin`. Bundled plugins live in `plugins/`. `bot.load_builtin_plugins()` loads the starter set from `builtin_plugins.py` (welcome, tags, polls, levels). Load other plugins explicitly with `bot.add_plugin(...)`; unload/reload existing plugin instances with `bot.remove_plugin()` / `bot.reload_plugin()`.

**Config and testing** — `config.py` defines `BotConfig` for env/file startup, including guild-scoped command sync. `testing.py` provides `FakeContext` and `invoke()` for command tests without a Discord connection.


**Database** — `database.py`: `SQLiteDatabase` and `MemoryDatabase` with per-guild namespacing. `GuildRecord` is the typed row abstraction.

**AI orchestration** — `orchestrator.py` routes across providers via `FallbackStrategy` (advances through providers on failure, raises `IndexError` on exhaustion). Provider adapters in `plugins/_ai_providers.py` — all provider classes are also exported directly from `easycord` via lazy imports (Anthropic, OpenAI, Gemini, Groq, Mistral, Hugging Face, Together AI, Ollama, LiteLLM). Tools registered in `tools.py` via `ToolRegistry`, gated by `ToolSafety`. Built-in tools in `builtin_tools.py`. Per-tool rate limiting in `tool_limits.py` — `ToolLimiter` methods are async, must be awaited.

**OpenClawPlugin** — `plugins/openclaw.py`: autonomous agent runner with per-guild task history and `/openclaw`, `/openclaw-task`, `/openclaw-status`, `/openclaw-stop`, `/openclaw-history` slash commands.

**Plugin AI tools** — `@ai_tool` on plugin methods can declare safety level, admin/guild requirements, role/user gates, timeouts, and rate limits; they register automatically into `bot.tool_registry`.

**Localization** — `i18n.py` (`LocalizationManager`): fallback chain (user → guild → system → default). Diagnostic modes: `SILENT`, `WARN`, `STRICT`.

**Middleware** — `middleware.py`: logging, auth, rate limiting applied around command dispatch.

**Composer** — `composer.py`: fluent builder API as an alternative to direct `Bot` instantiation.

**Managers** — `managers.py`: high-level setup presets for common configurations.

**Embed cards** — `embed_cards.py`: `EmbedCard` bundles a `discord.Embed` with an optional `discord.ui.View`.
