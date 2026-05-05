"""AI-powered moderation using Orchestrator for real-time message analysis."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Literal

import discord

from easycord import (
    ConversationMemory,
    Plugin,
    RateLimit,
    ToolLimiter,
    on,
    slash,
)
from easycord.plugins._config_manager import PluginConfigManager

if TYPE_CHECKING:
    from easycord import Context, Orchestrator

logger = logging.getLogger(__name__)

ModerationAction = Literal["delete", "warn", "timeout", "mute"]

_DEFAULTS = {
    "enabled": False,
    "action_level": "notify_only",
    "confidence_threshold": 0.85,
    "rules": ["spam", "abuse"],
    "warn_rate_limit": {"max_calls": 10, "window_minutes": 60},
    "timeout_rate_limit": {"max_calls": 5, "window_minutes": 60},
    "mod_review_channel": None,
    "audit_channel": None,
}


class AIModeratorPlugin(Plugin):
    """AI-powered server moderation using LLM analysis.

    Analyzes messages in real-time for spam, abuse, NSFW content using
    configured LLM provider. Supports auto-delete, warnings, timeouts.
    Per-guild config stored atomically via ServerConfigStore.

    Quick start::

        from easycord.plugins.ai_moderator import AIModeratorPlugin

        moderator = AIModeratorPlugin(orchestrator=my_orchestrator)
        bot.add_plugin(moderator)

    Configure via slash commands::

        /mod_enable         — Enable/disable moderation for server
        /mod_config         — View current config
        /mod_threshold      — Set confidence threshold (0.0-1.0)
        /mod_action_level   — Set action level (notify_only, warn, auto_delete)
        /mod_add_rule       — Add rule to check (spam, abuse, nsfw)
        /mod_remove_rule    — Remove rule
    """

    def __init__(self, orchestrator: Orchestrator | None = None):
        super().__init__()
        self.orchestrator = orchestrator
        self.config = PluginConfigManager(".easycord/moderation")
        self.conversation_memory = ConversationMemory()
        self.warn_limiter = ToolLimiter()
        self.timeout_limiter = ToolLimiter()

    async def on_load(self) -> None:
        """Initialize moderation plugin."""
        if not self.orchestrator:
            logger.warning("AIModeratorPlugin: No orchestrator provided, AI analysis disabled")
            return
        logger.info("AIModeratorPlugin loaded")

    async def _get_config(self, guild_id: int) -> dict:
        """Get moderation config for guild, creating defaults if needed."""
        return await self.config.get(guild_id, "moderation", _DEFAULTS)

    async def _update_config(self, guild_id: int, **kwargs) -> dict:
        """Update moderation config atomically."""
        return await self.config.update(guild_id, "moderation", **kwargs)

    async def _analyze_message(self, guild_id: int, message: discord.Message) -> tuple[ModerationAction | None, float, str]:
        """Analyze message using Orchestrator. Return (action, confidence, reason)."""
        if not self.orchestrator:
            return None, 0.0, "Orchestrator not configured"

        cfg = await self._get_config(guild_id)
        rules_text = ", ".join(cfg.get("rules", []))

        # Build analysis prompt
        prompt = (
            f"Analyze this Discord message for policy violations. Check for: {rules_text}.\n"
            f"Message: {message.content}\n"
            f"User: {message.author.name}\n"
            f"Reply with JSON: {{'action': 'delete|warn|timeout|none', 'confidence': 0.0-1.0, 'reason': 'brief reason'}}"
        )

        # Get conversation context for user
        messages = self.conversation_memory.get_messages(message.author.id, guild_id)
        messages.append({"role": "user", "content": prompt})

        try:
            from easycord import ContextBuilder, RunContext

            run_ctx = RunContext(
                messages=messages,
                ctx=None,  # No Discord context needed for analysis
                conversation_memory=self.conversation_memory,
            )
            result = await self.orchestrator.run(run_ctx)

            # Parse result JSON
            import json
            import re

            json_match = re.search(r"\{.*?\}", result.text, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                action = data.get("action", "none")
                confidence = float(data.get("confidence", 0.0))
                reason = data.get("reason", "No reason provided")

                # Clamp action to valid values
                if action not in ("delete", "warn", "timeout", "mute", "none"):
                    action = "none"

                return action if action != "none" else None, confidence, reason

        except Exception as e:
            logger.error("Failed to analyze message: %s", e, exc_info=True)

        return None, 0.0, "Analysis failed"

    async def _execute_action(
        self, ctx: Context, action: ModerationAction, user: discord.User, reason: str, message: discord.Message | None = None
    ) -> bool:
        """Execute moderation action. Return True if successful."""
        try:
            if action == "delete" and message:
                await message.delete()
                logger.info("Deleted message from %s: %s", user, reason)
                return True

            elif action == "warn":
                warn_limit = RateLimit(max_calls=10, window_minutes=60)
                allowed, msg = await self.warn_limiter.check_limit(user.id, "warn", warn_limit)
                if not allowed:
                    logger.warning("Warn rate limit exceeded for %s", user)
                    return False
                await ctx.send(f"⚠️ {user.mention} warned: {reason}")
                logger.info("Warned user %s: %s", user, reason)
                return True

            elif action == "timeout":
                timeout_limit = RateLimit(max_calls=5, window_minutes=60)
                allowed, msg = await self.timeout_limiter.check_limit(user.id, "timeout", timeout_limit)
                if not allowed:
                    logger.warning("Timeout rate limit exceeded for %s", user)
                    return False
                member = ctx.guild.get_member(user.id)
                if member:
                    await member.timeout(discord.utils.utcnow() + discord.utils.timedelta(minutes=5), reason=reason)
                    logger.info("Timed out user %s: %s", user, reason)
                    return True

            elif action == "mute":
                # Find or create mute role
                mute_role = discord.utils.get(ctx.guild.roles, name="Muted")
                if not mute_role:
                    try:
                        mute_role = await ctx.guild.create_role(name="Muted", reason="AIModeratorPlugin auto-created")
                    except discord.Forbidden:
                        logger.error("Cannot create mute role")
                        return False

                member = ctx.guild.get_member(user.id)
                if member and mute_role:
                    await member.add_roles(mute_role, reason=reason)
                    logger.info("Muted user %s: %s", user, reason)
                    return True

        except discord.Forbidden:
            logger.error("Permission denied executing action %s for %s", action, user)
        except Exception as e:
            logger.error("Failed to execute action %s: %s", action, e, exc_info=True)

        return False

    @on("message")
    async def _on_message(self, message: discord.Message) -> None:
        """Analyze and moderate messages."""
        if not message.guild or message.author.bot:
            return

        cfg = await self._get_config(message.guild.id)
        if not cfg.get("enabled"):
            return

        # Analyze message
        action, confidence, reason = await self._analyze_message(message.guild.id, message)

        threshold = cfg.get("confidence_threshold", 0.85)
        action_level = cfg.get("action_level", "notify_only")

        if action and confidence >= threshold:
            # Take action based on confidence
            if action_level == "auto_delete" and confidence >= 0.95:
                await message.delete()
                logger.info("Auto-deleted message from %s: %s (%.2f%%)", message.author, reason, confidence * 100)

            elif action_level == "warn" or action_level == "auto_delete":
                # Warn user
                try:
                    await message.author.send(f"⚠️ Your message was flagged: {reason} ({confidence*100:.0f}% confidence)")
                except discord.Forbidden:
                    pass

            elif action_level == "notify_only":
                # Log to review channel
                review_channel_id = cfg.get("mod_review_channel")
                if review_channel_id:
                    channel = message.guild.get_channel(review_channel_id)
                    if channel:
                        embed = discord.Embed(
                            title="Message Flagged",
                            description=f"User: {message.author.mention}\nMessage: {message.content[:500]}",
                            color=discord.Color.orange(),
                        )
                        embed.add_field(name="Action", value=action, inline=True)
                        embed.add_field(name="Confidence", value=f"{confidence*100:.1f}%", inline=True)
                        embed.add_field(name="Reason", value=reason, inline=False)
                        await channel.send(embed=embed)

    # ────────────────────────────────────────────────────────────
    # Slash commands for config
    # ────────────────────────────────────────────────────────────

    @slash(description="Enable or disable AI moderation", guild_only=True)
    async def mod_enable(self, ctx: Context, enabled: bool) -> None:
        """Enable/disable moderation."""
        await self._update_config(ctx.guild.id, enabled=enabled)
        status = "enabled" if enabled else "disabled"
        await ctx.send(f"✅ Moderation {status}")

    @slash(description="View moderation config", guild_only=True)
    async def mod_config(self, ctx: Context) -> None:
        """Show current moderation configuration."""
        cfg = await self._get_config(ctx.guild.id)
        embed = discord.Embed(title="Moderation Config", color=discord.Color.blurple())
        embed.add_field(name="Enabled", value=str(cfg.get("enabled")), inline=True)
        embed.add_field(name="Action Level", value=cfg.get("action_level", "unknown"), inline=True)
        embed.add_field(name="Confidence Threshold", value=f"{cfg.get('confidence_threshold', 0.85)*100:.0f}%", inline=True)
        embed.add_field(name="Rules", value=", ".join(cfg.get("rules", [])), inline=False)
        await ctx.send_embed_from_dict(embed.to_dict())

    @slash(description="Set confidence threshold (0.0-1.0)", guild_only=True)
    async def mod_threshold(self, ctx: Context, threshold: float) -> None:
        """Set confidence threshold."""
        threshold = max(0.0, min(1.0, threshold))
        await self._update_config(ctx.guild.id, confidence_threshold=threshold)
        await ctx.send(f"✅ Threshold set to {threshold*100:.0f}%")

    @slash(description="Set action level: notify_only, warn, auto_delete", guild_only=True)
    async def mod_action_level(self, ctx: Context, level: str) -> None:
        """Set action level."""
        if level not in ("notify_only", "warn", "auto_delete"):
            await ctx.send("❌ Invalid level. Use: notify_only, warn, auto_delete")
            return
        await self._update_config(ctx.guild.id, action_level=level)
        await ctx.send(f"✅ Action level set to {level}")

    @slash(description="Add rule to check: spam, abuse, nsfw", guild_only=True)
    async def mod_add_rule(self, ctx: Context, rule: str) -> None:
        """Add moderation rule."""
        if rule not in ("spam", "abuse", "nsfw"):
            await ctx.send("❌ Invalid rule. Use: spam, abuse, nsfw")
            return
        cfg = await self._get_config(ctx.guild.id)
        rules = cfg.get("rules", [])
        if rule not in rules:
            rules.append(rule)
            await self._update_config(ctx.guild.id, rules=rules)
        await ctx.send(f"✅ Added rule: {rule}")

    @slash(description="Remove rule", guild_only=True)
    async def mod_remove_rule(self, ctx: Context, rule: str) -> None:
        """Remove moderation rule."""
        cfg = await self._get_config(ctx.guild.id)
        rules = cfg.get("rules", [])
        if rule in rules:
            rules.remove(rule)
            await self._update_config(ctx.guild.id, rules=rules)
        await ctx.send(f"✅ Removed rule: {rule}")
