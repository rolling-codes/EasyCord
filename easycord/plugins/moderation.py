"""Manual moderation tools — kick, ban, timeout, warn, mute without AI."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord

from easycord import Plugin, RateLimit, ToolLimiter, on, slash
from easycord.plugins._config_manager import PluginConfigManager

if TYPE_CHECKING:
    from easycord import Context

logger = logging.getLogger(__name__)

_DEFAULTS = {
    "enabled": True,
    "audit_channel": None,
    "mute_role": None,
    "auto_warn_threshold": 3,
    "enable_warnings": True,
}


class ModerationPlugin(Plugin):
    """Manual server moderation tools.

    Provides admin commands for standard moderation actions: kick, ban,
    timeout, warn, mute, unban. Tracks moderation history and prevents abuse
    via rate limiting. Fully featured without AI.

    Quick start::

        from easycord.plugins.moderation import ModerationPlugin

        bot.add_plugin(ModerationPlugin())

    Commands registered::

        /kick           — Remove user from server (no history)
        /ban            — Ban user from server
        /unban          — Unban previously banned user
        /timeout        — Temporarily mute a user (1-28 days)
        /warn           — Issue a formal warning (tracked)
        /mute           — Add mute role (permanent until removed)
        /unmute         — Remove mute role
        /warnings       — View warning history for a user
        /mod_config     — View moderation settings
    """

    def __init__(self):
        super().__init__()
        self.config = PluginConfigManager(".easycord/moderation")
        self.warn_limiter = ToolLimiter()
        self.ban_limiter = ToolLimiter()

    async def on_load(self) -> None:
        """Initialize moderation plugin."""
        logger.info("ModerationPlugin loaded")


    async def _get_config(self, guild_id: int) -> dict:
        """Get moderation config for guild."""
        return await self.config.get(guild_id, "moderation", _DEFAULTS)

    async def _update_config(self, guild_id: int, **kwargs) -> dict:
        """Update moderation config atomically."""
        return await self.config.update(guild_id, "moderation", **kwargs)

    async def _log_moderation(self, ctx: Context, action: str, target: discord.User, reason: str, duration: str = None) -> None:
        """Log moderation action to audit channel."""
        cfg = await self._get_config(ctx.guild.id)
        audit_channel_id = cfg.get("audit_channel")

        if not audit_channel_id:
            return

        audit_channel = ctx.guild.get_channel(audit_channel_id)
        if not audit_channel:
            return

        embed = discord.Embed(
            title=f"Moderation Log — {action.upper()}",
            description=f"User: {target.mention} ({target.name}#{target.discriminator})",
            color=discord.Color.red() if action in ("ban", "kick") else discord.Color.orange(),
        )
        embed.add_field(name="Reason", value=reason or "No reason provided", inline=False)
        if duration:
            embed.add_field(name="Duration", value=duration, inline=True)
        embed.add_field(name="Moderator", value=ctx.user.mention, inline=True)
        embed.set_footer(text=f"User ID: {target.id}")

        try:
            await audit_channel.send(embed=embed)
        except discord.Forbidden:
            logger.warning("Cannot post to audit channel %s", audit_channel_id)

    async def _get_or_create_mute_role(self, guild: discord.Guild) -> discord.Role | None:
        """Get or create mute role for guild."""
        mute_role = discord.utils.get(guild.roles, name="Muted")
        if not mute_role:
            try:
                mute_role = await guild.create_role(name="Muted", reason="ModerationPlugin auto-created")
                logger.info("Created mute role for guild %s", guild.id)
            except discord.Forbidden:
                logger.error("Cannot create mute role for guild %s", guild.id)
                return None
        return mute_role

    @slash(description="Kick a user from the server", guild_only=True)
    async def kick(self, ctx: Context, user: discord.User, reason: str = None) -> None:
        """Kick a user from the server."""
        if not ctx.user.guild_permissions.kick_members:
            await ctx.send("❌ You lack `kick_members` permission")
            return

        member = ctx.guild.get_member(user.id)
        if not member:
            await ctx.send(f"❌ {user.mention} is not in this server")
            return

        try:
            await member.kick(reason=reason or "No reason provided")
            await ctx.send(f"✅ Kicked {user.mention}")
            await self._log_moderation(ctx, "kick", user, reason)
        except discord.Forbidden:
            await ctx.send("❌ I lack permission to kick this user")
        except discord.HTTPException as e:
            await ctx.send(f"❌ Failed to kick user: {e}")

    @slash(description="Ban a user from the server", guild_only=True)
    async def ban(self, ctx: Context, user: discord.User, reason: str = None, delete_days: int = 0) -> None:
        """Ban a user from the server."""
        if not ctx.user.guild_permissions.ban_members:
            await ctx.send("❌ You lack `ban_members` permission")
            return

        # Rate limit bans to 5 per hour per moderator
        allowed, msg = self.ban_limiter.check_limit(ctx.user.id, "ban", RateLimit(max_calls=5, window_minutes=60))
        if not allowed:
            await ctx.send(f"⏳ {msg}")
            return

        try:
            await ctx.guild.ban(user, reason=reason or "No reason provided", delete_message_days=delete_days)
            await ctx.send(f"✅ Banned {user.mention}")
            await self._log_moderation(ctx, "ban", user, reason)
        except discord.Forbidden:
            await ctx.send("❌ I lack permission to ban this user")
        except discord.HTTPException as e:
            await ctx.send(f"❌ Failed to ban user: {e}")

    @slash(description="Unban a previously banned user", guild_only=True)
    async def unban(self, ctx: Context, user: discord.User, reason: str = None) -> None:
        """Unban a user."""
        if not ctx.user.guild_permissions.ban_members:
            await ctx.send("❌ You lack `ban_members` permission")
            return

        try:
            await ctx.guild.unban(user, reason=reason or "No reason provided")
            await ctx.send(f"✅ Unbanned {user.mention}")
            await self._log_moderation(ctx, "unban", user, reason)
        except discord.NotFound:
            await ctx.send(f"❌ {user.mention} is not banned")
        except discord.Forbidden:
            await ctx.send("❌ I lack permission to unban users")
        except discord.HTTPException as e:
            await ctx.send(f"❌ Failed to unban user: {e}")

    @slash(description="Timeout a user (temporary mute)", guild_only=True)
    async def timeout(self, ctx: Context, user: discord.User, minutes: int, reason: str = None) -> None:
        """Timeout a user for specified minutes (1-40320 = up to 28 days)."""
        if not ctx.user.guild_permissions.moderate_members:
            await ctx.send("❌ You lack `moderate_members` permission")
            return

        minutes = max(1, min(40320, minutes))

        member = ctx.guild.get_member(user.id)
        if not member:
            await ctx.send(f"❌ {user.mention} is not in this server")
            return

        try:
            await member.timeout(discord.utils.utcnow() + discord.utils.timedelta(minutes=minutes), reason=reason)
            duration = f"{minutes} minutes"
            await ctx.send(f"✅ Timed out {user.mention} for {duration}")
            await self._log_moderation(ctx, "timeout", user, reason, duration)
        except discord.Forbidden:
            await ctx.send("❌ I lack permission to timeout this user")
        except discord.HTTPException as e:
            await ctx.send(f"❌ Failed to timeout user: {e}")

    @slash(description="Issue a formal warning to a user", guild_only=True)
    async def warn(self, ctx: Context, user: discord.User, reason: str = None) -> None:
        """Warn a user and track warnings."""
        if not ctx.user.guild_permissions.moderate_members:
            await ctx.send("❌ You lack `moderate_members` permission")
            return

        cfg = await self._get_config(ctx.guild.id)
        if not cfg.get("enable_warnings"):
            await ctx.send("⚠️ Warnings are disabled for this server")
            return

        # Rate limit warns to 10 per hour per moderator
        allowed, msg = self.warn_limiter.check_limit(ctx.user.id, "warn", RateLimit(max_calls=10, window_minutes=60))
        if not allowed:
            await ctx.send(f"⏳ {msg}")
            return

        # Load warnings for user
        cfg_obj = await self.config.store.load(ctx.guild.id)
        warnings = cfg_obj.get_other("warnings", {})
        user_id_str = str(user.id)

        if user_id_str not in warnings:
            warnings[user_id_str] = []

        warnings[user_id_str].append({
            "reason": reason or "No reason provided",
            "moderator": str(ctx.user.id),
        })

        cfg_obj.set_other("warnings", warnings)
        await self.config.store.save(cfg_obj)

        warn_count = len(warnings[user_id_str])
        auto_mute_threshold = cfg.get("auto_warn_threshold", 3)

        await ctx.send(f"⚠️ Warned {user.mention}. Warning #{warn_count}")
        await self._log_moderation(ctx, "warn", user, reason)

        # Auto-mute if threshold reached
        if warn_count >= auto_mute_threshold:
            mute_role = await self._get_or_create_mute_role(ctx.guild)
            member = ctx.guild.get_member(user.id)
            if mute_role and member:
                try:
                    await member.add_roles(mute_role, reason=f"Auto-muted after {warn_count} warnings")
                    await ctx.send(f"🔇 Auto-muted {user.mention} (warning threshold reached)")
                except discord.Forbidden:
                    logger.warning("Cannot add mute role to %s", user.id)

    @slash(description="View warnings for a user", guild_only=True)
    async def warnings(self, ctx: Context, user: discord.User) -> None:
        """Show warning history for a user."""
        cfg_obj = await self.config.store.load(ctx.guild.id)
        all_warnings = cfg_obj.get_other("warnings", {})
        user_warnings = all_warnings.get(str(user.id), [])

        if not user_warnings:
            await ctx.send(f"✅ {user.mention} has no warnings")
            return

        embed = discord.Embed(
            title=f"Warnings for {user.name}",
            description=f"Total: {len(user_warnings)}",
            color=discord.Color.orange(),
        )

        for i, warn in enumerate(user_warnings[-10:], 1):  # Show last 10
            embed.add_field(
                name=f"Warning #{len(user_warnings) - 10 + i}",
                value=warn.get("reason", "No reason"),
                inline=False,
            )

        await ctx.send_embed_from_dict(embed.to_dict())

    @slash(description="Add mute role to a user", guild_only=True)
    async def mute(self, ctx: Context, user: discord.User, reason: str = None) -> None:
        """Mute a user by adding mute role."""
        if not ctx.user.guild_permissions.manage_roles:
            await ctx.send("❌ You lack `manage_roles` permission")
            return

        member = ctx.guild.get_member(user.id)
        if not member:
            await ctx.send(f"❌ {user.mention} is not in this server")
            return

        mute_role = await self._get_or_create_mute_role(ctx.guild)
        if not mute_role:
            await ctx.send("❌ Cannot create or find mute role")
            return

        if mute_role in member.roles:
            await ctx.send(f"ℹ️ {user.mention} is already muted")
            return

        try:
            await member.add_roles(mute_role, reason=reason or "Muted by moderator")
            await ctx.send(f"🔇 Muted {user.mention}")
            await self._log_moderation(ctx, "mute", user, reason)
        except discord.Forbidden:
            await ctx.send("❌ I lack permission to manage roles")
        except discord.HTTPException as e:
            await ctx.send(f"❌ Failed to mute user: {e}")

    @slash(description="Remove mute role from a user", guild_only=True)
    async def unmute(self, ctx: Context, user: discord.User, reason: str = None) -> None:
        """Unmute a user by removing mute role."""
        if not ctx.user.guild_permissions.manage_roles:
            await ctx.send("❌ You lack `manage_roles` permission")
            return

        member = ctx.guild.get_member(user.id)
        if not member:
            await ctx.send(f"❌ {user.mention} is not in this server")
            return

        mute_role = discord.utils.get(ctx.guild.roles, name="Muted")
        if not mute_role or mute_role not in member.roles:
            await ctx.send(f"ℹ️ {user.mention} is not muted")
            return

        try:
            await member.remove_roles(mute_role, reason=reason or "Unmuted by moderator")
            await ctx.send(f"🔊 Unmuted {user.mention}")
            await self._log_moderation(ctx, "unmute", user, reason)
        except discord.Forbidden:
            await ctx.send("❌ I lack permission to manage roles")
        except discord.HTTPException as e:
            await ctx.send(f"❌ Failed to unmute user: {e}")

    @slash(description="View moderation settings", guild_only=True)
    async def mod_config(self, ctx: Context) -> None:
        """Show moderation configuration."""
        cfg = await self._get_config(ctx.guild.id)
        embed = discord.Embed(title="Moderation Config", color=discord.Color.blurple())
        embed.add_field(name="Warnings Enabled", value=str(cfg.get("enable_warnings")), inline=True)
        embed.add_field(name="Auto-Mute Threshold", value=f"{cfg.get('auto_warn_threshold')} warnings", inline=True)

        audit_channel_id = cfg.get("audit_channel")
        audit_channel = ctx.guild.get_channel(audit_channel_id) if audit_channel_id else None
        embed.add_field(
            name="Audit Channel",
            value=f"{audit_channel.mention}" if audit_channel else "Not set",
            inline=False,
        )

        await ctx.send_embed_from_dict(embed.to_dict())
