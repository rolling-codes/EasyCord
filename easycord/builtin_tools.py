"""Built-in tools available to all AI instances."""
from __future__ import annotations

import json
from typing import TYPE_CHECKING

from easycord.context_builder import ContextBuilder
from easycord.tools import ToolRegistry, ToolSafety

if TYPE_CHECKING:
    from easycord.context import Context


def register_builtin_tools(registry: ToolRegistry) -> None:
    """Register built-in tools on the bot."""
    registry.register(
        name="get_bot_state",
        func=builtin_get_bot_state,
        description="Get current bot and server state (members, roles, channels, permissions)",
        safety=ToolSafety.SAFE,
        parameters={
            "type": "object",
            "properties": {},
        },
    )

    registry.register(
        name="list_members",
        func=builtin_list_members,
        description="List server members with basic info",
        safety=ToolSafety.SAFE,
        parameters={
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Max members to list (default 10)",
                }
            },
        },
    )

    registry.register(
        name="list_roles",
        func=builtin_list_roles,
        description="List server roles",
        safety=ToolSafety.SAFE,
        parameters={
            "type": "object",
            "properties": {},
        },
    )

    registry.register(
        name="list_channels",
        func=builtin_list_channels,
        description="List server channels",
        safety=ToolSafety.SAFE,
        parameters={
            "type": "object",
            "properties": {},
        },
    )


async def builtin_get_bot_state(ctx: Context) -> str:
    """Return current bot and server state."""
    state = ContextBuilder.build_bot_state_summary(ctx)
    return json.dumps(state, indent=2)


async def builtin_list_members(ctx: Context, limit: int = 10) -> str:
    """List members in the server."""
    if not ctx.guild:
        return "No guild context."

    members = ctx.guild.members[:limit]
    data = [
        {
            "name": m.name,
            "id": m.id,
            "top_role": m.top_role.name if m.top_role else None,
            "joined_at": m.joined_at.isoformat() if m.joined_at else None,
        }
        for m in members
    ]

    return json.dumps(
        {"count": len(members), "members": data},
        indent=2,
    )


async def builtin_list_roles(ctx: Context) -> str:
    """List roles in the server."""
    if not ctx.guild:
        return "No guild context."

    roles = [
        {
            "name": r.name,
            "id": r.id,
            "position": r.position,
            "permissions": {
                "value": r.permissions.value,
                "enabled": [name for name, enabled in r.permissions if enabled],
            },
        }
        for r in ctx.guild.roles
    ]

    return json.dumps(
        {"count": len(roles), "roles": roles},
        indent=2,
    )


async def builtin_list_channels(ctx: Context) -> str:
    """List channels in the server."""
    if not ctx.guild:
        return "No guild context."

    channels = [
        {
            "name": c.name,
            "id": c.id,
            "type": c.type.name,
        }
        for c in ctx.guild.channels
    ]

    return json.dumps(
        {"count": len(channels), "channels": channels},
        indent=2,
    )
