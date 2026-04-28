"""Tests for easycord.plugins — AI providers and AIPlugin."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from easycord.plugins._ai_providers import (
    AIProvider,
    AnthropicProvider,
    GeminiProvider,
    GroqProvider,
    HuggingFaceProvider,
    LiteLLMProvider,
    MistralProvider,
    OllamaProvider,
    OpenAIProvider,
    TogetherAIProvider,
)
from easycord.plugins.openclaude import AIPlugin, OpenClaudePlugin


# ============================================================================
# Section 1 — AIProvider base (abstract enforcement)
# ============================================================================


def test_aiprovider_abstract():
    """AIProvider cannot be instantiated directly."""
    with pytest.raises(TypeError):
        AIProvider(api_key="test", model="test")


# ============================================================================
# Section 2 — AnthropicProvider unit tests
# ============================================================================


def test_anthropic_requires_api_key():
    """AnthropicProvider requires ANTHROPIC_API_KEY."""
    with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
        AnthropicProvider(api_key=None)


def test_anthropic_accepts_explicit_key():
    """AnthropicProvider accepts explicit api_key."""
    provider = AnthropicProvider(api_key="test-key")
    assert provider._api_key == "test-key"


def test_anthropic_reads_env_var(monkeypatch):
    """AnthropicProvider reads ANTHROPIC_API_KEY from environment."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "env-key")
    provider = AnthropicProvider()
    assert provider._api_key == "env-key"


def test_anthropic_custom_model():
    """AnthropicProvider accepts custom model."""
    provider = AnthropicProvider(api_key="test", model="claude-3-opus")
    assert provider._model == "claude-3-opus"


def test_anthropic_missing_sdk():
    """AnthropicProvider raises ImportError if anthropic SDK missing."""
    provider = AnthropicProvider(api_key="test")
    with patch.dict("sys.modules", {"anthropic": None}):
        with pytest.raises(ImportError, match="anthropic"):
            provider._init_client()


@pytest.mark.asyncio
async def test_anthropic_query_returns_text():
    """AnthropicProvider.query returns response text."""
    provider = AnthropicProvider(api_key="test")
    with patch.object(provider, "_init_client"):
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Claude response")]
        provider._client = MagicMock()
        provider._client.messages.create.return_value = mock_response
        assert await provider.query("hello") == "Claude response"


# ============================================================================
# Section 3 — OpenAIProvider unit tests
# ============================================================================


def test_openai_requires_api_key():
    """OpenAIProvider requires OPENAI_API_KEY."""
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        OpenAIProvider(api_key=None)


def test_openai_accepts_explicit_key():
    """OpenAIProvider accepts explicit api_key."""
    provider = OpenAIProvider(api_key="test-key")
    assert provider._api_key == "test-key"


def test_openai_reads_env_var(monkeypatch):
    """OpenAIProvider reads OPENAI_API_KEY from environment."""
    monkeypatch.setenv("OPENAI_API_KEY", "env-key")
    provider = OpenAIProvider()
    assert provider._api_key == "env-key"


def test_openai_custom_model():
    """OpenAIProvider accepts custom model."""
    provider = OpenAIProvider(api_key="test", model="gpt-3.5-turbo")
    assert provider._model == "gpt-3.5-turbo"


def test_openai_missing_sdk():
    """OpenAIProvider raises ImportError if openai SDK missing."""
    provider = OpenAIProvider(api_key="test")
    with patch.dict("sys.modules", {"openai": None}):
        with pytest.raises(ImportError, match="openai"):
            provider._init_client()


@pytest.mark.asyncio
async def test_openai_query_returns_text():
    """OpenAIProvider.query returns response text."""
    provider = OpenAIProvider(api_key="test")
    with patch.object(provider, "_init_client"):
        mock_choice = MagicMock()
        mock_choice.message.content = "GPT response"
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        provider._client = MagicMock()
        provider._client.chat.completions.create.return_value = mock_response
        assert await provider.query("hello") == "GPT response"


# ============================================================================
# Section 4 — GeminiProvider unit tests
# ============================================================================


def test_gemini_requires_api_key():
    """GeminiProvider requires GOOGLE_API_KEY."""
    with pytest.raises(ValueError, match="GOOGLE_API_KEY"):
        GeminiProvider(api_key=None)


def test_gemini_accepts_explicit_key():
    """GeminiProvider accepts explicit api_key."""
    provider = GeminiProvider(api_key="test-key")
    assert provider._api_key == "test-key"


def test_gemini_reads_env_var(monkeypatch):
    """GeminiProvider reads GOOGLE_API_KEY from environment."""
    monkeypatch.setenv("GOOGLE_API_KEY", "env-key")
    provider = GeminiProvider()
    assert provider._api_key == "env-key"


def test_gemini_custom_model():
    """GeminiProvider accepts custom model."""
    provider = GeminiProvider(api_key="test", model="gemini-pro")
    assert provider._model == "gemini-pro"


def test_gemini_missing_sdk():
    """GeminiProvider raises ImportError if google-generativeai SDK missing."""
    provider = GeminiProvider(api_key="test")
    with patch.dict("sys.modules", {"google.generativeai": None}):
        with pytest.raises(ImportError, match="google-generativeai"):
            provider._init_client()


@pytest.mark.asyncio
async def test_gemini_query_returns_text():
    """GeminiProvider.query returns response text."""
    provider = GeminiProvider(api_key="test")
    with patch.object(provider, "_init_client"):
        mock_response = MagicMock()
        mock_response.text = "Gemini response"
        provider._client = MagicMock()
        provider._client.generate_content.return_value = mock_response
        assert await provider.query("hello") == "Gemini response"


# ============================================================================
# Section 5 — OllamaProvider unit tests
# ============================================================================


def test_ollama_no_api_key_required():
    """OllamaProvider doesn't require API key (local)."""
    provider = OllamaProvider()
    assert provider._api_key is None


def test_ollama_accepts_explicit_model():
    """OllamaProvider accepts custom model name."""
    provider = OllamaProvider(model="llama3")
    assert provider._model == "llama3"


def test_ollama_missing_sdk():
    """OllamaProvider raises ImportError if ollama SDK missing."""
    provider = OllamaProvider()
    with patch.dict("sys.modules", {"ollama": None}):
        with pytest.raises(ImportError, match="ollama"):
            provider._init_client()


@pytest.mark.asyncio
async def test_ollama_query_returns_text():
    """OllamaProvider.query returns response text."""
    provider = OllamaProvider()
    with patch.object(provider, "_init_client"):
        mock_ollama = MagicMock()
        mock_ollama.chat.return_value = {"message": {"content": "Ollama response"}}
        provider._client = mock_ollama
        assert await provider.query("hello") == "Ollama response"


# ============================================================================
# Section 6 — MistralProvider unit tests
# ============================================================================


def test_mistral_requires_api_key():
    """MistralProvider requires MISTRAL_API_KEY."""
    with pytest.raises(ValueError, match="MISTRAL_API_KEY"):
        MistralProvider(api_key=None)


def test_mistral_accepts_explicit_key():
    """MistralProvider accepts explicit api_key."""
    provider = MistralProvider(api_key="test-key")
    assert provider._api_key == "test-key"


@pytest.mark.asyncio
async def test_mistral_query_returns_text():
    """MistralProvider.query returns response text."""
    provider = MistralProvider(api_key="test")
    with patch.object(provider, "_init_client"):
        mock_message = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = "Mistral response"
        mock_message.choices = [mock_choice]
        provider._client = MagicMock()
        provider._client.chat.return_value = mock_message
        assert await provider.query("hello") == "Mistral response"


# ============================================================================
# Section 7 — GroqProvider unit tests
# ============================================================================


def test_groq_requires_api_key():
    """GroqProvider requires GROQ_API_KEY."""
    with pytest.raises(ValueError, match="GROQ_API_KEY"):
        GroqProvider(api_key=None)


def test_groq_accepts_explicit_key():
    """GroqProvider accepts explicit api_key."""
    provider = GroqProvider(api_key="test-key")
    assert provider._api_key == "test-key"


@pytest.mark.asyncio
async def test_groq_query_returns_text():
    """GroqProvider.query returns response text."""
    provider = GroqProvider(api_key="test")
    with patch.object(provider, "_init_client"):
        mock_choice = MagicMock()
        mock_choice.message.content = "Groq response"
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        provider._client = MagicMock()
        provider._client.chat.completions.create.return_value = mock_response
        assert await provider.query("hello") == "Groq response"


# ============================================================================
# Section 8 — HuggingFaceProvider unit tests
# ============================================================================


def test_huggingface_requires_api_key():
    """HuggingFaceProvider requires HF_API_KEY."""
    with pytest.raises(ValueError, match="HF_API_KEY"):
        HuggingFaceProvider(api_key=None)


def test_huggingface_accepts_explicit_key():
    """HuggingFaceProvider accepts explicit api_key."""
    provider = HuggingFaceProvider(api_key="test-key")
    assert provider._api_key == "test-key"


@pytest.mark.asyncio
async def test_huggingface_query_returns_text():
    """HuggingFaceProvider.query returns response text."""
    provider = HuggingFaceProvider(api_key="test")
    with patch.object(provider, "_init_client"):
        provider._client = MagicMock()
        provider._client.text_generation.return_value = "HF response"
        assert await provider.query("hello") == "HF response"


# ============================================================================
# Section 9 — TogetherAIProvider unit tests
# ============================================================================


def test_together_requires_api_key():
    """TogetherAIProvider requires TOGETHER_API_KEY."""
    with pytest.raises(ValueError, match="TOGETHER_API_KEY"):
        TogetherAIProvider(api_key=None)


def test_together_accepts_explicit_key():
    """TogetherAIProvider accepts explicit api_key."""
    provider = TogetherAIProvider(api_key="test-key")
    assert provider._api_key == "test-key"


@pytest.mark.asyncio
async def test_together_query_returns_text():
    """TogetherAIProvider.query returns response text."""
    provider = TogetherAIProvider(api_key="test")
    with patch.object(provider, "_init_client"):
        provider._client = MagicMock()
        provider._client.Complete.create.return_value = {
            "output": {"choices": [{"text": "Together response"}]}
        }
        assert await provider.query("hello") == "Together response"


# ============================================================================
# Section 10 — LiteLLMProvider unit tests
# ============================================================================


def test_litellm_requires_api_key():
    """LiteLLMProvider requires LITELLM_API_KEY."""
    with pytest.raises(ValueError, match="LITELLM_API_KEY"):
        LiteLLMProvider(api_key=None)


def test_litellm_accepts_explicit_key():
    """LiteLLMProvider accepts explicit api_key."""
    provider = LiteLLMProvider(api_key="test-key")
    assert provider._api_key == "test-key"


@pytest.mark.asyncio
async def test_litellm_query_returns_text():
    """LiteLLMProvider.query returns response text."""
    provider = LiteLLMProvider(api_key="test")
    with patch.object(provider, "_init_client"):
        provider._client = MagicMock()
        provider._client.return_value = {
            "choices": [{"message": {"content": "LiteLLM response"}}]
        }
        assert await provider.query("hello") == "LiteLLM response"


# ============================================================================
# Section 11 — AIPlugin unit tests
# ============================================================================


@pytest.mark.asyncio
async def test_aiplugin_ask_calls_provider_and_responds():
    """AIPlugin.ask calls provider and responds with result."""
    provider = MagicMock(spec=AIProvider)
    provider.query = AsyncMock(return_value="AI response")
    plugin = AIPlugin(provider=provider)
    ctx = MagicMock()
    ctx.defer = AsyncMock()
    ctx.respond = AsyncMock()
    ctx.user.id = 123
    ctx.guild_id = 456

    await plugin.ask(ctx, prompt="test")

    ctx.defer.assert_called_once()
    ctx.respond.assert_called_once_with("AI response")


@pytest.mark.asyncio
async def test_aiplugin_truncates_long_response():
    """AIPlugin.ask truncates responses over 2000 chars."""
    provider = MagicMock(spec=AIProvider)
    provider.query = AsyncMock(return_value="x" * 3000)
    plugin = AIPlugin(provider=provider)
    ctx = MagicMock()
    ctx.defer = AsyncMock()
    ctx.respond = AsyncMock()
    ctx.user.id = 123
    ctx.guild_id = 456

    await plugin.ask(ctx, prompt="test")

    text = ctx.respond.call_args[0][0]
    assert len(text) <= 2000
    assert text.endswith("...")


@pytest.mark.asyncio
async def test_aiplugin_handles_import_error():
    """AIPlugin.ask handles ImportError from provider."""
    provider = MagicMock(spec=AIProvider)
    provider.query = AsyncMock(side_effect=ImportError("sdk missing"))
    plugin = AIPlugin(provider=provider)
    ctx = MagicMock()
    ctx.defer = AsyncMock()
    ctx.t = MagicMock(return_value="sdk missing")
    ctx.respond = AsyncMock()
    ctx.user.id = 123
    ctx.guild_id = 456

    await plugin.ask(ctx, prompt="test")

    ctx.respond.assert_called_once()
    assert ctx.respond.call_args[1].get("ephemeral") is True


@pytest.mark.asyncio
async def test_aiplugin_handles_api_error():
    """AIPlugin.ask handles generic API errors."""
    provider = MagicMock(spec=AIProvider)
    provider.query = AsyncMock(side_effect=Exception("rate limit exceeded"))
    plugin = AIPlugin(provider=provider)
    ctx = MagicMock()
    ctx.defer = AsyncMock()
    ctx.t = MagicMock(return_value="Error calling AI: rate limit exceeded")
    ctx.respond = AsyncMock()
    ctx.user.id = 123
    ctx.guild_id = 456

    await plugin.ask(ctx, prompt="test")

    ctx.respond.assert_called_once()
    assert ctx.respond.call_args[1].get("ephemeral") is True


# ============================================================================
# Section 12 — OpenClaudePlugin backwards-compat tests
# ============================================================================


def test_openclaude_init_requires_api_key():
    """OpenClaudePlugin requires ANTHROPIC_API_KEY."""
    with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
        OpenClaudePlugin(api_key=None)


def test_openclaude_init_with_api_key():
    """OpenClaudePlugin initializes with explicit API key."""
    plugin = OpenClaudePlugin(api_key="test-key")
    assert plugin._provider._api_key == "test-key"


def test_openclaude_init_with_env_var(monkeypatch):
    """OpenClaudePlugin reads ANTHROPIC_API_KEY from environment."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "env-key")
    plugin = OpenClaudePlugin()
    assert plugin._provider._api_key == "env-key"


def test_openclaude_model_customizable():
    """OpenClaudePlugin accepts custom model."""
    plugin = OpenClaudePlugin(api_key="test", model="claude-3-opus")
    assert plugin._provider._model == "claude-3-opus"


@pytest.mark.asyncio
async def test_openclaude_ask_defers_and_responds():
    """OpenClaudePlugin.ask shows a localized thinking message and edits it."""
    plugin = OpenClaudePlugin(api_key="test-key")
    ctx = MagicMock()
    ctx.defer = AsyncMock()
    ctx.t = MagicMock(return_value="Thinking locally...")
    ctx.respond = AsyncMock()
    ctx.edit_response = AsyncMock()
    ctx.user.id = 123
    ctx.guild_id = 456

    with patch.object(plugin._provider, "query", new_callable=AsyncMock, return_value="Test response"):
        await plugin.ask(ctx, prompt="Test prompt")

    ctx.defer.assert_not_called()
    ctx.t.assert_called_once_with("openclaude.thinking", default="Thinking...")
    ctx.respond.assert_called_once_with("Thinking locally...")
    ctx.edit_response.assert_called_once_with("Test response")


@pytest.mark.asyncio
async def test_aiplugin_rate_limits_per_user():
    """AIPlugin.ask rate limits repeated requests per guild/user."""
    provider = MagicMock(spec=AIProvider)
    provider.query = AsyncMock(return_value="AI response")
    plugin = AIPlugin(provider=provider, rate_limit=1, rate_window=60)
    ctx = MagicMock()
    ctx.defer = AsyncMock()
    ctx.respond = AsyncMock()
    ctx.t = MagicMock(return_value="Slow down")
    ctx.user.id = 123
    ctx.guild_id = 456

    await plugin.ask(ctx, prompt="first")
    await plugin.ask(ctx, prompt="second")

    assert provider.query.await_count == 1
    ctx.t.assert_called_with(
        "ai.rate_limited",
        default="You're asking too quickly. Try again in {seconds:.0f}s.",
        seconds=pytest.approx(60, abs=1),
    )
    assert ctx.respond.call_args_list[-1].kwargs["ephemeral"] is True


@pytest.mark.asyncio
async def test_aiplugin_rate_limit_is_per_user():
    """AIPlugin.ask tracks separate users independently."""
    provider = MagicMock(spec=AIProvider)
    provider.query = AsyncMock(return_value="AI response")
    plugin = AIPlugin(provider=provider, rate_limit=1, rate_window=60)
    ctx = MagicMock()
    ctx.defer = AsyncMock()
    ctx.respond = AsyncMock()
    ctx.user.id = 123
    ctx.guild_id = 456

    other_ctx = MagicMock()
    other_ctx.defer = AsyncMock()
    other_ctx.respond = AsyncMock()
    other_ctx.user.id = 999
    other_ctx.guild_id = 456

    await plugin.ask(ctx, prompt="first")
    await plugin.ask(other_ctx, prompt="second")

    assert provider.query.await_count == 2
