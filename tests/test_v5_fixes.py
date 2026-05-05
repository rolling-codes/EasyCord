"""Tests covering all v5.0.0 bug fixes."""
from __future__ import annotations

import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from easycord.orchestrator import FallbackStrategy, RunContext
from easycord.tool_limits import RateLimit, ToolLimiter
from easycord.tools import ToolRegistry, ToolResult, ToolSafety


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
# Orchestrator — provider failure logging
# ---------------------------------------------------------------------------

class TestOrchestratorLogging:
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
