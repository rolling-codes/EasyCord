"""Build AI context from bot state and available tools."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from easycord.bot import Bot
    from easycord.context import Context
    from easycord.tools import ToolRegistry


class ContextBuilder:
    """Synthesize bot state and tools into AI context."""

    @staticmethod
    def build_system_prompt(
        bot: Bot,
        ctx: Context,
        registry: ToolRegistry,
    ) -> str:
        """Build system prompt with available tools and bot state."""
        tools_list = ContextBuilder._format_tools(registry, ctx)
        commands_list = ContextBuilder._format_commands(bot)
        state_summary = ContextBuilder._format_state(ctx)

        return f"""You are a Discord bot assistant with access to tools and commands.

## Available Tools
{tools_list}

## Available Commands
{commands_list}

## Current State
{state_summary}

You can call tools by name with arguments. Always check the current state before making decisions.
Prefer querying state over making assumptions about the server.
Respect permission boundaries: don't attempt to call tools you don't have permission for."""

    @staticmethod
    def _format_tools(registry: ToolRegistry, ctx: Context) -> str:
        """Format available tools for AI."""
        available = registry.list_available(ctx)
        if not available:
            return "No tools available."

        lines = []
        for tool in available:
            lines.append(f"- **{tool.name}** — {tool.description}")
            if tool.parameters:
                props = tool.parameters.get("properties", {})
                if props:
                    param_list = ", ".join(props.keys())
                    lines.append(f"  Parameters: {param_list}")

        return "\n".join(lines)

    @staticmethod
    def _format_commands(bot: Bot) -> str:
        """Format available slash commands for AI."""
        commands = bot.tree.get_commands()
        if not commands:
            return "No commands available."

        lines = []
        for cmd in commands:
            lines.append(f"- **/{cmd.name}** — {cmd.description or 'No description'}")

        return "\n".join(lines)

    @staticmethod
    def _format_state(ctx: Context) -> str:
        """Format current server state for AI."""
        if not ctx.guild:
            return "Direct message context (no guild state)."

        guild = ctx.guild
        member_count = len(guild.members)
        role_count = len(guild.roles)
        channel_count = len(guild.channels)
        moderator_roles = [r.name for r in guild.roles if r.permissions.manage_messages]

        return f"""
- **Guild:** {guild.name} (ID: {guild.id})
- **Members:** {member_count}
- **Roles:** {role_count}
- **Channels:** {channel_count}
- **Your Role:** {ctx.author.top_role.name if ctx.author.top_role else 'No role'}
- **Is Admin:** {ctx.is_admin()}
- **Moderator Roles:** {', '.join(moderator_roles) or 'None'}
"""

    @staticmethod
    def build_bot_state_summary(ctx: Context) -> dict:
        """Build a JSON-serializable bot state snapshot."""
        if not ctx.guild:
            return {"type": "dm", "context": "Direct message"}

        guild = ctx.guild
        return {
            "guild": {
                "name": guild.name,
                "id": guild.id,
                "member_count": len(guild.members),
                "role_count": len(guild.roles),
                "channel_count": len(guild.channels),
            },
            "user": {
                "name": ctx.author.name,
                "id": ctx.author.id,
                "top_role": ctx.author.top_role.name if ctx.author.top_role else None,
                "is_admin": ctx.is_admin(),
            },
            "roles": [
                {"name": r.name, "id": r.id, "position": r.position}
                for r in guild.roles[:10]  # Top 10 roles
            ],
        }
