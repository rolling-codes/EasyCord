"""Tests covering all v5.0.0 bug fixes."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from easycord.orchestrator import FallbackStrategy, RunContext
from easycord.tool_limits import RateLimit, ToolLimiter
from easycord.tools import ToolCall, ToolRegistry, ToolResult, ToolSafety


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_provider(name: str = "FakeProvider") -> MagicMock:
    p = MagicMock()
    p.__class__.__name__ = name
    return p


def _make_run_ctx() -> MagicMock:
    return MagicMock(spec=RunContext)


def _make_ctx(
    *,
    user_id: int = 1,
    guild=None,
    is_admin: bool = False,
) -> MagicMock:
    """Return a fake Discord Context."""
    ctx = MagicMock()
    ctx.user = MagicMock()
    ctx.user.id = user_id
    ctx.guild = guild
    # is_admin must be a property (not a callable) — use PropertyMock
    type(ctx).is_admin = property(lambda self: is_admin)
    return ctx


# ---------------------------------------------------------------------------
# FallbackStrategy — the core v5 fix
# ---------------------------------------------------------------------------

class TestFallbackStrategy:
    def test_select_first_provider_on_attempt_0(self) -> None:
        p1, p2 = _make_provider("P1"), _make_provider("P2")
        strategy = FallbackStrategy([p1, p2])
        assert strategy.select(_make_run_ctx(), 0) is p1

    def test_select_second_provider_on_attempt_1(self) -> None:
        p1, p2 = _make_provider("P1"), _make_provider("P2")
        strategy = FallbackStrategy([p1, p2])
        assert strategy.select(_make_run_ctx(), 1) is p2

    def test_each_attempt_advances_provider(self) -> None:
        providers = [_make_provider(f"P{i}") for i in range(4)]
        strategy = FallbackStrategy(providers)
        selected = [strategy.select(_make_run_ctx(), i) for i in range(4)]
        assert selected == providers

    def test_raises_index_error_when_exhausted(self) -> None:
        strategy = FallbackStrategy([_make_provider()])
        with pytest.raises(IndexError):
            strategy.select(_make_run_ctx(), 1)

    def test_raises_on_empty_provider_list(self) -> None:
        strategy = FallbackStrategy([])
        with pytest.raises(IndexError):
            strategy.select(_make_run_ctx(), 0)


# ---------------------------------------------------------------------------
# ToolLimiter — async + thread-safe rate limiting
# ---------------------------------------------------------------------------

class TestToolLimiter:
    @pytest.mark.asyncio
    async def test_allows_calls_under_limit(self) -> None:
        limiter = ToolLimiter()
        limit = RateLimit(max_calls=3, window_minutes=60)
        for _ in range(3):
            allowed, reason = await limiter.check_limit(1, "tool", limit)
            assert allowed
            assert reason is None

    @pytest.mark.asyncio
    async def test_blocks_call_over_limit(self) -> None:
        limiter = ToolLimiter()
        limit = RateLimit(max_calls=2, window_minutes=60)
        await limiter.check_limit(1, "tool", limit)
        await limiter.check_limit(1, "tool", limit)
        allowed, reason = await limiter.check_limit(1, "tool", limit)
        assert not allowed
        assert reason is not None

    @pytest.mark.asyncio
    async def test_limits_are_per_user(self) -> None:
        limiter = ToolLimiter()
        limit = RateLimit(max_calls=1, window_minutes=60)
        await limiter.check_limit(1, "tool", limit)
        # user 2 should still be allowed
        allowed, _ = await limiter.check_limit(2, "tool", limit)
        assert allowed

    @pytest.mark.asyncio
    async def test_limits_are_per_tool(self) -> None:
        limiter = ToolLimiter()
        limit = RateLimit(max_calls=1, window_minutes=60)
        await limiter.check_limit(1, "tool_a", limit)
        # different tool should still be allowed
        allowed, _ = await limiter.check_limit(1, "tool_b", limit)
        assert allowed

    @pytest.mark.asyncio
    async def test_reset_user_clears_limits(self) -> None:
        limiter = ToolLimiter()
        limit = RateLimit(max_calls=1, window_minutes=60)
        await limiter.check_limit(1, "tool", limit)
        await limiter.reset_user(1)
        allowed, _ = await limiter.check_limit(1, "tool", limit)
        assert allowed

    @pytest.mark.asyncio
    async def test_reset_tool_clears_limits(self) -> None:
        limiter = ToolLimiter()
        limit = RateLimit(max_calls=1, window_minutes=60)
        await limiter.check_limit(1, "tool", limit)
        await limiter.reset_tool("tool")
        allowed, _ = await limiter.check_limit(1, "tool", limit)
        assert allowed

    @pytest.mark.asyncio
    async def test_concurrent_calls_are_safe(self) -> None:
        """Multiple concurrent callers must not bypass the limit."""
        limiter = ToolLimiter()
        limit = RateLimit(max_calls=5, window_minutes=60)
        results = await asyncio.gather(
            *[limiter.check_limit(1, "tool", limit) for _ in range(10)]
        )
        allowed_count = sum(1 for allowed, _ in results if allowed)
        assert allowed_count == 5

    @pytest.mark.asyncio
    async def test_check_limit_is_a_coroutine(self) -> None:
        limiter = ToolLimiter()
        limit = RateLimit(max_calls=1, window_minutes=60)
        coro = limiter.check_limit(1, "tool", limit)
        assert asyncio.iscoroutine(coro)
        await coro


# ---------------------------------------------------------------------------
# ToolRegistry — async can_execute + is_admin as property
# ---------------------------------------------------------------------------

class TestToolRegistry:
    def _registry_with_tool(
        self,
        *,
        require_guild: bool = False,
        require_admin: bool = False,
        rate_limit=None,
    ) -> ToolRegistry:
        registry = ToolRegistry()
        registry.register(
            name="test_tool",
            func=lambda ctx: "ok",
            description="A test tool",
            safety=ToolSafety.SAFE,
            require_guild=require_guild,
            require_admin=require_admin,
            rate_limit=rate_limit,
        )
        return registry

    @pytest.mark.asyncio
    async def test_can_execute_is_async(self) -> None:
        registry = self._registry_with_tool()
        ctx = _make_ctx()
        coro = registry.can_execute(ctx, "test_tool")
        assert asyncio.iscoroutine(coro)
        await coro

    @pytest.mark.asyncio
    async def test_can_execute_allows_basic_tool(self) -> None:
        registry = self._registry_with_tool()
        ctx = _make_ctx()
        allowed, reason = await registry.can_execute(ctx, "test_tool")
        assert allowed
        assert reason is None

    @pytest.mark.asyncio
    async def test_can_execute_denies_unknown_tool(self) -> None:
        registry = self._registry_with_tool()
        ctx = _make_ctx()
        allowed, _ = await registry.can_execute(ctx, "no_such_tool")
        assert not allowed

    @pytest.mark.asyncio
    async def test_can_execute_reads_is_admin_as_property(self) -> None:
        """is_admin must be read as a property, not called as a method."""
        registry = self._registry_with_tool(require_admin=True)
        admin_ctx = _make_ctx(is_admin=True)
        allowed, _ = await registry.can_execute(admin_ctx, "test_tool")
        assert allowed

        non_admin_ctx = _make_ctx(is_admin=False)
        allowed, _ = await registry.can_execute(non_admin_ctx, "test_tool")
        assert not allowed

    @pytest.mark.asyncio
    async def test_can_execute_enforces_rate_limit(self) -> None:
        limit = RateLimit(max_calls=1, window_minutes=60)
        registry = self._registry_with_tool(rate_limit=limit)
        ctx = _make_ctx()
        allowed, _ = await registry.can_execute(ctx, "test_tool")
        assert allowed
        allowed, reason = await registry.can_execute(ctx, "test_tool")
        assert not allowed
        assert reason is not None

    def test_list_available_works_synchronously(self) -> None:
        registry = self._registry_with_tool()
        ctx = _make_ctx()
        tools = registry.list_available(ctx)
        assert any(t.name == "test_tool" for t in tools)

    @pytest.mark.asyncio
    async def test_execute_returns_result(self) -> None:
        registry = self._registry_with_tool()
        ctx = _make_ctx()
        from easycord.tools import ToolCall
        call = ToolCall(name="test_tool")
        result = await registry.execute(ctx, call)
        assert result.success
        assert result.output == "ok"

    @pytest.mark.asyncio
    async def test_execute_unknown_tool_returns_failure(self) -> None:
        registry = self._registry_with_tool()
        ctx = _make_ctx()
        from easycord.tools import ToolCall
        call = ToolCall(name="missing_tool")
        result = await registry.execute(ctx, call)
        assert not result.success

    def test_disabled_tool_not_in_list_available(self) -> None:
        registry = self._registry_with_tool()
        ctx = _make_ctx()
        registry.disable("test_tool")
        tools = registry.list_available(ctx)
        assert not any(t.name == "test_tool" for t in tools)


# ---------------------------------------------------------------------------
# ToolCall/ToolResult — audit fields (id, tool_id, tool_name, mutations)
# ---------------------------------------------------------------------------

class TestToolAuditFields:
    def test_tool_call_id_auto_generates(self) -> None:
        """ToolCall.id auto-generates as 32-char hex string."""
        call = ToolCall(name="test_tool")
        assert call.id is not None
        assert isinstance(call.id, str)
        assert len(call.id) == 32
        assert all(c in "0123456789abcdef" for c in call.id)

    def test_tool_call_id_unique_per_call(self) -> None:
        """Each ToolCall has a unique id."""
        calls = [ToolCall(name="test_tool") for _ in range(100)]
        ids = [call.id for call in calls]
        assert len(ids) == len(set(ids))  # All unique

    def test_tool_call_id_explicit_support(self) -> None:
        """ToolCall.id can be explicitly provided."""
        custom_id = "mycustom123456789abcdefghijklmn"
        call = ToolCall(name="test_tool", id=custom_id)
        assert call.id == custom_id

    def test_tool_result_legacy_construction(self) -> None:
        """ToolResult supports backward-compatible construction."""
        # Old-style: positional success, output as positional
        result1 = ToolResult(success=True, output="ok")
        assert result1.success is True
        assert result1.output == "ok"
        assert result1.error is None

        # New-style: with audit fields
        result2 = ToolResult(success=True, output="ok", tool_id="id123", tool_name="tool")
        assert result2.success is True
        assert result2.tool_id == "id123"
        assert result2.tool_name == "tool"

    def test_tool_result_tool_id_preserved(self) -> None:
        """ToolResult.tool_id is preserved after tool execution."""
        registry = ToolRegistry()
        registry.register(
            name="test_tool",
            func=lambda ctx: "ok",
            description="A test tool",
            safety=ToolSafety.SAFE,
            require_guild=False,
        )
        call = ToolCall(name="test_tool")
        ctx = _make_ctx()

        result = asyncio.run(registry.execute(ctx, call))

        assert result.tool_id == call.id
        assert result.success is True

    def test_tool_result_tool_name_preserved(self) -> None:
        """ToolResult.tool_name is preserved after tool execution."""
        registry = ToolRegistry()
        registry.register(
            name="test_tool",
            func=lambda ctx: "ok",
            description="A test tool",
            safety=ToolSafety.SAFE,
            require_guild=False,
        )
        call = ToolCall(name="test_tool")
        ctx = _make_ctx()

        result = asyncio.run(registry.execute(ctx, call))

        assert result.tool_name == call.name
        assert result.tool_name == "test_tool"

    def test_tool_result_mutations_fresh_per_instance(self) -> None:
        """ToolResult.mutations defaults to a fresh empty list per instance."""
        result1 = ToolResult(success=True, output="ok")
        result2 = ToolResult(success=True, output="ok")

        assert result1.mutations == []
        assert result2.mutations == []
        assert result1.mutations is not result2.mutations  # Different objects

    @pytest.mark.asyncio
    async def test_tool_result_failure_preserves_audit_fields(self) -> None:
        """Failed tool execution preserves tool_id, tool_name, and sets success=False."""
        registry = ToolRegistry()
        registry.register(
            name="test_tool",
            func=lambda ctx: "ok",
            description="A test tool",
            safety=ToolSafety.SAFE,
            require_guild=False,
            timeout_ms=1,  # Very short timeout to trigger timeout error
        )

        async def slow_tool(ctx):
            await asyncio.sleep(10)
            return "never"

        registry.register(
            name="slow_tool",
            func=slow_tool,
            description="A slow test tool",
            safety=ToolSafety.SAFE,
            require_guild=False,
            timeout_ms=10,  # Short timeout
        )

        call = ToolCall(name="slow_tool")
        ctx = _make_ctx()

        result = await registry.execute(ctx, call)

        # Verify failure case populates audit fields
        assert result.success is False
        assert result.tool_id == call.id
        assert result.tool_name == call.name
        assert result.error == "Tool execution timeout"


# ---------------------------------------------------------------------------
# Orchestrator — provider failure logging
# ---------------------------------------------------------------------------

class TestOrchestratorLogging:
    @pytest.mark.asyncio
    async def test_run_supports_legacy_string_provider(self) -> None:
        from easycord.orchestrator import Orchestrator, RunContext

        class LegacyProvider:
            def __init__(self) -> None:
                self.prompt = None

            async def query(self, prompt: str) -> str:
                self.prompt = prompt
                return "legacy hello"

        provider = LegacyProvider()
        registry = ToolRegistry()
        orchestrator = Orchestrator(strategy=FallbackStrategy([provider]), tools=registry)
        ctx = _make_ctx()
        run_ctx = RunContext(messages=[{"role": "user", "content": "hi"}], ctx=ctx)

        response = await orchestrator.run(run_ctx)

        assert response.text == "legacy hello"
        assert provider.prompt == "user: hi"

    @pytest.mark.asyncio
    async def test_run_passes_tools_to_tool_aware_provider(self) -> None:
        from easycord.orchestrator import Orchestrator, RunContext

        class ToolAwareProvider:
            def __init__(self) -> None:
                self.tools = None

            async def query(self, prompt: str, tools=None):
                self.tools = tools
                output = MagicMock()
                output.tool_call = None
                output.text = "tool-aware hello"
                return output

        provider = ToolAwareProvider()
        registry = ToolRegistry()
        registry.register(
            name="lookup",
            func=lambda ctx: "ok",
            description="Lookup data",
            safety=ToolSafety.SAFE,
            require_guild=False,
        )
        orchestrator = Orchestrator(strategy=FallbackStrategy([provider]), tools=registry)
        ctx = _make_ctx()
        run_ctx = RunContext(messages=[{"role": "user", "content": "hi"}], ctx=ctx)

        response = await orchestrator.run(run_ctx)

        assert response.text == "tool-aware hello"
        assert provider.tools is not None
        assert provider.tools[0]["function"]["name"] == "lookup"

    @pytest.mark.asyncio
    async def test_provider_failure_emits_warning(self) -> None:
        from easycord.orchestrator import Orchestrator, RunContext

        failing_provider = MagicMock()
        failing_provider.query = AsyncMock(side_effect=RuntimeError("boom"))
        type(failing_provider).__name__ = "FailingProvider"

        ok_provider = MagicMock()
        ok_output = MagicMock()
        ok_output.tool_call = None
        ok_output.text = "hello"
        ok_provider.query = AsyncMock(return_value=ok_output)
        type(ok_provider).__name__ = "OkProvider"

        strategy = FallbackStrategy([failing_provider, ok_provider])
        registry = ToolRegistry()
        orchestrator = Orchestrator(strategy=strategy, tools=registry)

        ctx = _make_ctx()
        run_ctx = RunContext(
            messages=[{"role": "user", "content": "hi"}],
            ctx=ctx,
            max_steps=5,
        )

        with patch("easycord.orchestrator.logger") as mock_logger:
            response = await orchestrator.run(run_ctx)
            mock_logger.warning.assert_called_once()
            warning_args = mock_logger.warning.call_args[0]
            assert "FailingProvider" in warning_args[1]

        assert response.text == "hello"

# ---------------------------------------------------------------------------
# Release blocker regressions
# ---------------------------------------------------------------------------

class TestReleaseBlockerRegressions:
    def test_context_builder_uses_context_user_and_member(self) -> None:
        from easycord.context_builder import ContextBuilder

        ctx = _make_ctx(guild=MagicMock())
        ctx.guild.name = "Guild"
        ctx.guild.id = 100
        ctx.guild.members = [MagicMock()]
        mod_role = MagicMock()
        mod_role.name = "Mods"
        mod_role.id = 5
        mod_role.position = 1
        mod_role.permissions.manage_messages = True
        ctx.guild.roles = [mod_role]
        ctx.guild.channels = [MagicMock()]
        ctx.user.name = "alice"
        member = MagicMock()
        member.top_role.name = "Admin"
        type(ctx).member = property(lambda self: member)

        state = ContextBuilder.build_bot_state_summary(ctx)
        prompt = ContextBuilder._format_state(ctx)

        assert state["user"]["name"] == "alice"
        assert state["user"]["top_role"] == "Admin"
        assert "Your Role:** Admin" in prompt

    @pytest.mark.asyncio
    async def test_builtin_list_roles_returns_permission_data(self) -> None:
        import json
        from easycord.builtin_tools import builtin_list_roles

        class Permissions:
            value = 8

            def __iter__(self):
                return iter([("administrator", True), ("manage_messages", False)])

        role = MagicMock()
        role.name = "Admin"
        role.id = 1
        role.position = 10
        role.permissions = Permissions()
        ctx = MagicMock()
        ctx.guild.roles = [role]

        data = json.loads(await builtin_list_roles(ctx))

        assert data["roles"][0]["permissions"]["value"] == 8
        assert data["roles"][0]["permissions"]["enabled"] == ["administrator"]

    @pytest.mark.asyncio
    async def test_orchestrator_supports_analysis_without_discord_context(self) -> None:
        from easycord.orchestrator import Orchestrator, RunContext

        class LegacyProvider:
            async def query(self, prompt: str) -> str:
                return "analysis complete"

        orchestrator = Orchestrator(
            strategy=FallbackStrategy([LegacyProvider()]),
            tools=ToolRegistry(),
        )
        response = await orchestrator.run(
            RunContext(messages=[{"role": "user", "content": "scan"}], ctx=None)
        )

        assert response.text == "analysis complete"

