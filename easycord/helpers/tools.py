"""Tool registry helper shortcuts."""
from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any, cast

from easycord.tools import ToolDef, ToolRegistry, ToolSafety

if TYPE_CHECKING:
    pass


class ToolHelpers:
    """Shortcuts for tool registry operations."""

    @staticmethod
    def register_batch(
        registry: ToolRegistry,
        tools: list[dict[str, Any]],
    ) -> int:
        """Register multiple tools at once.

        Each tool dict should have: name, func, description, safety
        Optional: parameters, require_guild, require_admin, allowed_roles, allowed_users, timeout_ms, rate_limit
        """
        count = 0
        for tool_config in tools:
            name = tool_config.get("name")
            func = tool_config.get("func")
            description = tool_config.get("description")
            safety = tool_config.get("safety")

            if not isinstance(name, str) or not callable(func) or not isinstance(description, str):
                continue
            if safety is not None and not isinstance(safety, ToolSafety):
                raise TypeError(
                    f"safety must be a ToolSafety enum member, got {type(safety).__name__!r}"
                )
            if not isinstance(safety, ToolSafety):
                continue

            registry.register(
                name=name,
                func=cast(Callable[..., Any], func),
                description=description,
                safety=safety,
                parameters=tool_config.get("parameters"),
                require_guild=tool_config.get("require_guild", True),
                require_admin=tool_config.get("require_admin", False),
                allowed_roles=tool_config.get("allowed_roles"),
                allowed_users=tool_config.get("allowed_users"),
                timeout_ms=tool_config.get("timeout_ms", 5000),
                rate_limit=tool_config.get("rate_limit"),
            )
            count += 1
        return count

    @staticmethod
    def check_permission(
        registry: ToolRegistry, tool_name: str, user_id: int, guild_id: int | None = None
    ) -> bool:
        """Check if tool is registered and enabled (does not check ctx-level permissions)."""
        tool = registry._tools.get(tool_name)
        if not tool:
            return False
        return tool_name in registry._allowlist and tool_name not in registry._denylist

    @staticmethod
    def list_all_tools(registry: ToolRegistry) -> dict[str, ToolDef]:
        """Get all registered tools (access internal _tools)."""
        return registry._tools.copy()

    @staticmethod
    def get_tool_info(registry: ToolRegistry, tool_name: str) -> dict | None:
        """Get tool metadata as dict."""
        tool = registry._tools.get(tool_name)
        if not tool:
            return None
        return {
            "name": tool.name,
            "description": tool.description,
            "safety": tool.safety.name,
            "require_admin": tool.require_admin,
            "require_guild": tool.require_guild,
        }
