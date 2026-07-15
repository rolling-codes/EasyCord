"""Suggestions system — submit, vote, and manage feature ideas."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord

from easycord import Plugin, slash
from easycord.config_schema import ConfigSchema
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

SCHEMA = ConfigSchema(key="suggestions", version=1, defaults=_DEFAULTS)


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

    async def on_load(self) -> None:
        """Initialize suggestions plugin."""
        logger.info("SuggestionsPlugin loaded")

    async def _get_config(self, guild_id: int) -> dict:
        """Get suggestions config for guild, healing any missing keys via SCHEMA."""
        return await self.config.get_schema(guild_id, SCHEMA)

    async def _get_next_id(self, guild_id: int) -> int:
        """Atomically increment and return the next suggestion ID.

        The whole read-increment-write runs under the per-guild lock so two
        concurrent ``/suggest`` calls can't both claim the same ID.
        """
        def _apply(cfg) -> int:
            next_id = cfg.get_other("suggestion_counter", 0) + 1
            cfg.set_other("suggestion_counter", next_id)
            return next_id

        return await self.config.store.mutate(guild_id, _apply)

    @slash(description="Submit a server suggestion", guild_only=True)
    async def suggest(self, ctx: Context, idea: str) -> None:
        """Submit a suggestion."""
        assert ctx.guild is not None  # guaranteed by guild_only=True
        cfg = await self._get_config(ctx.guild.id)
        channel_id = cfg.get("suggestions_channel")

        if not channel_id:
            await ctx.respond("❌ Suggestions channel not configured", ephemeral=True)
            return

        channel = ctx.guild.get_channel(channel_id)
        if not isinstance(channel, (discord.TextChannel, discord.Thread)):
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

            # Store suggestion info atomically (preserve concurrent writers' entries)
            def _store(cfg) -> None:
                suggestions = cfg.get_other("suggestions", {})
                suggestions[str(suggestion_id)] = {
                    "user_id": ctx.user.id,
                    "idea": idea,
                    "message_id": msg.id,
                    "status": "pending",
                }
                cfg.set_other("suggestions", suggestions)

            await self.config.store.mutate(ctx.guild.id, _store)

            await ctx.respond(f"✅ Suggestion #{suggestion_id} posted!", ephemeral=True)
        except discord.Forbidden:
            await ctx.respond("❌ Cannot post to suggestions channel", ephemeral=True)

    @slash(description="View pending suggestions", guild_only=True)
    async def suggestions(self, ctx: Context) -> None:
        """Show all pending suggestions."""
        assert ctx.guild is not None  # guaranteed by guild_only=True
        cfg_obj = await self.config.store.load(ctx.guild.id)
        suggestions = cfg_obj.get_other("suggestions", {})

        pending = {
            sid: s
            for sid, s in suggestions.items()
            if isinstance(s, dict) and s.get("status") == "pending"
        }


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
        await ctx.respond(embed=embed)

    @slash(description="Approve a suggestion", guild_only=True)
    async def suggestion_approve(self, ctx: Context, suggestion_id: int) -> None:
        """Approve a suggestion (admin only)."""
        assert ctx.guild is not None  # guaranteed by guild_only=True
        assert isinstance(ctx.user, discord.Member)  # guild_only ⇒ invoker is a Member
        if not ctx.user.guild_permissions.manage_guild:
            await ctx.respond("❌ You lack `manage_guild` permission", ephemeral=True)
            return

        def _apply(cfg) -> bool:
            suggestions = cfg.get_other("suggestions", {})
            suggestion = suggestions.get(str(suggestion_id))
            if suggestion is None:
                return False
            suggestion["status"] = "approved"
            cfg.set_other("suggestions", suggestions)
            return True

        if not await self.config.store.mutate(ctx.guild.id, _apply):
            await ctx.respond("❌ Suggestion not found", ephemeral=True)
            return

        await ctx.respond(f"✅ Suggestion #{suggestion_id} approved")

    @slash(description="Reject a suggestion", guild_only=True)
    async def suggestion_reject(self, ctx: Context, suggestion_id: int) -> None:
        """Reject a suggestion (admin only)."""
        assert ctx.guild is not None  # guaranteed by guild_only=True
        assert isinstance(ctx.user, discord.Member)  # guild_only ⇒ invoker is a Member
        if not ctx.user.guild_permissions.manage_guild:
            await ctx.respond("❌ You lack `manage_guild` permission", ephemeral=True)
            return

        def _apply(cfg) -> bool:
            suggestions = cfg.get_other("suggestions", {})
            suggestion = suggestions.get(str(suggestion_id))
            if suggestion is None:
                return False
            suggestion["status"] = "rejected"
            cfg.set_other("suggestions", suggestions)
            return True

        if not await self.config.store.mutate(ctx.guild.id, _apply):
            await ctx.respond("❌ Suggestion not found", ephemeral=True)
            return

        await ctx.respond(f"✅ Suggestion #{suggestion_id} rejected")
