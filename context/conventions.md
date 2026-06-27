# Conventions

## Naming

- Bot mixins: `_bot_<area>.py` — context mixins: `_context_<area>.py`
- Internal modules prefixed `_` are not part of the public contract

## Invariants

- Per-guild state always goes through the database layer — never stored on the `Bot` instance directly
- `@ai_tool` requires an explicit `ToolSafety` annotation to register into `ToolRegistry`; plugin tools register automatically into `bot.tool_registry`
- Localization keys looked up via `LocalizationManager` — strings must not be hardcoded in plugin responses
- `ctx.is_admin` is a property, not a method — do not call it as `ctx.is_admin()`
- `ctx.user` and `ctx.member` are the correct context attributes — `ctx.author` does not exist
- `ToolLimiter` methods (`check_limit`, `reset_user`, `reset_tool`) are async — always await them
- Legacy AI providers accept only `query(prompt)` and return plain strings; tool-aware providers accept a `tools` schema argument — the orchestrator handles both
- Cooldown sentinels in `LevelsPlugin._cooldowns` default to `float("-inf")`, not `0.0` — this ensures the first message always passes the gate regardless of `time.monotonic()` value on fresh runners
- CI workflow actions are pinned to `actions/checkout@v4` and `actions/setup-python@v5` — v6 does not exist
- `LocalizationManager` metrics are guarded by an internal `threading.Lock`; mutate them only through `_record_metric` (never inline `+=`) so counters stay correct under sharded/multi-thread access. The lock is a no-op cost unless `track_metrics=True`
- Hot-reload and command dispatch are serialized by the bot-wide `_reload_lock` (`_get_reload_lock()`); a plugin swap (`remove_plugin → add_plugin → on_reload`) must run inside it, and dispatch acquires it only while `_hot_reload_active` (dev watcher running) so production stays lock-free
- Commands that call a privileged Discord API (kick/ban/timeout/role edits) declare `bot_permissions=[...]` on `@slash`; the bot's perms are validated at dispatch via `ctx.bot_permissions`, distinct from `permissions=`/`require_admin` which gate the invoking user. `require_admin` never implies the bot must be admin
- Standalone helper modules that receive the bot/plugin (`_command_registration.py`, `_plugin_scanner.py`) type those params as `_BotBase` / `Plugin` under `TYPE_CHECKING` — not `object` — so the composed surface resolves and mixin `self` stays assignable. New shared bot attributes must be declared in `_bot_base.py` (`_BotBase`) to stay visible to mixins and helpers
- `pyrightconfig.json` severity policy: **error** is reserved for diagnostics that actually break at runtime (`reportMissingImports`, `reportUndefinedVariable`, `reportPossiblyUnboundVariable`); real-but-noisy type checks (`reportReturnType`, `reportArgumentType`, `reportOptionalMemberAccess`, `reportAttributeAccessIssue`) are **warning**; and intentional dynamic patterns / pure annotation-style (`reportFunctionMemberAccess` — the decorator system stamps `_slash_*`/`_ai_tool_*`/`_is_*` onto functions; `reportIncompatibleMethodOverride` — the deliberate `discord.Client` override pattern; `reportMissingTypeArgument`; `reportUnknown*`) are **off**. Net: a green error baseline, so any error that appears is a genuine bug. Optional third-party provider SDKs in `plugins/_ai_providers.py` are imported lazily and carry `# pyright: ignore[reportMissingImports]`
