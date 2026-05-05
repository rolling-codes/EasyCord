"""AI orchestration layer — routing, tool loops, context management."""
from __future__ import annotations

import logging
import inspect
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

from easycord.tools import ToolCall, ToolRegistry

logger = logging.getLogger("easycord.orchestrator")

if TYPE_CHECKING:
    from easycord.context import Context
    from easycord.plugins._ai_providers import AIProvider
    from easycord.conversation_memory import ConversationMemory


@dataclass
class RunContext:
    """Context for orchestrator.run()."""

    messages: list[dict]
    ctx: Context | None  # Discord context for permission checks
    max_steps: int = 5
    timeout_ms: int = 30000
    system_prompt: str | None = None  # AI system context
    conversation_memory: ConversationMemory | None = None  # For multi-turn


@dataclass
class FinalResponse:
    """Result from orchestrator."""

    text: str
    provider: Optional[AIProvider] = None
    steps: int = 0


class ProviderStrategy(ABC):
    """Abstract provider selection strategy."""

    @abstractmethod
    def select(
        self, run_ctx: RunContext, attempt: int
    ) -> AIProvider:
        """Select provider for this attempt. Raise on no more options."""


class FallbackStrategy(ProviderStrategy):
    """Try providers in chain; move to next on failure."""

    def __init__(self, providers: list[AIProvider]):
        self.providers = providers

    def select(self, run_ctx: RunContext, attempt: int) -> AIProvider:
        if attempt >= len(self.providers):
            raise IndexError("No more providers to try")
        return self.providers[attempt]


class Orchestrator:
    """Coordinate provider selection, tool execution, and looping."""

    def __init__(
        self,
        strategy: ProviderStrategy,
        tools: ToolRegistry,
    ):
        self.strategy = strategy
        self.tools = tools

    async def run(self, run_ctx: RunContext) -> FinalResponse:
        """Execute orchestration loop."""
        max_steps = run_ctx.max_steps
        attempt = 0
        steps = 0
        messages = list(run_ctx.messages)

        # Prepend system prompt if provided
        if run_ctx.system_prompt:
            messages.insert(
                0,
                {
                    "role": "system",
                    "content": run_ctx.system_prompt,
                },
            )

        while steps < max_steps:
            try:
                provider = self.strategy.select(run_ctx, attempt)
            except IndexError:
                return FinalResponse(
                    text="All providers exhausted",
                    provider=None,
                    steps=steps,
                )

            try:
                # Build tool schema for provider
                tools_schema = self.tools.to_provider_schema(run_ctx.ctx) if run_ctx.ctx else []

                # Query provider
                prompt = self._format_messages(messages)
                output = await self._query_provider(
                    provider,
                    prompt,
                    tools_schema if tools_schema else None,
                )

                if isinstance(output, str):
                    if run_ctx.conversation_memory and run_ctx.ctx:
                        run_ctx.conversation_memory.add_assistant_message(
                            run_ctx.ctx.user.id,
                            output,
                            run_ctx.ctx.guild.id if run_ctx.ctx.guild else None,
                        )
                    return FinalResponse(
                        text=output,
                        provider=provider,
                        steps=steps,
                    )

                # Check for tool call
                tool_call = getattr(output, "tool_call", None)
                if tool_call:
                    if run_ctx.ctx is None:
                        messages.append(
                            {
                                "role": "assistant",
                                "content": f"Tool '{tool_call.name}' not available: no Discord context",
                            }
                        )
                        steps += 1
                        continue

                    allowed, reason = await self.tools.can_execute(run_ctx.ctx, tool_call.name)
                    if not allowed:
                        messages.append(
                            {
                                "role": "assistant",
                                "content": f"Tool '{tool_call.name}' not available: {reason}",
                            }
                        )
                        steps += 1
                        continue

                    result = await self.tools.execute(run_ctx.ctx, tool_call)

                    messages.append(
                        {
                            "role": "tool",
                            "name": tool_call.name,
                            "content": result.output if result.output is not None else result.error,
                        }
                    )
                    steps += 1
                    continue

                # Check for final text
                text = getattr(output, "text", None)
                if text:
                    # Save to conversation memory if provided
                    if run_ctx.conversation_memory and run_ctx.ctx:
                        run_ctx.conversation_memory.add_assistant_message(
                            run_ctx.ctx.user.id,
                            text,
                            run_ctx.ctx.guild.id if run_ctx.ctx.guild else None,
                        )
                    return FinalResponse(
                        text=text,
                        provider=provider,
                        steps=steps,
                    )

                # Neither tool nor text — try fallback
                attempt += 1
                continue

            except Exception as e:
                logger.warning(
                    "Provider %s failed on attempt %d: %s",
                    type(provider).__name__,
                    attempt,
                    e,
                )
                attempt += 1
                continue

        return FinalResponse(
            text="Max steps reached",
            provider=None,
            steps=steps,
        )

    async def _query_provider(
        self,
        provider: AIProvider,
        prompt: str,
        tools_schema: list[dict] | None,
    ):
        """Call providers with tools only when their query signature supports it."""
        query = provider.query
        signature = inspect.signature(query)
        supports_tools = any(
            p.kind is inspect.Parameter.VAR_KEYWORD or name == "tools"
            for name, p in signature.parameters.items()
        )
        if supports_tools:
            return await query(prompt=prompt, tools=tools_schema)
        return await query(prompt)

    @staticmethod
    def _format_messages(messages: list[dict]) -> str:
        """Convert chat-style messages into the plain prompt used by legacy providers."""
        lines = []
        for message in messages:
            role = message.get("role", "user")
            content = message.get("content", "")
            if role == "tool" and message.get("name"):
                role = f"tool:{message['name']}"
            lines.append(f"{role}: {content}")
        return "\n".join(lines)
