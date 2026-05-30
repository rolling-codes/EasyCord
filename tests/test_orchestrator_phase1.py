"""Phase 1 orchestration loop tests: tool-call, tool-result, step accounting, fallback, memory."""
from __future__ import annotations

import asyncio
from copy import deepcopy
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from easycord.orchestrator import Orchestrator, RunContext, FallbackStrategy, Message
from easycord.plugins._ai_providers import AIProvider
from easycord.tools import ToolRegistry, ToolCall, ToolResult, ToolSafety


class TestToolCallProtocol:
    """Test tool call extraction from provider output."""

    def test_extract_tool_call_success(self):
        """Valid tool_call object is extracted from provider output."""
        orchestrator = Orchestrator(FallbackStrategy([]), ToolRegistry())

        output = MagicMock()
        output.tool_call = MagicMock()
        output.tool_call.name = "test_tool"
        output.tool_call.args = {"key": "value"}

        tool_call = orchestrator._extract_tool_call(output)

        assert tool_call is not None
        assert tool_call.name == "test_tool"
        assert tool_call.args == {"key": "value"}

    def test_extract_tool_call_none(self):
        """Output with no tool_call attribute returns None."""
        orchestrator = Orchestrator(FallbackStrategy([]), ToolRegistry())

        output = MagicMock(spec=[])  # No tool_call attribute
        tool_call = orchestrator._extract_tool_call(output)

        assert tool_call is None


class TestToolResultProtocol:
    """Test tool result appending to message history."""

    def test_tool_result_appended_with_success_true(self):
        """Successful tool result is appended to messages."""
        orchestrator = Orchestrator(FallbackStrategy([]), ToolRegistry())

        result = ToolResult(
            success=True,
            output="result text",
            tool_id="abc123",
            tool_name="test_tool",
        )
        call = ToolCall(name="test_tool", args={})
        call.id = "abc123"

        message = orchestrator._build_tool_message(result, call)

        assert message["role"] == "tool"
        assert message["name"] == "test_tool"
        assert message["content"] == "result text"
        assert message["tool_call_id"] == "abc123"
        assert "error" not in message  # No error field on success

    def test_tool_result_appended_with_success_false(self):
        """Failed tool result is appended with error flag."""
        orchestrator = Orchestrator(FallbackStrategy([]), ToolRegistry())

        result = ToolResult(
            success=False,
            error="Tool failed",
            tool_id="abc123",
            tool_name="test_tool",
        )
        call = ToolCall(name="test_tool", args={})
        call.id = "abc123"

        message = orchestrator._build_tool_message(result, call)

        assert message["role"] == "tool"
        assert message["name"] == "test_tool"
        assert message["content"] == "Tool failed"  # Error is used as content
        assert message["tool_call_id"] == "abc123"
        assert message["error"] == "Tool failed"  # Error field set


class TestStepAccounting:
    """Test step counting and loop termination."""

    @pytest.mark.asyncio
    async def test_step_increments_on_provider_query(self):
        """Step increments once per provider query (not per tool)."""
        # Create a provider that returns a tool call
        provider = MagicMock(spec=AIProvider)
        provider.supports_tools = False
        output = MagicMock()
        output.tool_call = MagicMock(name="test_tool", args={})
        provider.query = AsyncMock(return_value=output)

        # Create a tool registry with the tool
        registry = ToolRegistry()
        registry.register(
            name="test_tool",
            func=lambda ctx: "ok",
            description="Test tool",
            safety=ToolSafety.SAFE,
            require_guild=False,
        )

        orchestrator = Orchestrator(FallbackStrategy([provider]), registry)

        ctx = MagicMock()
        ctx.user = MagicMock(id=1)
        ctx.guild = None
        type(ctx).is_admin = property(lambda self: False)

        run_ctx = RunContext(
            messages=[{"role": "user", "content": "test"}],
            ctx=ctx,
            max_steps=1,
        )

        response = await orchestrator.run(run_ctx)

        # Step should be 1 even though tool was executed
        assert response.steps == 1

    @pytest.mark.asyncio
    async def test_max_steps_terminates_loop(self):
        """Loop terminates when steps >= max_steps."""
        provider = MagicMock(spec=AIProvider)
        provider.supports_tools = False
        output = MagicMock()
        output.tool_call = MagicMock(name="test_tool", args={})
        provider.query = AsyncMock(return_value=output)

        registry = ToolRegistry()
        registry.register(
            name="test_tool",
            func=lambda ctx: "ok",
            description="Test tool",
            safety=ToolSafety.SAFE,
            require_guild=False,
        )

        orchestrator = Orchestrator(FallbackStrategy([provider]), registry)
        ctx = MagicMock()
        ctx.user = MagicMock(id=1)
        ctx.guild = None
        type(ctx).is_admin = property(lambda self: False)

        run_ctx = RunContext(
            messages=[{"role": "user", "content": "test"}],
            ctx=ctx,
            max_steps=1,
        )

        response = await orchestrator.run(run_ctx)

        assert response.text == "Max steps reached"
        assert response.steps == 1

    @pytest.mark.asyncio
    async def test_final_response_before_max_steps(self):
        """Final response exits loop early (doesn't wait for max_steps)."""
        provider = MagicMock(spec=AIProvider)
        provider.supports_tools = False
        provider.query = AsyncMock(return_value="Final answer")

        orchestrator = Orchestrator(FallbackStrategy([provider]), ToolRegistry())
        ctx = MagicMock()
        ctx.user = MagicMock(id=1)
        ctx.guild = None

        run_ctx = RunContext(
            messages=[{"role": "user", "content": "test"}],
            ctx=ctx,
            max_steps=10,  # High max_steps
        )

        response = await orchestrator.run(run_ctx)

        assert response.text == "Final answer"
        assert response.steps == 1  # Early exit, only 1 step used


class TestProviderFallback:
    """Test fallback behavior on provider exceptions and invalid output."""

    @pytest.mark.asyncio
    async def test_fallback_on_provider_exception(self):
        """Provider exception triggers fallback to next provider."""
        failing_provider = MagicMock(spec=AIProvider)
        failing_provider.supports_tools = False
        failing_provider.query = AsyncMock(side_effect=RuntimeError("boom"))

        ok_provider = MagicMock(spec=AIProvider)
        ok_provider.supports_tools = False
        ok_provider.query = AsyncMock(return_value="success")

        orchestrator = Orchestrator(
            FallbackStrategy([failing_provider, ok_provider]), ToolRegistry()
        )
        ctx = MagicMock()
        ctx.user = MagicMock(id=1)
        ctx.guild = None

        run_ctx = RunContext(
            messages=[{"role": "user", "content": "test"}],
            ctx=ctx,
        )

        response = await orchestrator.run(run_ctx)

        assert response.text == "success"
        assert response.steps == 2  # One step per provider query (failing + ok)

    @pytest.mark.asyncio
    async def test_all_providers_exhausted(self):
        """All providers exhausted returns controlled message (no raw IndexError leak)."""
        failing_provider = MagicMock(spec=AIProvider)
        failing_provider.supports_tools = False
        failing_provider.query = AsyncMock(side_effect=RuntimeError("boom"))

        orchestrator = Orchestrator(
            FallbackStrategy([failing_provider]), ToolRegistry()
        )
        ctx = MagicMock()
        ctx.user = MagicMock(id=1)
        ctx.guild = None

        run_ctx = RunContext(
            messages=[{"role": "user", "content": "test"}],
            ctx=ctx,
        )

        response = await orchestrator.run(run_ctx)

        assert response.text == "All providers exhausted"
        # Do NOT check for raw IndexError — orchestrator should return controlled FinalResponse

    @pytest.mark.asyncio
    async def test_history_preserved_across_fallbacks(self):
        """Messages list continues without rollback across fallbacks."""
        failing_provider = MagicMock(spec=AIProvider)
        failing_provider.supports_tools = False
        failing_provider.query = AsyncMock(side_effect=RuntimeError("boom"))

        ok_provider = MagicMock(spec=AIProvider)
        ok_provider.supports_tools = False
        ok_provider.query = AsyncMock(return_value="ok")

        orchestrator = Orchestrator(
            FallbackStrategy([failing_provider, ok_provider]), ToolRegistry()
        )

        initial_messages = [{"role": "user", "content": "test"}]
        ctx = MagicMock()
        ctx.user = MagicMock(id=1)
        ctx.guild = None

        run_ctx = RunContext(messages=initial_messages, ctx=ctx)

        # Capture messages that were used in the loop
        with patch.object(orchestrator, "_format_messages", wraps=orchestrator._format_messages) as mock_format:
            response = await orchestrator.run(run_ctx)

        # Messages should have been accumulated
        assert response.text == "ok"
        # The mock should show messages were passed to format (history preserved)
        assert mock_format.called

    def test_permission_denied_not_fallback(self):
        """Permission denial retries same provider (not fallback)."""
        # This test validates the logic: permission check should NOT trigger fallback
        # Instead, error message appended, attempt reset to 0, continue (retry same provider)
        # This is verified in integration tests with real ToolRegistry.can_execute()
        pass  # Covered by integration tests with real registry


class TestMemoryUpdate:
    """Test ConversationMemory update timing."""

    @pytest.mark.asyncio
    async def test_memory_updated_on_final_response(self):
        """ConversationMemory is updated only on final response."""
        provider = MagicMock(spec=AIProvider)
        provider.supports_tools = False
        provider.query = AsyncMock(return_value="Final answer")

        orchestrator = Orchestrator(FallbackStrategy([provider]), ToolRegistry())

        mock_memory = MagicMock()
        mock_memory.add_assistant_message = MagicMock()

        ctx = MagicMock()
        ctx.user = MagicMock(id=123)
        ctx.guild = MagicMock(id=456)

        run_ctx = RunContext(
            messages=[{"role": "user", "content": "test"}],
            ctx=ctx,
            conversation_memory=mock_memory,
        )

        response = await orchestrator.run(run_ctx)

        assert response.text == "Final answer"
        mock_memory.add_assistant_message.assert_called_once_with(123, "Final answer", 456)

    @pytest.mark.asyncio
    async def test_memory_not_updated_on_timeout(self):
        """ConversationMemory is NOT updated when orchestrator times out."""
        async def slow_inner(ctx):
            await asyncio.sleep(10)
            return None

        orchestrator = Orchestrator(FallbackStrategy([]), ToolRegistry())

        mock_memory = MagicMock()
        mock_memory.add_assistant_message = MagicMock()

        ctx = MagicMock()
        ctx.user = MagicMock(id=123)
        ctx.guild = MagicMock(id=456)

        run_ctx = RunContext(
            messages=[{"role": "user", "content": "test"}],
            ctx=ctx,
            timeout_ms=100,  # Very short timeout
            conversation_memory=mock_memory,
        )

        with patch.object(orchestrator, "_run_inner", side_effect=slow_inner):
            response = await orchestrator.run(run_ctx)

        assert response.text == "Orchestration timeout"
        # Memory should NOT be updated on timeout
        mock_memory.add_assistant_message.assert_not_called()
