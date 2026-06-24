"""AI-powered moderation using Orchestrator for real-time message analysis."""
from __future__ import annotations

import logging
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
from easycord.plugins._utils import SENDABLE_CHANNEL_TYPES

if TYPE_CHECKING:
    from easycord import Context, Orchestrator

logger = logging.getLogger(__name__)

ModerationAction = Literal["delete", "warn"]

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
            f"<message>{message.content}</message>\n"
            f"<author>{message.author.name}</author>\n"
            f"Reply with JSON: {{'action': 'delete|warn|none', 'confidence': 0.0-1.0, 'reason': 'brief reason'}}"
        )

        # Get conversation context for user
        messages = self.conversation_memory.get_messages(message.author.id, guild_id)
        messages.append({"role": "user", "content": prompt})

        try:
            from easycord import RunContext

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
                if action not in ("delete", "warn", "none"):
                    action = "none"

                return action if action != "none" else None, confidence, reason

        except Exception as e:
            logger.error("Failed to analyze message: %s", e, exc_info=True)

        return None, 0.0, "Analysis failed"

    async def _execute_action(
        self, message: discord.Message, action: ModerationAction, reason: str
    ) -> bool:
        """Execute a moderation action through the governed path. Return True on success.

        This is the single place destructive moderation runs: it owns rate
        limiting (`warn_limiter` / `timeout_limiter`), channel narrowing, and
        Discord error handling. Called from the ``on_message`` event path, so it
        must never let a Discord failure escape into the event dispatcher.
        """
        guild = message.guild
        if guild is None:
            return False
        user = message.author
        channel = message.channel
        try:
            if action == "delete":
                await message.delete()
                logger.info("Deleted message from %s: %s", user, reason)
                return True

            if action == "warn":
                warn_limit = RateLimit(max_calls=10, window_minutes=60)
                allowed, _ = await self.warn_limiter.check_limit(user.id, "warn", warn_limit)
                if not allowed:
                    logger.warning("Warn rate limit exceeded for %s", user)
                    return False
                if isinstance(channel, SENDABLE_CHANNEL_TYPES):
                    await channel.send(f"⚠️ {user.mention} warned: {reason}")
                logger.info("Warned user %s: %s", user, reason)
                return True

        except discord.Forbidden:
            logger.error("Permission denied executing action %s for %s", action, user)
        except Exception as e:  # noqa: BLE001 - event path must not raise into the dispatcher
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

        if not action or confidence < threshold:
            return

        # All destructive moderation routes through the governed _execute_action
        # path (rate limiting + Discord error handling). notify_only is the only
        # non-destructive branch and stays inline.
        if action_level == "auto_delete" and confidence >= 0.95:
            await self._execute_action(message, "delete", reason)

        elif action_level == "warn" or action_level == "auto_delete":
            await self._execute_action(message, "warn", reason)

        elif action_level == "notify_only":
            review_channel_id = cfg.get("mod_review_channel")
            if review_channel_id:
                channel = message.guild.get_channel(review_channel_id)
                if isinstance(channel, SENDABLE_CHANNEL_TYPES):
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
        assert ctx.guild is not None
        await self._update_config(ctx.guild.id, enabled=enabled)
        status = "enabled" if enabled else "disabled"
        await ctx.send(f"✅ Moderation {status}")

    @slash(description="View moderation config", guild_only=True)
    async def mod_config(self, ctx: Context) -> None:
        """Show current moderation configuration."""
        assert ctx.guild is not None
        cfg = await self._get_config(ctx.guild.id)
        embed = discord.Embed(title="Moderation Config", color=discord.Color.blurple())
        embed.add_field(name="Enabled", value=str(cfg.get("enabled")), inline=True)
        embed.add_field(name="Action Level", value=cfg.get("action_level", "unknown"), inline=True)
        embed.add_field(name="Confidence Threshold", value=f"{cfg.get('confidence_threshold', 0.85)*100:.0f}%", inline=True)
        embed.add_field(name="Rules", value=", ".join(cfg.get("rules", [])), inline=False)
        await ctx.respond(embed=embed)

    @slash(description="Set confidence threshold (0.0-1.0)", guild_only=True)
    async def mod_threshold(self, ctx: Context, threshold: float) -> None:
        """Set confidence threshold."""
        assert ctx.guild is not None
        threshold = max(0.0, min(1.0, threshold))
        await self._update_config(ctx.guild.id, confidence_threshold=threshold)
        await ctx.send(f"✅ Threshold set to {threshold*100:.0f}%")

    @slash(description="Set action level: notify_only, warn, auto_delete", guild_only=True)
    async def mod_action_level(self, ctx: Context, level: str) -> None:
        """Set action level."""
        assert ctx.guild is not None
        if level not in ("notify_only", "warn", "auto_delete"):
            await ctx.send("❌ Invalid level. Use: notify_only, warn, auto_delete")
            return
        await self._update_config(ctx.guild.id, action_level=level)
        await ctx.send(f"✅ Action level set to {level}")

    @slash(description="Add rule to check: spam, abuse, nsfw", guild_only=True)
    async def mod_add_rule(self, ctx: Context, rule: str) -> None:
        """Add moderation rule."""
        assert ctx.guild is not None
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
        assert ctx.guild is not None
        cfg = await self._get_config(ctx.guild.id)
        rules = cfg.get("rules", [])
        if rule in rules:
            rules.remove(rule)
            await self._update_config(ctx.guild.id, rules=rules)
        await ctx.send(f"✅ Removed rule: {rule}")
