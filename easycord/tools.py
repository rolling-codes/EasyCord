"""Tool definitions, registry, and execution for AI orchestrator."""
from __future__ import annotations

import asyncio
import inspect
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, Callable, Optional

if TYPE_CHECKING:
    from easycord.context import Context
    from easycord.tool_limits import RateLimit


class ToolSafety(Enum):
    """Tool safety classification."""

    SAFE = "read_only"
    CONTROLLED = "validated"
    RESTRICTED = "never_expose"


@dataclass
class ToolDef:
    """Tool definition with metadata and safety."""

    name: str
    description: str
    func: Callable
    safety: ToolSafety
    parameters: dict = field(default_factory=dict)
    require_guild: bool = True
    require_admin: bool = False
    allowed_roles: list[int] = field(default_factory=list)
    allowed_users: list[int] = field(default_factory=list)
    timeout_ms: int = 5000
    rate_limit: RateLimit | None = None


@dataclass
class ToolCall:
    """AI's request to invoke a tool."""

    name: str
    args: dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolResult:
    """Result of tool execution."""

    success: bool
    output: str
    error: Optional[str] = None


class ToolRegistry:
    """Registry of tools accessible to AI, with permission checks."""

    def __init__(self):
        from easycord.tool_limits import ToolLimiter

        self._tools: dict[str, ToolDef] = {}
        self._allowlist: set[str] = set()
        self._denylist: set[str] = set()
        self._limiter = ToolLimiter()

    def register(
        self,
        name: str,
        func: Callable,
        description: str,
        safety: ToolSafety,
        parameters: dict | None = None,
        require_guild: bool = True,
        require_admin: bool = False,
        allowed_roles: list[int] | None = None,
        allowed_users: list[int] | None = None,
        timeout_ms: int = 5000,
        rate_limit: RateLimit | None = None,
    ) -> None:
        """Register a tool (explicit opt-in)."""
        if name in self._tools:
            raise ValueError(f"Tool '{name}' already registered")

        self._tools[name] = ToolDef(
            name=name,
            func=func,
            description=description,
            safety=safety,
            parameters=parameters or {},
            require_guild=require_guild,
            require_admin=require_admin,
            allowed_roles=allowed_roles or [],
            allowed_users=allowed_users or [],
            timeout_ms=timeout_ms,
            rate_limit=rate_limit,
        )
        self._allowlist.add(name)

    def register_slash_command(
        self,
        command_name: str,
        wrapper_func: Callable,
        description: str,
        safety: ToolSafety,
        **opts,
    ) -> None:
        """Wrap an existing slash command as a tool."""
        self.register(
            name=f"cmd_{command_name}",
            func=wrapper_func,
            description=description,
            safety=safety,
            **opts,
        )

    def enable(self, name: str) -> None:
        """Enable a tool."""
        if name in self._tools:
            self._allowlist.add(name)

    def disable(self, name: str) -> None:
        """Disable a tool."""
        if name in self._tools:
            self._allowlist.discard(name)
            self._denylist.add(name)

    def _can_execute_sync(self, ctx: Context, tool_name: str) -> tuple[bool, Optional[str]]:
        """Permission checks that don't require async (no rate limit)."""
        if tool_name not in self._tools:
            return False, "Tool not found"
        if tool_name in self._denylist:
            return False, "Tool is disabled"
        if tool_name not in self._allowlist:
            return False, "Tool not enabled"

        tool = self._tools[tool_name]

        if tool.require_guild and not ctx.guild:
            return False, "Guild-only tool"

        if tool.require_admin and not ctx.is_admin:
            return False, "Admin required"

        if tool.allowed_roles:
            member = ctx.guild.get_member(ctx.user.id) if ctx.guild else None
            if member is None:
                return False, f"Requires role(s): {tool.allowed_roles}"
            user_roles = {r.id for r in member.roles}
            if not user_roles & set(tool.allowed_roles):
                return False, f"Requires role(s): {tool.allowed_roles}"

        if tool.allowed_users and ctx.user.id not in tool.allowed_users:
            return False, "User not allowed"

        return True, None

    async def can_execute(self, ctx: Context, tool_name: str) -> tuple[bool, Optional[str]]:
        """Check if context can invoke tool (including async rate limit check)."""
        allowed, reason = self._can_execute_sync(ctx, tool_name)
        if not allowed:
            return False, reason

        tool = self._tools[tool_name]
        if tool.rate_limit:
            allowed, reason = await self._limiter.check_limit(
                ctx.user.id, tool_name, tool.rate_limit
            )
            if not allowed:
                return False, reason

        return True, None

    async def execute(
        self,
        ctx: Context,
        call: ToolCall,
    ) -> ToolResult:
        """Execute a tool call with safety checks."""
        if call.name not in self._tools:
            return ToolResult(False, "", f"Tool '{call.name}' not found")

        allowed, reason = await self.can_execute(ctx, call.name)
        if not allowed:
            return ToolResult(False, "", reason)

        tool = self._tools[call.name]

        try:
            result = await asyncio.wait_for(
                self._call_func(tool.func, ctx, call.args),
                timeout=tool.timeout_ms / 1000.0,
            )
            return ToolResult(True, str(result))
        except asyncio.TimeoutError:
            return ToolResult(False, "", "Tool execution timeout")
        except Exception as e:
            return ToolResult(False, "", f"Error: {str(e)}")

    async def _call_func(self, func: Callable, ctx: Context, args: dict) -> Any:
        """Call function, handling both sync and async."""
        if inspect.iscoroutinefunction(func):
            return await func(ctx, **args)
        else:
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(None, lambda: func(ctx, **args))

    def list_available(self, ctx: Context) -> list[ToolDef]:
        """List tools executable by this context (excludes rate-limit check)."""
        return [
            t
            for t in self._tools.values()
            if self._can_execute_sync(ctx, t.name)[0]
        ]

    def to_provider_schema(self, ctx: Context) -> list[dict]:
        """Convert to OpenAI-style function schema for providers."""
        tools = self.list_available(ctx)
        return [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters,
                },
            }
            for t in tools
        ]
