"""Member join/leave/update event logging to a designated channel."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import discord

from easycord import Plugin, on
from easycord.plugins._config_manager import PluginConfigManager

if TYPE_CHECKING:
    from easycord import Context

logger = logging.getLogger(__name__)

_DEFAULTS = {
    "log_channel": None,
    "enabled": True,
}


class MemberLoggingPlugin(Plugin):
    """Log member join, leave, update events to a channel.

    Tracks: joins, leaves, nickname changes, role changes, timeout/unmute.
    Logs to designated channel with embeds. Per-guild config.

    Quick start::

        from easycord.plugins.member_logging import MemberLoggingPlugin

        bot.add_plugin(MemberLoggingPlugin())

    Configure::

        /member_log_channel <channel>  — Set where logs are posted
        /member_log_config             — View current config
    """

    def __init__(self):
        super().__init__()
        self.config = PluginConfigManager(".easycord/member-logging")

    async def on_load(self) -> None:
        """Initialize member logging plugin."""
        logger.info("MemberLoggingPlugin loaded")

    async def _get_config(self, guild_id: int) -> dict:
        """Get member logging config for guild."""
        return await self.config.get(guild_id, "member_logging", _DEFAULTS)

    async def _log_to_channel(self, guild: discord.Guild, embed: discord.Embed) -> None:
        """Post embed to configured log channel."""
        cfg = await self._get_config(guild.id)
        channel_id = cfg.get("log_channel")

        if not channel_id or not cfg.get("enabled"):
            return

        channel = guild.get_channel(channel_id)
        if not channel:
            logger.warning("Member log channel %s not found in guild %s", channel_id, guild.id)
            return

        try:
            await channel.send(embed=embed)
        except discord.Forbidden:
            logger.error("No permission to post to member log channel %s", channel_id)
        except discord.HTTPException as e:
            logger.error("Failed to post member log: %s", e)

    @on("member_join")
    async def _on_member_join(self, member: discord.Member) -> None:
        """Log member join."""
        embed = discord.Embed(
            title="Member Joined",
            description=f"{member.mention} ({member.name}#{member.discriminator})",
            color=discord.Color.green(),
            timestamp=datetime.now(timezone.utc),
        )
        embed.add_field(name="Account Created", value=member.created_at.strftime("%Y-%m-%d"), inline=True)
        embed.set_thumbnail(url=member.avatar.url if member.avatar else None)
        embed.set_footer(text=f"ID: {member.id}")

        logger.info("Member joined: %s (%s)", member, member.id)
        await self._log_to_channel(member.guild, embed)

    @on("member_remove")
    async def _on_member_remove(self, member: discord.Member) -> None:
        """Log member leave."""
        embed = discord.Embed(
            title="Member Left",
            description=f"{member.mention} ({member.name}#{member.discriminator})",
            color=discord.Color.red(),
            timestamp=datetime.now(timezone.utc),
        )
        embed.add_field(
            name="Member Since",
            value=member.joined_at.strftime("%Y-%m-%d") if member.joined_at else "Unknown",
            inline=True,
        )
        embed.set_thumbnail(url=member.avatar.url if member.avatar else None)
        embed.set_footer(text=f"ID: {member.id}")

        logger.info("Member left: %s (%s)", member, member.id)
        await self._log_to_channel(member.guild, embed)

    @on("member_update")
    async def _on_member_update(self, before: discord.Member, after: discord.Member) -> None:
        """Log member updates (nickname, roles, timeout, etc)."""
        if not before.guild:
            return

        changes = []

        # Nickname change
        if before.nick != after.nick:
            before_nick = before.nick or before.name
            after_nick = after.nick or after.name
            changes.append(f"Nickname: `{before_nick}` → `{after_nick}`")

        # Role additions
        added_roles = set(after.roles) - set(before.roles)
        if added_roles:
            role_names = ", ".join(role.mention for role in added_roles)
            changes.append(f"Roles added: {role_names}")

        # Role removals
        removed_roles = set(before.roles) - set(after.roles)
        if removed_roles:
            role_names = ", ".join(role.mention for role in removed_roles)
            changes.append(f"Roles removed: {role_names}")

        # Timeout added
        if before.timed_out_until is None and after.timed_out_until is not None:
            until = after.timed_out_until.strftime("%Y-%m-%d %H:%M:%S UTC")
            changes.append(f"Timed out until: {until}")

        # Timeout removed
        if before.timed_out_until is not None and after.timed_out_until is None:
            changes.append("Timeout removed")

        if not changes:
            return

        embed = discord.Embed(
            title="Member Updated",
            description=f"{after.mention} ({after.name}#{after.discriminator})",
            color=discord.Color.blue(),
            timestamp=datetime.now(timezone.utc),
        )

        for change in changes:
            embed.add_field(name="Change", value=change, inline=False)

        embed.set_thumbnail(url=after.avatar.url if after.avatar else None)
        embed.set_footer(text=f"ID: {after.id}")

        logger.info("Member updated: %s (%s) — %s", after, after.id, "; ".join(changes))
        await self._log_to_channel(after.guild, embed)

    @on("user_update")
    async def _on_user_update(self, before: discord.User, after: discord.User) -> None:
        """Log user global updates (username, avatar, etc).

        Note: This fires for ALL guilds the user is in, so we can only
        log to common channels if needed. For now just log username changes.
        """
        if before.name != after.name:
            logger.info("User renamed: %s → %s (%s)", before.name, after.name, after.id)
