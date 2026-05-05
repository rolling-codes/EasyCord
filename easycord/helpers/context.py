"""Context operation helpers."""
from __future__ import annotations

from typing import TYPE_CHECKING

import discord

from easycord.helpers.embed import EmbedBuilder

if TYPE_CHECKING:
    from easycord import Context


class ContextHelpers:
    """Shortcuts for common context operations."""

    @staticmethod
    async def respond_error(ctx: Context, title: str, description: str) -> discord.Message:
        """Send error embed response."""
        embed = EmbedBuilder.error(title, description)
        return await ctx.respond(embed=embed.build())

    @staticmethod
    async def respond_success(ctx: Context, title: str, description: str) -> discord.Message:
        """Send success embed response."""
        embed = EmbedBuilder.success(title, description)
        return await ctx.respond(embed=embed.build())

    @staticmethod
    async def respond_info(ctx: Context, title: str, description: str) -> discord.Message:
        """Send info embed response."""
        embed = EmbedBuilder.info(title, description)
        return await ctx.respond(embed=embed.build())

    @staticmethod
    async def respond_warning(ctx: Context, title: str, description: str) -> discord.Message:
        """Send warning embed response."""
        embed = EmbedBuilder.warning(title, description)
        return await ctx.respond(embed=embed.build())

    @staticmethod
    def list_members(ctx: Context, role_filter: str | discord.Role | None = None) -> list[discord.Member]:
        """List guild members, optionally filtered by role."""
        if not ctx.guild:
            return []
        members = list(ctx.guild.members)
        if isinstance(role_filter, str):
            role = discord.utils.get(ctx.guild.roles, name=role_filter)
            if role:
                members = [m for m in members if role in m.roles]
        elif isinstance(role_filter, discord.Role):
            members = [m for m in members if role_filter in m.roles]
        return members

    @staticmethod
    async def bulk_timeout(
        ctx: Context, user_ids: list[int], duration: int, reason: str = ""
    ) -> dict[int, bool]:
        """Timeout multiple users (duration in seconds)."""
        from datetime import timedelta

        results = {}
        timeout = discord.utils.utcnow() + timedelta(seconds=duration)
        for user_id in user_ids:
            try:
                member = await ctx.guild.fetch_member(user_id)
                await member.timeout(timeout, reason=reason)
                results[user_id] = True
            except Exception:
                results[user_id] = False
        return results

    @staticmethod
    async def bulk_role_add(ctx: Context, user_ids: list[int], role_id: int) -> dict[int, bool]:
        """Add role to multiple users."""
        results = {}
        role = ctx.guild.get_role(role_id) if ctx.guild else None
        if not role:
            return {uid: False for uid in user_ids}
        for user_id in user_ids:
            try:
                member = await ctx.guild.fetch_member(user_id)
                await member.add_roles(role)
                results[user_id] = True
            except Exception:
                results[user_id] = False
        return results

    @staticmethod
    async def bulk_role_remove(ctx: Context, user_ids: list[int], role_id: int) -> dict[int, bool]:
        """Remove role from multiple users."""
        results = {}
        role = ctx.guild.get_role(role_id) if ctx.guild else None
        if not role:
            return {uid: False for uid in user_ids}
        for user_id in user_ids:
            try:
                member = await ctx.guild.fetch_member(user_id)
                await member.remove_roles(role)
                results[user_id] = True
            except Exception:
                results[user_id] = False
        return results

    @staticmethod
    def paginate_list(items: list, per_page: int = 10) -> list[list]:
        """Split list into pages."""
        pages = []
        for i in range(0, len(items), per_page):
            pages.append(items[i : i + per_page])
        return pages

    @staticmethod
    async def send_paginated(
        ctx: Context, pages: list[list], template: str = "Page", item_format: str = "{}"
    ) -> discord.Message:
        """Send first page of paginated content."""
        if not pages:
            return await ContextHelpers.respond_error(ctx, "Empty", "No items to display")
        first_page = pages[0]
        content = "\n".join(item_format.format(item) for item in first_page)
        embed = (
            EmbedBuilder(f"{template} 1/{len(pages)}", content)
            .set_footer(f"Showing {len(first_page)} of {sum(len(p) for p in pages)} items")
            .build()
        )
        return await ctx.respond(embed=embed)
