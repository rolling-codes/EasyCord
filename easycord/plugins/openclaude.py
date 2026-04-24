"""OpenClaude integration for AI-powered responses via Claude."""
from __future__ import annotations

import os
from typing import Optional

import discord

from easycord import Plugin, slash


class OpenClaudePlugin(Plugin):
    """AI assistant plugin using Claude API for intelligent responses.

    Members can ask questions via `/ask` and receive Claude-generated responses.
    Requires ANTHROPIC_API_KEY environment variable or explicit API key.

    Quick start::

        from easycord.plugins.openclaude import OpenClaudePlugin
        bot.add_plugin(OpenClaudePlugin())

    Slash commands registered
    -------------------------
    ``/ask`` — Ask Claude a question and get an AI-powered response.
    """

    def __init__(self, api_key: Optional[str] = None, model: str = "claude-3-5-sonnet-20241022") -> None:
        """Initialize OpenClaude plugin.

        Parameters
        ----------
        api_key : str, optional
            Anthropic API key. If not provided, uses ANTHROPIC_API_KEY env var.
        model : str
            Claude model to use (default: claude-3-5-sonnet-20241022).
        """
        self._api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self._model = model
        self._client = None

        if not self._api_key:
            raise ValueError("ANTHROPIC_API_KEY env var or api_key param required")

    def _init_client(self):
        """Lazy-initialize Anthropic client."""
        if self._client is None:
            try:
                from anthropic import Anthropic
            except ImportError:
                raise ImportError("anthropic package required. Install with: pip install anthropic")
            self._client = Anthropic(api_key=self._api_key)

    @slash(description="Ask Claude a question and get an AI response.", guild_only=True)
    async def ask(self, ctx, prompt: str) -> None:
        """Ask Claude a question.

        Parameters
        ----------
        ctx : Context
            Command context.
        prompt : str
            Question or prompt for Claude.
        """
        await ctx.defer()

        try:
            self._init_client()

            # Call Claude API
            message = self._client.messages.create(
                model=self._model,
                max_tokens=1024,
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
            )

            # Extract response text
            response_text = message.content[0].text

            # Send response (truncate if too long)
            if len(response_text) > 2000:
                response_text = response_text[:1997] + "..."

            await ctx.respond(response_text)

        except ImportError:
            await ctx.respond(
                ctx.t(
                    "openclaude.anthropic_not_installed",
                    default="Anthropic SDK not installed. Run: `pip install anthropic`",
                ),
                ephemeral=True,
            )
        except Exception as exc:
            await ctx.respond(
                ctx.t(
                    "openclaude.error",
                    default="Error calling Claude: {error}",
                    error=str(exc),
                ),
                ephemeral=True,
            )
