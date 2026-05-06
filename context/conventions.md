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
