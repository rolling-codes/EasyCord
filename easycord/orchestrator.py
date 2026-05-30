"""AI orchestration layer — routing, tool loops, context management."""
from __future__ import annotations

import asyncio
import logging
import inspect
from abc import ABC, abstractmethod
from copy import deepcopy
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional, TypedDict, Any

from easycord.tools import ToolRegistry

logger = logging.getLogger("easycord.orchestrator")


class Message(TypedDict, total=False):
    """Message in orchestration context.

    Required fields: role, content
    Optional fields: name (for tool messages), timestamp, tool_call_id, error
    """
    role: str  # "user", "assistant", "system", or "tool"
    content: str
    name: str  # Tool message name
    timestamp: Any  # datetime if present
    tool_call_id: str  # Tool call ID for tracking
    error: str  # Error message if tool failed


if TYPE_CHECKING:
    from easycord.context import Context
    from easycord.plugins._ai_providers import AIProvider
    from easycord.conversation_memory import ConversationMemory
    from easycord.tools import ToolCall, ToolResult


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
        """Execute orchestration loop with timeout enforcement."""
        timeout_seconds = run_ctx.timeout_ms / 1000.0 if run_ctx.timeout_ms else None
        try:
            return await asyncio.wait_for(
                self._run_inner(run_ctx),
                timeout=timeout_seconds
            )
        except asyncio.TimeoutError:
            return FinalResponse(
                text="Orchestration timeout",
                provider=None,
                steps=0,
            )

    async def _run_inner(self, run_ctx: RunContext) -> FinalResponse:
        """Internal orchestration loop (called with timeout wrapper).

        Implements Phase 1 core loop with:
        - Provider query loop with max_steps
        - Tool call extraction and execution
        - Tool result appending with audit fields
        - Provider fallback on exception or invalid output
        - Memory update only on final response
        """
        max_steps = run_ctx.max_steps
        attempt = 0
        steps = 0
        messages = deepcopy(run_ctx.messages)

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
                # Increment steps once per provider query
                steps += 1

                # Build tool schema for provider
                tools_schema = self.tools.to_provider_schema(run_ctx.ctx) if run_ctx.ctx else []

                # Query provider
                prompt = self._format_messages(messages)
                output = await self._query_provider(
                    provider,
                    prompt,
                    tools_schema if tools_schema else None,
                )

                # Check for immediate string response
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

                # Extract tool call
                tool_call = self._extract_tool_call(output)
                if tool_call:
                    # Check Discord context
                    if run_ctx.ctx is None:
                        messages.append(
                            {
                                "role": "assistant",
                                "content": f"Tool '{tool_call.name}' not available: no Discord context",
                            }
                        )
                        attempt = 0  # Reset fallback counter, retry same provider
                        continue

                    # Check permissions (does NOT increment steps)
                    allowed, reason = await self.tools.can_execute(run_ctx.ctx, tool_call.name)
                    if not allowed:
                        messages.append(
                            {
                                "role": "assistant",
                                "content": f"Tool '{tool_call.name}' not available: {reason}",
                            }
                        )
                        attempt = 0  # Reset fallback counter, retry same provider
                        continue

                    # Execute tool
                    result = await self.tools.execute(run_ctx.ctx, tool_call)

                    # Append tool result to messages
                    messages.append(self._build_tool_message(result, tool_call))

                    # Check for final text after tool execution
                    final_text = getattr(output, "text", None)
                    if final_text:
                        if run_ctx.conversation_memory and run_ctx.ctx:
                            run_ctx.conversation_memory.add_assistant_message(
                                run_ctx.ctx.user.id,
                                final_text,
                                run_ctx.ctx.guild.id if run_ctx.ctx.guild else None,
                            )
                        return FinalResponse(
                            text=final_text,
                            provider=provider,
                            steps=steps,
                        )

                    # Reset provider fallback counter after successful tool execution
                    attempt = 0
                    continue

                # Check for final text without tool call
                text = getattr(output, "text", None)
                if text:
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

                # Neither tool nor text — fallback to next provider
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
        """Call providers with tools only when they support it."""
        supports_tools = getattr(provider, "supports_tools", False)
        if supports_tools:
            return await provider.query(prompt=prompt, tools=tools_schema)
        return await provider.query(prompt)

    def _extract_tool_call(self, provider_output: Any) -> Optional["ToolCall"]:
        """Extract tool call from provider output, validating structure.

        Args:
            provider_output: Provider response object

        Returns:
            ToolCall if output.tool_call exists, else None

        Raises:
            ValueError if tool_call exists but lacks required 'name' attribute
        """
        from easycord.tools import ToolCall

        tool_call = getattr(provider_output, "tool_call", None)
        if tool_call is None:
            return None

        # Validate structure
        if not hasattr(tool_call, "name"):
            raise ValueError("tool_call missing 'name' attribute")

        # Coerce to ToolCall if needed
        if isinstance(tool_call, ToolCall):
            return tool_call
        elif isinstance(tool_call, dict):
            return ToolCall(name=tool_call["name"], args=tool_call.get("args", {}))
        else:
            return ToolCall(
                name=tool_call.name, args=getattr(tool_call, "args", {})
            )

    def _build_tool_message(
        self, result: "ToolResult", tool_call: "ToolCall"
    ) -> dict[str, Any]:
        """Build message dict for tool result.

        Args:
            result: ToolResult from tool execution
            tool_call: Original ToolCall that was executed

        Returns:
            Message dict with tool result and audit fields
        """
        message = {
            "role": "tool",
            "name": tool_call.name,
            "content": result.output if result.success else result.error,
            "tool_call_id": result.tool_id,
        }

        # Add error flag if execution failed
        if not result.success:
            message["error"] = result.error

        return message

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
