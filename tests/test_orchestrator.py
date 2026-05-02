"""Tests for the AI orchestrator compatibility layer."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from easycord.orchestrator import FallbackStrategy, Orchestrator, RunContext
from easycord.tools import ToolRegistry


def _make_ctx():
    ctx = MagicMock()
    ctx.user.id = 123
    ctx.guild = None
    return ctx


@pytest.mark.asyncio
async def test_orchestrator_supports_legacy_string_providers():
    """Legacy providers returning plain strings should still work."""
    provider = MagicMock()
    provider.query = AsyncMock(return_value="legacy response")
    orchestrator = Orchestrator(
        strategy=FallbackStrategy([provider]),
        tools=ToolRegistry(),
    )

    result = await orchestrator.run(
        RunContext(
            messages=[{"role": "user", "content": "hello world"}],
            ctx=_make_ctx(),
        )
    )

    assert result.text == "legacy response"
    provider.query.assert_awaited_once_with("USER: hello world")


@pytest.mark.asyncio
async def test_orchestrator_uses_tool_aware_provider_signature_when_available():
    """Tool-aware providers should receive the richer query signature."""
    provider = MagicMock()
    provider.query = AsyncMock(return_value=SimpleNamespace(text="tool aware", tool_call=None))
    orchestrator = Orchestrator(
        strategy=FallbackStrategy([provider]),
        tools=ToolRegistry(),
    )

    result = await orchestrator.run(
        RunContext(
            messages=[{"role": "user", "content": "hello world"}],
            ctx=_make_ctx(),
        )
    )

    assert result.text == "tool aware"
    provider.query.assert_awaited_once_with(prompt="USER: hello world", tools=None)
