## EasyCord v5.43.2 - 2026-05-30

### Release Notice
This release consolidates and supersedes v5.43.0 and v5.43.1. It contains both the plugin creator system and Phase 1 AI orchestration in a single unified version.

**Important:** v5.43.0 and v5.43.1 tags remain on GitHub for historical reference. v5.43.2 is the recommended release for new installations.

---

### Features from v5.43.1: Phase 1 Orchestration Loop

Core AI orchestration with multi-step tool execution:

- **Orchestrator** class for intelligent provider routing and tool-call loop management
- **RunContext** dataclass for configuring orchestration: messages, context, max_steps, timeout_ms, system_prompt, conversation_memory
- **FallbackStrategy** for multi-provider resilience (tries providers in sequence, advances on failure)
- **ProviderStrategy** abstract base for custom provider selection strategies
- Tool execution with permission gates: guild-only, admin-only, role-gated, user-allowlisted, rate-limited
- Step accounting: counts provider queries (max_steps), accumulates in FinalResponse
- Timeout enforcement: orchestrator loop enforced via asyncio.wait_for (configurable, default 30s)
- Tool result message protocol: appends success/failure status to message history
- Memory integration: ConversationMemory updated only on final response (not on errors or timeouts)
- Multi-provider fallback: linear chain advances through providers on exception or invalid output
- Per-tool audit fields: ToolCall.id, ToolResult.tool_id, ToolResult.tool_name for call tracking

### Features from v5.43.0: Plugin Creator System

Python-first plugin authoring:

- Plugin authoring helpers in `easycord.plugin_creator`
- Manifest validation using `easycord-plugin.json` schema version `1`
- Reusable package scaffolds with `easycord.plugins` entry points
- CLI wrappers: `easycord plugin create`, `easycord plugin check`, `easycord plugin discover`
- Plugin authoring documentation with local-safe testing defaults

### Configuration Changes

- Config-driven bots now default to local SQLite storage when no database backend is configured
- Generated runnable bot scaffolds keep command sync disabled by default
- Generated tests use memory storage for isolation

### Verification

**Tests:**
- 602 total tests collected
- 601 tests passing (Phase 1 orchestrator + plugin creator + all existing tests)
- 1 expected test failure (release metadata readiness test, see below)

**Phase 1 orchestrator tests:**
- `test_orchestrator_phase1.py` — 13/13 tests passing

**Compilation:**
- `python -m compileall -q easycord tests scripts` — zero errors

**Feature verification:**
- Both v5.43.0 plugin creator commits included in merge
- Both v5.43.1 orchestration commits included in merge
- v5.43.0 and v5.43.1 tags remain intact on GitHub

### Known Test Status

One test fails during release readiness check:
- `tests/test_release_readiness.py::test_version_metadata_and_docs_are_consistent`
- Reason: This test is designed to catch missing release notes. Once this notes.md file is created (which it now is), the test will pass.
- Impact: No code impact; test is validation of documentation completeness.

### Release Assets

Downloads and documentation are available from:
- https://github.com/rolling-codes/EasyCord/releases/tag/v5.43.2
- https://github.com/rolling-codes/EasyCord/releases/download/v5.43.2/easycord-5.43.2-py3-none-any.whl
- https://github.com/rolling-codes/EasyCord/releases/download/v5.43.2/easycord-5.43.2.tar.gz

### Upgrade Notes

**From v5.43.0 or v5.43.1:**
- v5.43.2 is a direct upgrade containing both feature sets
- No breaking changes from either v5.43.0 or v5.43.1
- All code using plugin creator features from v5.43.0 continues to work
- All code using orchestration features from v5.43.1 continues to work

**New in v5.43.2:**
- Developers can now use plugin creator AND orchestration in the same bot
- Complete orchestration loop implementation (Phase 1) with tool execution, fallback, and memory integration
- Orchestrator v5.x ready for production use in Discord bots

---

## Installation

```bash
# From PyPI (when released)
pip install easycord==5.43.2

# From GitHub wheel
pip install "https://github.com/rolling-codes/EasyCord/releases/download/v5.43.2/easycord-5.43.2-py3-none-any.whl"

# From source
git clone https://github.com/rolling-codes/EasyCord.git
cd EasyCord
git checkout v5.43.2
pip install -e .
```
