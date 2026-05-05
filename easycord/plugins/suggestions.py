"""Suggestions system — submit, vote, and manage feature ideas."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord

from easycord import Plugin, slash, on
from easycord.plugins._config_manager import PluginConfigManager

if TYPE_CHECKING:
    from easycord import Context

logger = logging.getLogger(__name__)

_DEFAULTS = {
    "enabled": True,
    "suggestions_channel": None,
    "upvote_emoji": "👍",
    "downvote_emoji": "👎",
}


class SuggestionsPlugin(Plugin):
    """Suggestions system for feature ideas and feedback.

    Members submit suggestions that are posted to a channel for voting.
    Admins can approve/reject suggestions.

    Quick start::

        from easycord.plugins.suggestions import SuggestionsPlugin

        bot.add_plugin(SuggestionsPlugin())

    Commands::

        /suggest <idea>           — Submit a suggestion
        /suggestions              — View all pending suggestions
        /suggestion_approve <id>  — Approve a suggestion (admin)
        /suggestion_reject <id>   — Reject a suggestion (admin)
    """

    def __init__(self):
        super().__init__()
        self.config = PluginConfigManager(".easycord/suggestions")
        self.suggestion_counter = {}

    async def on_load(self) -> None:
        """Initialize suggestions plugin."""
        logger.info("SuggestionsPlugin loaded")

    async def _get_config(self, guild_id: int) -> dict:
        """Get suggestions config for guild."""
        return await self.config.get(guild_id, "suggestions", _DEFAULTS)

    async def _get_next_id(self, guild_id: int) -> int:
        """Get next suggestion ID."""
        cfg_obj = await self.config.store.load(guild_id)
        counter = cfg_obj.get_other("suggestion_counter", 0)
        next_id = counter + 1
        cfg_obj.set_other("suggestion_counter", next_id)
        await self.config.store.save(cfg_obj)
        return next_id

    @slash(description="Submit a server suggestion", guild_only=True)
    async def suggest(self, ctx: Context, idea: str) -> None:
        """Submit a suggestion."""
        cfg = await self._get_config(ctx.guild.id)
        channel_id = cfg.get("suggestions_channel")

        if not channel_id:
            await ctx.respond("❌ Suggestions channel not configured", ephemeral=True)
            return

        channel = ctx.guild.get_channel(channel_id)
        if not channel:
            await ctx.respond("❌ Suggestions channel not found", ephemeral=True)
            return

        suggestion_id = await self._get_next_id(ctx.guild.id)
        upvote = cfg.get("upvote_emoji", "👍")
        downvote = cfg.get("downvote_emoji", "👎")

        embed = discord.Embed(
            title=f"Suggestion #{suggestion_id}",
            description=idea,
            color=discord.Color.blurple(),
        )
        embed.set_author(name=ctx.user.name, icon_url=ctx.user.avatar.url if ctx.user.avatar else None)
        embed.set_footer(text=f"ID: {suggestion_id}")

        try:
            msg = await channel.send(embed=embed)
            await msg.add_reaction(upvote)
            await msg.add_reaction(downvote)

            # Store suggestion info
            cfg_obj = await self.config.store.load(ctx.guild.id)
            suggestions = cfg_obj.get_other("suggestions", {})
            suggestions[str(suggestion_id)] = {
                "user_id": ctx.user.id,
                "idea": idea,
                "message_id": msg.id,
                "status": "pending",
            }
            cfg_obj.set_other("suggestions", suggestions)
            await self.config.store.save(cfg_obj)

            await ctx.respond(f"✅ Suggestion #{suggestion_id} posted!", ephemeral=True)
        except discord.Forbidden:
            await ctx.respond("❌ Cannot post to suggestions channel", ephemeral=True)

    @slash(description="View pending suggestions", guild_only=True)
    async def suggestions(self, ctx: Context) -> None:
        """Show all pending suggestions."""
        cfg_obj = await self.config.store.load(ctx.guild.id)
        suggestions = cfg_obj.get_other("suggestions", {})

        pending = {sid: s for sid, s in suggestions.items() if s.get("status") == "pending"}

        if not pending:
            await ctx.respond("No pending suggestions")
            return

        lines = []
        for sid in sorted(pending.keys(), key=int, reverse=True)[:10]:
            s = pending[sid]
            lines.append(f"**#{sid}** — {s['idea'][:100]}")

        embed = discord.Embed(
            title=f"Pending Suggestions ({len(pending)})",
            description="\n".join(lines),
            color=discord.Color.blurple(),
        )
        await ctx.send_embed_from_dict(embed.to_dict())

    @slash(description="Approve a suggestion", guild_only=True)
    async def suggestion_approve(self, ctx: Context, suggestion_id: int) -> None:
        """Approve a suggestion (admin only)."""
        if not ctx.user.guild_permissions.manage_guild:
            await ctx.respond("❌ You lack `manage_guild` permission", ephemeral=True)
            return

        cfg_obj = await self.config.store.load(ctx.guild.id)
        suggestions = cfg_obj.get_other("suggestions", {})
        suggestion = suggestions.get(str(suggestion_id))

        if not suggestion:
            await ctx.respond("❌ Suggestion not found", ephemeral=True)
            return

        suggestion["status"] = "approved"
        cfg_obj.set_other("suggestions", suggestions)
        await self.config.store.save(cfg_obj)

        await ctx.respond(f"✅ Suggestion #{suggestion_id} approved")

    @slash(description="Reject a suggestion", guild_only=True)
    async def suggestion_reject(self, ctx: Context, suggestion_id: int) -> None:
        """Reject a suggestion (admin only)."""
        if not ctx.user.guild_permissions.manage_guild:
            await ctx.respond("❌ You lack `manage_guild` permission", ephemeral=True)
            return

        cfg_obj = await self.config.store.load(ctx.guild.id)
        suggestions = cfg_obj.get_other("suggestions", {})
        suggestion = suggestions.get(str(suggestion_id))

        if not suggestion:
            await ctx.respond("❌ Suggestion not found", ephemeral=True)
            return

        suggestion["status"] = "rejected"
        cfg_obj.set_other("suggestions", suggestions)
        await self.config.store.save(cfg_obj)

        await ctx.respond(f"✅ Suggestion #{suggestion_id} rejected")
