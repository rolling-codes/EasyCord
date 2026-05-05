# Changelog

## EasyCord v5.0.0 - 2026-05-05

### What's New
- Promoted EasyCord to a production-stable 5.0.0 release with Python 3.13 classifier support and `easycord.__version__ = "5.0.0"`.
- Exposed all built-in AI provider classes directly from `easycord` through lazy imports, including Anthropic, OpenAI, Gemini, Groq, Mistral, Hugging Face, Together AI, Ollama, and LiteLLM providers.
- Expanded `@ai_tool` support so plugin tools can declare safety level, admin/guild requirements, role/user gates, timeouts, and rate limits, then register automatically into `bot.tool_registry`.
- Added comprehensive regression coverage across context helpers, database behavior, localization, middleware, plugins, server config, utility helpers, and v5 release fixes.

### Bug Fixes
- Fixed fallback provider selection so `FallbackStrategy` advances through providers and reports exhaustion correctly.
- Fixed `ctx.is_admin` usage across tool permissions and AI context building by reading it as a property instead of calling it as a method.
- Fixed async rate-limit handling by awaiting `ToolLimiter.check_limit`, `reset_user`, and `reset_tool` in helpers and moderation plugins.
- Fixed AI orchestration compatibility with legacy providers that return plain strings and accept only `query(prompt)`, while still passing tool schemas to tool-aware providers.
- Fixed AI moderation analysis runs that intentionally have no Discord command context by disabling tool exposure and guarding conversation-memory writes.
- Fixed built-in role listing so role permissions serialize as a permission value and enabled permission names instead of raising at runtime.
- Fixed Discord context state snapshots to use `ctx.user` and `ctx.member` instead of the nonexistent `ctx.author` attribute.
- Replaced deprecated event-loop usage in AI providers with `asyncio.get_running_loop()`.

### Verification
- `py -3 -m pytest tests` -> 352 passed.
- `py -3 -m build` -> built `easycord-5.0.0.tar.gz` and `easycord-5.0.0-py3-none-any.whl`.
