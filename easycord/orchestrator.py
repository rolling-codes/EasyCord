"""AI orchestration layer — routing, tool loops, context management."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

from easycord.tools import ToolCall, ToolRegistry

if TYPE_CHECKING:
    from easycord.context import Context
    from easycord.plugins._ai_providers import AIProvider


@dataclass
class RunContext:
    """Context for orchestrator.run()."""

    messages: list[dict]
    ctx: Context  # Discord context for permission checks
    max_steps: int = 5
    timeout_ms: int = 30000
    system_prompt: str | None = None  # AI system context


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
        return self.providers[min(attempt, len(self.providers) - 1)]


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
                tools_schema = self.tools.to_provider_schema(run_ctx.ctx)

                # Query provider
                output = await provider.query(
                    prompt="",  # using messages directly
                    tools=tools_schema if tools_schema else None,
                )

                # Check for tool call
                if output.tool_call:
                    allowed, reason = self.tools.can_execute(
                        run_ctx.ctx, output.tool_call.name
                    )
                    if not allowed:
                        messages.append(
                            {
                                "role": "assistant",
                                "content": f"Tool '{output.tool_call.name}' not available: {reason}",
                            }
                        )
                        steps += 1
                        continue

                    result = await self.tools.execute(
                        run_ctx.ctx, output.tool_call
                    )

                    messages.append(
                        {
                            "role": "tool",
                            "name": output.tool_call.name,
                            "content": result.output or result.error,
                        }
                    )
                    steps += 1
                    continue

                # Check for final text
                if output.text:
                    return FinalResponse(
                        text=output.text,
                        provider=provider,
                        steps=steps,
                    )

                # Neither tool nor text — try fallback
                attempt += 1
                continue

            except Exception as e:
                # Provider failed — try fallback
                attempt += 1
                continue

        return FinalResponse(
            text="Max steps reached",
            provider=None,
            steps=steps,
        )
