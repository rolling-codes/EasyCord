"""Tests for AIPlugin / OpenClaudePlugin — rate limiting, pruning, prompt checks, and formatting."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from easycord.plugins._ai_providers import AIProvider
from easycord.plugins.openclaude import AIPlugin, OpenClaudePlugin


class FakeProvider(AIProvider):
    def __init__(self, reply: str = "Hello from AI") -> None:
        super().__init__(None, "test")
        self.reply = reply
        self.query_count = 0

    def _init_client(self) -> None:
        pass

    async def query(self, prompt: str) -> str:
        self.query_count += 1
        if "raise_import" in prompt:
            raise ImportError("Fake SDK not installed")
        if "raise_error" in prompt:
            raise RuntimeError("API failure")
        return self.reply


def _ctx(*, guild_id: int = 100, user_id: int = 1):
    ctx = MagicMock()
    ctx.guild = MagicMock()
    ctx.guild.id = guild_id
    ctx.guild_id = guild_id
    ctx.user = MagicMock()
    ctx.user.id = user_id
    ctx.respond = AsyncMock()
    ctx.defer = AsyncMock()
    ctx.edit_response = AsyncMock()
    # Simple localization mock
    ctx.t = lambda key, default, **kwargs: default.format(**kwargs)
    return ctx


class TestAIPlugin:
    def test_initialization(self) -> None:
        provider = FakeProvider()
        plugin = AIPlugin(provider, rate_limit=2, rate_window=10.0, max_prompt_chars=100)
        assert plugin._provider == provider
        assert plugin._rate_limit == 2
        assert plugin._rate_window == 10.0
        assert plugin._max_prompt_chars == 100

    @pytest.mark.asyncio
    async def test_ask_happy_path(self) -> None:
        provider = FakeProvider("Canned Response")
        plugin = AIPlugin(provider, rate_limit=5)
        ctx = _ctx()
        
        await plugin.ask(ctx, "hello")
        
        assert ctx.defer.call_count == 1
        ctx.respond.assert_called_once_with("Canned Response")
        assert provider.query_count == 1

    @pytest.mark.asyncio
    async def test_ask_truncation(self) -> None:
        long_reply = "A" * 3000
        provider = FakeProvider(long_reply)
        plugin = AIPlugin(provider)
        ctx = _ctx()
        
        await plugin.ask(ctx, "hello")
        
        # Verify response is truncated to <= 2000 chars and ends with ...
        response_sent = ctx.respond.call_args[0][0]
        assert len(response_sent) == 2000
        assert response_sent.endswith("...")

    @pytest.mark.asyncio
    async def test_ask_thinking_key(self) -> None:
        provider = FakeProvider("Thoughtful response")
        plugin = AIPlugin(provider, thinking_key="thinking...")
        ctx = _ctx()
        
        await plugin.ask(ctx, "hello")
        
        # First calls respond with the thinking message
        ctx.respond.assert_any_call("Thinking...")
        # Then calls edit_response with the final response
        ctx.edit_response.assert_called_once_with("Thoughtful response")

    @pytest.mark.asyncio
    async def test_max_prompt_chars(self) -> None:
        provider = FakeProvider()
        plugin = AIPlugin(provider, max_prompt_chars=10)
        ctx = _ctx()
        
        await plugin.ask(ctx, "too long prompt here")
        
        assert provider.query_count == 0
        assert ctx.defer.call_count == 0
        assert "too long" in ctx.respond.call_args[0][0].lower()
        assert ctx.respond.call_args[1]["ephemeral"] is True

    @pytest.mark.asyncio
    async def test_rate_limiting_triggered(self) -> None:
        provider = FakeProvider()
        # Allow 2 requests per 60s
        plugin = AIPlugin(provider, rate_limit=2, rate_window=60.0)
        ctx = _ctx(user_id=42)
        
        # First request
        await plugin.ask(ctx, "first")
        # Second request
        await plugin.ask(ctx, "second")
        # Third request - should be blocked
        await plugin.ask(ctx, "third")
        
        assert provider.query_count == 2
        # Verify the third response indicates rate limit
        assert "asking too quickly" in ctx.respond.call_args[0][0].lower()
        assert ctx.respond.call_args[1]["ephemeral"] is True

    @pytest.mark.asyncio
    async def test_rate_limiting_pruning(self) -> None:
        provider = FakeProvider()
        plugin = AIPlugin(provider, rate_limit=1, rate_window=0.01)
        ctx = _ctx(user_id=99)
        
        # First request
        await plugin.ask(ctx, "first")
        
        # Sleep to let window expire
        await asyncio.sleep(0.02)
        
        # Second request should succeed because of pruning / window expiration
        await plugin.ask(ctx, "second")
        
        assert provider.query_count == 2

    @pytest.mark.asyncio
    async def test_handle_import_error(self) -> None:
        provider = FakeProvider()
        plugin = AIPlugin(provider)
        ctx = _ctx()
        
        await plugin.ask(ctx, "raise_import")
        
        assert ctx.respond.call_args[1]["ephemeral"] is True
        assert "not installed" in ctx.respond.call_args[0][0]

    @pytest.mark.asyncio
    async def test_handle_generic_error(self) -> None:
        provider = FakeProvider()
        plugin = AIPlugin(provider)
        ctx = _ctx()
        
        await plugin.ask(ctx, "raise_error")
        
        assert ctx.respond.call_args[1]["ephemeral"] is True
        assert "error calling ai" in ctx.respond.call_args[0][0].lower()


class TestOpenClaudePlugin:
    def test_openclaude_wraps_aiplugin(self) -> None:
        plugin = OpenClaudePlugin(api_key="fake-key", rate_limit=5)
        assert plugin._rate_limit == 5
        assert plugin._thinking_key == "openclaude.thinking"
        assert plugin._provider.__class__.__name__ == "AnthropicProvider"
