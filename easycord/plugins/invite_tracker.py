"""Track invites — see who invited whom."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord

from easycord import Plugin, on
from easycord.plugins._config_manager import PluginConfigManager

if TYPE_CHECKING:
    from easycord import Context

logger = logging.getLogger(__name__)


class InviteTrackerPlugin(Plugin):
    """Track server invites and log who invited new members.

    On member join, check active invites to detect which link was used.
    Log invite source. Useful for growth tracking and member onboarding.
    Per-guild config for log channel.

    Quick start::

        from easycord.plugins.invite_tracker import InviteTrackerPlugin

        bot.add_plugin(InviteTrackerPlugin())

    Configure::

        /invite_log_channel <#channel>  — Set invite log channel
        /invite_tracker_config          — View current config
    """

    def __init__(self):
        super().__init__()
        self.config = PluginConfigManager(".easycord/invite-tracker")
        # Cache invites to detect changes: {guild_id: {code: uses}}
        self._invite_cache: dict[int, dict[str, int]] = {}

    async def on_load(self) -> None:
        """Initialize invite tracker plugin."""
        logger.info("InviteTrackerPlugin loaded")
        # Cache current invites
        for guild in self.bot.guilds:
            await self._refresh_invite_cache(guild.id)

    async def _get_config(self, guild_id: int) -> dict:
        """Get invite tracker config for guild."""
        return await self.config.get(
            guild_id,
            "invite_tracker",
            {"enabled": True, "log_channel": None}
        )

    async def _refresh_invite_cache(self, guild_id: int) -> None:
        """Refresh invite cache for guild."""
        guild = self.bot.get_guild(guild_id)
        if not guild:
            return

        try:
            invites = await guild.invites()
            cache = {invite.code: invite.uses for invite in invites}
            self._invite_cache[guild_id] = cache
        except discord.Forbidden:
            logger.warning("No permission to view invites in guild %s", guild_id)

    async def _log_invite(self, member: discord.Member, invite_code: str | None) -> None:
        """Log member join via invite."""
        cfg = await self._get_config(member.guild.id)
        channel_id = cfg.get("log_channel")

        if not channel_id:
            return

        channel = member.guild.get_channel(channel_id)
        if not channel:
            logger.warning("Invite log channel %s not found", channel_id)
            return

        embed = discord.Embed(
            title="Member Joined via Invite",
            description=f"{member.mention} ({member.name}#{member.discriminator})",
            color=discord.Color.green(),
        )
        if invite_code:
            embed.add_field(name="Invite Code", value=f"`{invite_code}`", inline=True)
        else:
            embed.add_field(name="Invite", value="Unknown (vanity URL or direct join)", inline=True)

        embed.set_thumbnail(url=member.avatar.url if member.avatar else None)
        embed.set_footer(text=f"ID: {member.id}")

        try:
            await channel.send(embed=embed)
        except discord.Forbidden:
            logger.error("No permission to post to invite log channel %s", channel_id)
        except discord.HTTPException as e:
            logger.error("Failed to post invite log: %s", e)

    @on("member_join")
    async def _on_member_join(self, member: discord.Member) -> None:
        """Track member join and detect invite used."""
        guild_id = member.guild.id
        old_cache = self._invite_cache.get(guild_id, {})

        # Refresh invites
        await self._refresh_invite_cache(guild_id)
        new_cache = self._invite_cache.get(guild_id, {})

        # Find which invite was used (Discord increments uses after a join).
        used_invite = None
        for code, new_uses in new_cache.items():
            old_uses = old_cache.get(code, new_uses)
            if new_uses > old_uses:
                used_invite = code
                break

        logger.info("Member joined: %s (invite: %s)", member, used_invite or "unknown")
        await self._log_invite(member, used_invite)

    @on("invite_create")
    async def _on_invite_create(self, invite: discord.Invite) -> None:
        """Update cache when invite created."""
        if not invite.guild:
            return

        if invite.guild.id not in self._invite_cache:
            self._invite_cache[invite.guild.id] = {}

        self._invite_cache[invite.guild.id][invite.code] = invite.uses

    @on("invite_delete")
    async def _on_invite_delete(self, invite: discord.Invite) -> None:
        """Update cache when invite deleted."""
        if not invite.guild:
            return

        if invite.guild.id in self._invite_cache and invite.code in self._invite_cache[invite.guild.id]:
            del self._invite_cache[invite.guild.id][invite.code]
