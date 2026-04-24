"""Tests for easycord.plugins.openclaude — OpenClaudePlugin."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from easycord.plugins.openclaude import OpenClaudePlugin


def test_init_requires_api_key():
    """Plugin requires ANTHROPIC_API_KEY or api_key param."""
    with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
        OpenClaudePlugin(api_key=None)


def test_init_with_api_key():
    """Plugin initializes with explicit API key."""
    plugin = OpenClaudePlugin(api_key="test-key")
    assert plugin._api_key == "test-key"


def test_init_with_env_var(monkeypatch):
    """Plugin reads ANTHROPIC_API_KEY from environment."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "env-key")
    plugin = OpenClaudePlugin()
    assert plugin._api_key == "env-key"


def test_model_customizable():
    """Plugin accepts custom model."""
    plugin = OpenClaudePlugin(api_key="test", model="claude-3-opus")
    assert plugin._model == "claude-3-opus"


@pytest.mark.asyncio
async def test_ask_command_defers_response():
    """Ask command defers response while calling API."""
    plugin = OpenClaudePlugin(api_key="test-key")
    ctx = MagicMock()
    ctx.defer = AsyncMock()
    ctx.respond = AsyncMock()

    with patch.object(plugin, "_init_client"):
        with patch.object(plugin, "_client") as mock_client:
            mock_response = MagicMock()
            mock_response.content = [MagicMock(text="Test response")]
            mock_client.messages.create.return_value = mock_response

            await plugin.ask(ctx, prompt="Test prompt")

            ctx.defer.assert_called_once()
            ctx.respond.assert_called_once_with("Test response")


@pytest.mark.asyncio
async def test_ask_command_truncates_long_responses():
    """Ask command truncates responses over 2000 chars."""
    plugin = OpenClaudePlugin(api_key="test-key")
    ctx = MagicMock()
    ctx.defer = AsyncMock()
    ctx.respond = AsyncMock()

    long_text = "x" * 3000
    with patch.object(plugin, "_init_client"):
        with patch.object(plugin, "_client") as mock_client:
            mock_response = MagicMock()
            mock_response.content = [MagicMock(text=long_text)]
            mock_client.messages.create.return_value = mock_response

            await plugin.ask(ctx, prompt="Test")

            called_text = ctx.respond.call_args[0][0]
            assert len(called_text) <= 2000
            assert called_text.endswith("...")


@pytest.mark.asyncio
async def test_ask_command_handles_missing_sdk():
    """Ask command gracefully handles missing Anthropic SDK."""
    plugin = OpenClaudePlugin(api_key="test-key")
    ctx = MagicMock()
    ctx.defer = AsyncMock()
    ctx.t = MagicMock(return_value="SDK not installed")
    ctx.respond = AsyncMock()

    with patch.object(plugin, "_init_client", side_effect=ImportError("anthropic")):
        await plugin.ask(ctx, prompt="Test")

        ctx.respond.assert_called_once()
        call_args = ctx.respond.call_args
        assert "not installed" in call_args[0][0].lower()


@pytest.mark.asyncio
async def test_ask_command_handles_api_errors():
    """Ask command handles API errors gracefully."""
    plugin = OpenClaudePlugin(api_key="test-key")
    ctx = MagicMock()
    ctx.defer = AsyncMock()
    ctx.t = MagicMock(return_value="API error")
    ctx.respond = AsyncMock()

    with patch.object(plugin, "_init_client"):
        with patch.object(plugin, "_client") as mock_client:
            mock_client.messages.create.side_effect = Exception("Rate limit exceeded")

            await plugin.ask(ctx, prompt="Test")

            ctx.respond.assert_called_once()
            call_args = ctx.respond.call_args
            assert "error" in call_args[0][0].lower() or "Rate limit" in call_args[0][0]
