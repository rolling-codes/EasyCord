"""Starboard — archive popular messages to a channel."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord

from easycord import Context, Plugin, on, slash
from easycord.plugins._config_manager import PluginConfigManager
from easycord.plugins._utils import SENDABLE_CHANNEL_TYPES

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Default starboard config
_DEFAULTS = {
    "enabled": True,
    "channel_id": None,
    "emoji": "⭐",
    "threshold": 3,
}


class StarboardPlugin(Plugin):
    """Archive messages with high emoji reactions to a starboard channel.

    When a message gets enough ⭐ reactions, bot posts an archive embed
    to the starboard channel. Removes from starboard if reactions drop below threshold.
    Per-guild config for channel + emoji + threshold.

    Quick start::

        from easycord.plugins.starboard import StarboardPlugin

        bot.add_plugin(StarboardPlugin())

    Configure::

        /starboard_channel <#channel>  — Set starboard channel
        /starboard_emoji <emoji>       — Set reaction emoji (default ⭐)
        /starboard_threshold <count>   — Set reaction threshold (default 3)
        /starboard_config              — View current config
    """

    def __init__(self):
        super().__init__()
        self.config = PluginConfigManager(".easycord/starboard")

    async def on_load(self) -> None:
        """Initialize starboard plugin."""
        logger.info("StarboardPlugin loaded")

    async def _get_config(self, guild_id: int) -> dict:
        """Get starboard config for guild."""
        return await self.config.get(guild_id, "starboard", _DEFAULTS)

    async def _update_config(self, guild_id: int, **kwargs) -> dict:
        """Update starboard config atomically."""
        return await self.config.update(guild_id, "starboard", **kwargs)

    async def _get_archived(self, guild_id: int) -> dict[str, int]:
        """Get archived messages map for guild."""
        cfg_obj = await self.config.store.load(guild_id)
        return cfg_obj.get_other("archived_messages", {})

    async def _set_archived(self, guild_id: int, message_id: int, post_id: int) -> None:
        """Store archived message mapping atomically."""
        def _apply(cfg) -> None:
            archived = cfg.get_other("archived_messages", {})
            archived[str(message_id)] = post_id
            cfg.set_other("archived_messages", archived)

        await self.config.store.mutate(guild_id, _apply)

    async def _remove_archived(self, guild_id: int, message_id: int) -> None:
        """Remove archived message mapping atomically."""
        def _apply(cfg) -> None:
            archived = cfg.get_other("archived_messages", {})
            archived.pop(str(message_id), None)
            cfg.set_other("archived_messages", archived)

        await self.config.store.mutate(guild_id, _apply)

    async def _archive_message(self, message: discord.Message, reaction_count: int) -> None:
        """Post or update message on starboard."""
        if not message.guild:
            return

        archived = await self._get_archived(message.guild.id)
        existing_post_id = archived.get(str(message.id))

        cfg = await self._get_config(message.guild.id)
        channel_id = cfg.get("channel_id")

        if not channel_id:
            return

        channel = message.guild.get_channel(channel_id)
        if not isinstance(channel, SENDABLE_CHANNEL_TYPES):
            logger.warning("Starboard channel %s not found or not sendable", channel_id)
            return

        # Create starboard embed
        embed = discord.Embed(
            title="⭐ Starred Message",
            description=message.content[:2000] if message.content else "(no text)",
            color=discord.Color.gold(),
            timestamp=message.created_at,
        )
        embed.set_author(name=message.author.display_name, icon_url=message.author.avatar.url if message.author.avatar else None)
        embed.add_field(name="Reactions", value=f"{cfg.get('emoji', '⭐')} {reaction_count}", inline=True)
        embed.add_field(
            name="Source",
            value=f"[Jump to message]({message.jump_url})",
            inline=True,
        )

        # Add first image if exists
        if message.attachments:
            img = next((a for a in message.attachments if a.content_type and a.content_type.startswith("image")), None)
            if img:
                embed.set_image(url=img.url)

        try:
            if existing_post_id:
                try:
                    post = await channel.fetch_message(existing_post_id)
                    await post.edit(embed=embed)
                    return
                except discord.NotFound:
                    pass # Post was deleted, send a new one

            post = await channel.send(embed=embed)
            await self._set_archived(message.guild.id, message.id, post.id)
            logger.info("Archived message %s to starboard", message.id)
        except discord.Forbidden:
            logger.error("No permission to post to starboard channel %s", channel_id)
        except discord.HTTPException as e:
            logger.error("Failed to post to starboard: %s", e)

    async def _unarchive_message(self, guild_id: int, message_id: int) -> None:
        """Remove message from starboard."""
        archived = await self._get_archived(guild_id)
        post_id = archived.get(str(message_id))
        if not post_id:
            return

        cfg = await self._get_config(guild_id)
        channel_id = cfg.get("channel_id")

        if not channel_id:
            return

        guild = self.bot.get_guild(guild_id)
        if not guild:
            return

        channel = guild.get_channel(channel_id)
        if not isinstance(channel, SENDABLE_CHANNEL_TYPES):
            return

        try:
            post = await channel.fetch_message(post_id)
            await post.delete()
            await self._remove_archived(guild_id, message_id)
            logger.info("Removed message %s from starboard", message_id)
        except discord.NotFound:
            # Already deleted, just clean up
            await self._remove_archived(guild_id, message_id)
        except discord.Forbidden:
            logger.error("No permission to delete from starboard")
        except discord.HTTPException as e:
            logger.error("Failed to remove from starboard: %s", e)

    @on("raw_reaction_add")
    async def _on_reaction_add(self, payload: discord.RawReactionActionEvent) -> None:
        """Check reaction count and archive if threshold met."""
        if payload.guild_id is None or (
            self.bot.user is not None and payload.user_id == self.bot.user.id
        ):
            return

        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return

        cfg = await self._get_config(guild.id)
        if not cfg.get("enabled"):
            return

        # Only react to configured emoji
        if str(payload.emoji) != cfg.get("emoji", "⭐"):
            return

        try:
            channel = guild.get_channel(payload.channel_id)
            if not isinstance(channel, SENDABLE_CHANNEL_TYPES):
                return

            message = await channel.fetch_message(payload.message_id)
            if not message:
                return

            # Count emoji reactions
            reaction = next((r for r in message.reactions if str(r.emoji) == str(payload.emoji)), None)
            if reaction and reaction.count >= cfg.get("threshold", 3):
                await self._archive_message(message, reaction.count)

        except discord.NotFound:
            pass  # message or channel was deleted before the reaction could be processed
        except discord.Forbidden:
            logger.warning("No permission to fetch message in %s", payload.guild_id)
        except discord.HTTPException as e:
            logger.error("Failed to check reaction: %s", e)

    @on("raw_reaction_remove")
    async def _on_reaction_remove(self, payload: discord.RawReactionActionEvent) -> None:
        """Check if message should be unarchived."""
        if payload.guild_id is None or (
            self.bot.user is not None and payload.user_id == self.bot.user.id
        ):
            return

        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return

        cfg = await self._get_config(guild.id)
        if not cfg.get("enabled"):
            return

        if str(payload.emoji) != cfg.get("emoji", "⭐"):
            return

        try:
            channel = guild.get_channel(payload.channel_id)
            if not isinstance(channel, SENDABLE_CHANNEL_TYPES):
                return

            message = await channel.fetch_message(payload.message_id)
            if not message:
                return

            # Count emoji reactions
            reaction = next((r for r in message.reactions if str(r.emoji) == str(payload.emoji)), None)
            count = reaction.count if reaction else 0

            # Unarchive if below threshold
            if count < cfg.get("threshold", 3):
                await self._unarchive_message(guild.id, payload.message_id)

        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            pass  # message/channel deleted or inaccessible; nothing to unarchive

    # ── Slash commands ────────────────────────────────────────

    @slash(description="Set the channel for starboard messages.", permissions=["manage_guild"], guild_only=True)
    async def starboard_channel(self, ctx: Context, channel: discord.TextChannel) -> None:
        assert ctx.guild is not None  # guaranteed by guild_only=True
        await self._update_config(ctx.guild.id, channel_id=channel.id)
        await ctx.respond(f"Starboard messages will be posted in {channel.mention}.", ephemeral=True)

    @slash(description="Set the emoji to trigger starboard.", permissions=["manage_guild"], guild_only=True)
    async def starboard_emoji(self, ctx: Context, emoji: str) -> None:
        assert ctx.guild is not None  # guaranteed by guild_only=True
        await self._update_config(ctx.guild.id, emoji=emoji)
        await ctx.respond(f"Starboard emoji set to {emoji}.", ephemeral=True)

    @slash(description="Set the reaction threshold for starboard.", permissions=["manage_guild"], guild_only=True)
    async def starboard_threshold(self, ctx: Context, threshold: int) -> None:
        assert ctx.guild is not None  # guaranteed by guild_only=True
        if threshold < 1:
            await ctx.respond("Threshold must be at least 1.", ephemeral=True)
            return
        await self._update_config(ctx.guild.id, threshold=threshold)
        await ctx.respond(f"Starboard threshold set to {threshold}.", ephemeral=True)

    @slash(description="Show the current starboard configuration for this server.", guild_only=True)
    async def starboard_config(self, ctx: Context) -> None:
        assert ctx.guild is not None  # guaranteed by guild_only=True
        cfg = await self._get_config(ctx.guild.id)
        channel_id = cfg.get("channel_id")
        channel = ctx.guild.get_channel(channel_id) if channel_id else None
        
        embed = discord.Embed(
            title=f"⭐ Starboard Config — {ctx.guild.name}",
            color=discord.Color.gold(),
        )
        embed.add_field(name="Enabled", value="✅" if cfg.get("enabled") else "❌", inline=True)
        embed.add_field(name="Channel", value=channel.mention if channel else "*not set*", inline=True)
        embed.add_field(name="Emoji", value=cfg.get("emoji", "⭐"), inline=True)
        embed.add_field(name="Threshold", value=str(cfg.get("threshold", 3)), inline=True)
        
        await ctx.respond(embed=embed, ephemeral=True)
