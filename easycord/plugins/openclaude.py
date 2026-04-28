"""AI assistant plugins using various LLM provider APIs."""
from __future__ import annotations

import time
from typing import TYPE_CHECKING, Optional

from easycord import Plugin, slash

if TYPE_CHECKING:
    from ._ai_providers import AIProvider


class AIPlugin(Plugin):
    """General-purpose AI assistant for any LLM provider.

    Members can ask questions via `/ask` and receive AI-generated responses.
    Supports Anthropic Claude, OpenAI GPT, Google Gemini, Ollama, and others.

    Quick start::

        from easycord.plugins.openclaude import AIPlugin
        from easycord.plugins._ai_providers import AnthropicProvider

        provider = AnthropicProvider(api_key="sk-ant-...")
        bot.add_plugin(AIPlugin(provider=provider))

    Slash commands registered
    -------------------------
    ``/ask`` — Ask the AI a question and get a response.
    """

    def __init__(
        self,
        provider: AIProvider,
        *,
        rate_limit: int = 3,
        rate_window: float = 60.0,
        thinking_key: str | None = None,
        max_prompt_chars: int = 4000,
    ) -> None:
        """Initialize AI plugin.

        Parameters
        ----------
        provider : AIProvider
            An AI provider instance (AnthropicProvider, OpenAIProvider, etc.).
        """
        super().__init__()
        self._provider = provider
        self._rate_limit = rate_limit
        self._rate_window = rate_window
        self._thinking_key = thinking_key
        self._max_prompt_chars = max_prompt_chars
        self._requests: dict[tuple[int | None, int], list[float]] = {}

    @staticmethod
    def _format_response(text: str) -> str:
        """Truncate response to Discord's 2000 char limit."""
        if len(text) > 2000:
            return text[:1997] + "..."
        return text

    def _rate_limit_retry_after(self, ctx) -> float | None:
        if self._rate_limit <= 0:
            return None

        guild_id = getattr(ctx, "guild_id", None)
        user_id = getattr(getattr(ctx, "user", None), "id", None)
        if user_id is None:
            return None

        now = time.monotonic()
        key = (guild_id, int(user_id))
        window_start = now - self._rate_window
        entries = [stamp for stamp in self._requests.get(key, []) if stamp > window_start]
        if len(entries) >= self._rate_limit:
            self._requests[key] = entries
            return max(0.0, self._rate_window - (now - entries[0]))
        entries.append(now)
        self._requests[key] = entries
        return None

    def _prune_old_request_buckets(self, now: float) -> None:
        # Keep the in-memory limiter bounded over long uptimes.
        stale_before = now - self._rate_window
        stale_keys = [
            key
            for key, values in self._requests.items()
            if not any(stamp > stale_before for stamp in values)
        ]
        for key in stale_keys:
            del self._requests[key]

    @slash(description="Ask an AI a question and get a response.", guild_only=True)
    async def ask(self, ctx, prompt: str) -> None:
        """Ask AI a question.

        Parameters
        ----------
        ctx : Context
            Command context.
        prompt : str
            Question or prompt for the AI.
        """
        if self._max_prompt_chars > 0 and len(prompt) > self._max_prompt_chars:
            await ctx.respond(
                ctx.t(
                    "ai.prompt_too_long",
                    default="Prompt is too long. Maximum length is {limit} characters.",
                    limit=self._max_prompt_chars,
                ),
                ephemeral=True,
            )
            return

        self._prune_old_request_buckets(time.monotonic())
        retry_after = self._rate_limit_retry_after(ctx)
        if retry_after is not None:
            await ctx.respond(
                ctx.t(
                    "ai.rate_limited",
                    default="You're asking too quickly. Try again in {seconds:.0f}s.",
                    seconds=retry_after,
                ),
                ephemeral=True,
            )
            return

        if self._thinking_key:
            await ctx.respond(
                ctx.t(self._thinking_key, default="Thinking..."),
            )
        else:
            await ctx.defer()

        try:
            response_text = await self._provider.query(prompt)
            response = self._format_response(response_text)
            if self._thinking_key:
                await ctx.edit_response(response)
            else:
                await ctx.respond(response)

        except ImportError as exc:
            await ctx.respond(
                ctx.t(
                    "ai.sdk_not_installed",
                    default=str(exc),
                ),
                ephemeral=True,
            )
        except Exception as exc:
            await ctx.respond(
                ctx.t(
                    "ai.error",
                    default="Error calling AI: {error}",
                    error=str(exc),
                ),
                ephemeral=True,
            )


class OpenClaudePlugin(AIPlugin):
    """Backwards-compatible wrapper for Anthropic Claude.

    Maintains the original OpenClaudePlugin interface while delegating to AIPlugin.

    Members can ask questions via `/ask` and receive Claude-generated responses.
    Requires ANTHROPIC_API_KEY environment variable or explicit API key.

    Quick start::

        from easycord.plugins.openclaude import OpenClaudePlugin
        bot.add_plugin(OpenClaudePlugin())

    Slash commands registered
    -------------------------
    ``/ask`` — Ask Claude a question and get an AI-powered response.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "claude-3-5-sonnet-20241022",
        rate_limit: int = 3,
        rate_window: float = 60.0,
        max_prompt_chars: int = 4000,
    ) -> None:
        """Initialize OpenClaude plugin.

        Parameters
        ----------
        api_key : str, optional
            Anthropic API key. If not provided, uses ANTHROPIC_API_KEY env var.
        model : str
            Claude model to use (default: claude-3-5-sonnet-20241022).
        """
        from ._ai_providers import AnthropicProvider

        provider = AnthropicProvider(api_key=api_key, model=model)
        super().__init__(
            provider=provider,
            rate_limit=rate_limit,
            rate_window=rate_window,
            thinking_key="openclaude.thinking",
            max_prompt_chars=max_prompt_chars,
        )
