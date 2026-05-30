## EasyCord v5.43.0 - 2026-05-30

### Added
- **Phase 1: Orchestration Loop** — Core AI orchestration with multi-step tool execution:
  - `Orchestrator` class for intelligent provider routing and tool-call loop management
  - `RunContext` dataclass for configuring orchestration: messages, context, max_steps, timeout_ms, system_prompt, conversation_memory
  - `FallbackStrategy` for multi-provider resilience (tries providers in sequence, advances on failure)
  - `ProviderStrategy` abstract base for custom provider selection strategies
  - Tool execution with permission gates: guild-only, admin-only, role-gated, user-allowlisted, rate-limited
  - Step accounting: counts provider queries (max_steps), accumulates in FinalResponse
  - Timeout enforcement: orchestrator loop enforced via asyncio.wait_for (configurable, default 30s)
  - Tool result message protocol: appends success/failure status to message history
  - Memory integration: ConversationMemory updated only on final response (not on errors or timeouts)
  - Multi-provider fallback: linear chain advances through providers on exception or invalid output
  - Per-tool audit fields: ToolCall.id, ToolResult.tool_id, ToolResult.tool_name for call tracking

### Documentation
- Added RunContext parameter documentation in README.md: messages, ctx, max_steps, timeout_ms, system_prompt, conversation_memory
- Added FinalResponse return type documentation: text, provider, steps fields
- Documented tool execution success/failure semantics: not found, permission denied, timeout, execution error all append error message and retry same provider
- Documented provider fallback behavior: exception or invalid output triggers advance to next provider; permission denials do NOT trigger fallback
- Documented memory update timing: ConversationMemory updated only on final response, NOT on timeout or max_steps_reached

### Verification
- `pytest tests/test_orchestrator_phase1.py` — 13 Phase 1 tests passing
- `pytest tests/` — 584 tests passing (all existing tests continue to pass, no regressions)
- `python -m compileall .` — zero compilation errors
- All version metadata consistent (v5.43.0 in pyproject.toml, __init__.py, CHANGELOG.md, README.md badges, and release URLs)

### Release Assets

Download from https://github.com/rolling-codes/EasyCord/releases:
- releases/download/v5.43.0/easycord-5.43.0-py3-none-any.whl — Python wheel
- releases/download/v5.43.0/easycord-5.43.0.tar.gz — Source distribution
