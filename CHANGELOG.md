# Changelog

## EasyCord v5.1.1 - 2026-05-06

### Bug Fixes
- Fixed `LevelsPlugin._award_xp` cooldown sentinel — default of `0.0` caused the first-message XP award to be silently blocked on freshly-booted CI runners and any host where `time.monotonic()` starts below `cooldown_seconds`. Changed to `float("-inf")` so a user who has never sent a message always passes the cooldown gate.

### CI & Infra
- Corrected GitHub Actions versions across all three workflows — `actions/checkout@v6` and `actions/setup-python@v6` do not exist and resolved unpredictably. Pinned to `actions/checkout@v4` and `actions/setup-python@v5`.

### Verification
- `pytest tests/` → 411 passed.

---

## EasyCord v5.1.0 - 2026-05-06

### Bug Fixes
- Fixed `LevelsPlugin` role reward assignment — `isinstance(author, discord.Member)` returned `False` on Python 3.11 with specced mocks and in some runtime edge cases; replaced with `hasattr(author, "add_roles")` which is version-agnostic and semantically correct.
- Fixed orchestrator empty-string output — `result.output or result.error` would fall through to the error branch when the AI returned an empty string (a valid response); now uses `result.output if result.output is not None else result.error`.
- Fixed `ToolRegistry` role check crash in DMs — when `allowed_roles` was set but `require_guild=False`, accessing `ctx.member.roles` in a DM context raised `AttributeError`; now safely fetches the member from the guild or returns a permission-denied message.

### New
- Added `OpenClawPlugin` — autonomous agent runner with per-guild task history and `/openclaw_task` / `/openclaw_stop` slash commands.

### CI & Infra
- Pinned GitHub Actions to `actions/checkout@v4` and `actions/setup-python@v5` across all CI workflows — v6 does not exist and resolved unpredictably.
- Fixed `LevelsPlugin._award_xp` cooldown sentinel from `0.0` to `float("-inf")` — on freshly-booted CI runners `time.monotonic()` can be under 60 s, causing the first-message cooldown check to silently block all XP awards.
- Added `test_levels_plugin.py` and `test_openclaw.py` — 411 tests now passing.
- Added `CLAUDE.md`, `AGENTS.md`, and `context/` architecture and conventions docs.

### Verification
- `pytest tests/` → 411 passed.

---

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

### Release Assets
- `EasyCord-v5.0.0.zip`: clean installable package archive with `easycord/`, README, changelog, license, package metadata, and context notes.
- `EasyCord-v5.0.0-dev.zip`: development and expansion archive with source, tests, package metadata, context notes, and sanitized development notes.

### Verification
- `py -3 -m pytest tests` -> 352 passed.
- Curated zip verification -> no nested package folder, no embedded archives, no cache files, no system-specific paths, and no personal information.
