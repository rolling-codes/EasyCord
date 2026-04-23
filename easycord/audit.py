"""Structured audit logging to a configured Discord channel."""
from __future__ import annotations

import datetime
import logging
from typing import TYPE_CHECKING

import discord

if TYPE_CHECKING:
    from .context import Context
    from .server_config import ServerConfigStore

logger = logging.getLogger("easycord")


class AuditLog:
    """Posts structured embeds to a guild's configured audit channel.

    The channel ID is read from ``ServerConfig`` on every call, so it can be
    reconfigured at runtime without restarting the bot. If no channel is
    configured, the call silently does nothing (``silent=True`` default).

    Example::

        store = ServerConfigStore()
        audit = AuditLog(store, channel_key="audit_log")

        # In your slash commands:
        @bot.slash(description="Ban a member", permissions=["ban_members"])
        async def ban(ctx, member: discord.Member, reason: str = ""):
            await member.ban(reason=reason)
            await audit.log(ctx, action="ban", target=member, reason=reason)
            await ctx.respond(f"Banned {member.display_name}.")

        # Configure the channel once (e.g. in a setup command):
        cfg = await store.load(ctx.guild.id)
        cfg.set_channel("audit_log", log_channel.id)
        await store.save(cfg)
    """

    def __init__(
        self,
        store: ServerConfigStore,
        *,
        channel_key: str = "audit_log",
        silent: bool = True,
        color: discord.Color = discord.Color.orange(),
    ) -> None:
        self._store = store
        self._key = channel_key
        self._silent = silent
        self._color = color

    async def log(
        self,
        ctx: Context,
        *,
        action: str,
        target: discord.abc.Snowflake | None = None,
        reason: str | None = None,
        **extra_fields: str,
    ) -> None:
        """Post an audit embed to the configured channel.

        Parameters
        ----------
        ctx:
            The command context (used for guild ID, invoking user, and client).
        action:
            Short label for what happened (e.g. ``"ban"``, ``"kick"``).
        target:
            The user or object the action was applied to.
        reason:
            Optional reason string. Shown as its own embed field.
        **extra_fields:
            Any additional ``name=value`` pairs to include as embed fields.
            Underscores in names are replaced with spaces and title-cased.
        """
        if not ctx.guild:
            return

        cfg = await self._store.load(ctx.guild.id)
        channel_id = cfg.get_channel(self._key)

        if channel_id is None:
            if not self._silent:
                logger.warning(
                    "AuditLog: no channel configured for key %r in guild %s",
                    self._key,
                    ctx.guild.id,
                )
            return

        client = ctx.interaction.client
        if client is None:
            if not self._silent:
                logger.warning(
                    "AuditLog: cannot resolve channel %s because the interaction has no client",
                    channel_id,
                )
            return

        try:
            channel = client.get_channel(channel_id) or await client.fetch_channel(channel_id)
        except (discord.NotFound, discord.Forbidden) as exc:
            logger.warning(
                "AuditLog: cannot access channel %s: %s", channel_id, exc
            )
            return

        if not hasattr(channel, "send"):
            logger.warning(
                "AuditLog: channel %s is not messageable; skipping audit post",
                channel_id,
            )
            return

        embed = discord.Embed(
            title=f"Action: {action}",
            color=self._color,
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )
        embed.add_field(name="Invoked by", value=str(ctx.user), inline=True)
        if target is not None:
            embed.add_field(name="Target", value=str(target), inline=True)
        if reason:
            embed.add_field(name="Reason", value=reason, inline=False)
        for name, value in extra_fields.items():
            embed.add_field(
                name=name.replace("_", " ").title(), value=value, inline=True
            )

        try:
            await channel.send(embed=embed)
        except discord.HTTPException as exc:
            logger.warning(
                "AuditLog: failed to post to channel %s: %s", channel_id, exc
            )
