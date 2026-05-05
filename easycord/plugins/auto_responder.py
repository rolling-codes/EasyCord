"""Auto-respond to messages matching keywords or patterns."""
from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

import discord

from easycord import Plugin, on
from easycord.plugins._config_manager import PluginConfigManager

if TYPE_CHECKING:
    from easycord import Context

logger = logging.getLogger(__name__)

_DEFAULTS = {
    "enabled": True,
    "triggers": {},
    "regex_triggers": {},
}


class AutoResponderPlugin(Plugin):
    """Trigger automatic responses on keywords or regex patterns.

    Setup keyword/pattern → response mappings. Bot auto-sends response
    when message matches. Per-guild config. Regex or literal string matching.

    Quick start::

        from easycord.plugins.auto_responder import AutoResponderPlugin

        bot.add_plugin(AutoResponderPlugin())

    Configure::

        /responder_add <keyword> <response>  — Add literal keyword trigger
        /responder_add_regex <pattern> <response>  — Add regex trigger
        /responder_list  — Show all triggers for guild
        /responder_remove <keyword>  — Remove trigger
    """

    def __init__(self):
        super().__init__()
        self.config = PluginConfigManager(".easycord/auto-responder")

    async def on_load(self) -> None:
        """Initialize auto-responder plugin."""
        logger.info("AutoResponderPlugin loaded")

    async def _get_config(self, guild_id: int) -> dict:
        """Get responder config for guild."""
        return await self.config.get(guild_id, "auto_responder", _DEFAULTS)

    async def _update_config(self, guild_id: int, **kwargs) -> dict:
        """Update responder config atomically."""
        return await self.config.update(guild_id, "auto_responder", **kwargs)

    @on("message")
    async def _on_message(self, message: discord.Message) -> None:
        """Check message for triggers and auto-respond."""
        if not message.guild or message.author.bot or not message.content:
            return

        cfg = await self._get_config(message.guild.id)
        if not cfg.get("enabled"):
            return

        content_lower = message.content.lower()

        # Check literal triggers (case-insensitive)
        for trigger, response in cfg.get("triggers", {}).items():
            if trigger.lower() in content_lower:
                try:
                    await message.reply(response, mention_author=False)
                except discord.Forbidden:
                    logger.warning("No permission to reply to message in %s", message.guild.id)
                except discord.HTTPException as e:
                    logger.error("Failed to send auto-response: %s", e)
                return  # Only respond once per message

        # Check regex triggers
        for pattern_str, response in cfg.get("regex_triggers", {}).items():
            try:
                pattern = re.compile(pattern_str, re.IGNORECASE)
                if pattern.search(content_lower):
                    await message.reply(response, mention_author=False)
                    return
            except re.error as e:
                logger.warning("Invalid regex pattern %s: %s", pattern_str, e)
                continue

    async def _add_trigger(self, guild_id: int, keyword: str, response: str) -> None:
        """Add literal keyword trigger."""
        from easycord import ServerConfig

        cfg = await self._get_config(guild_id)
        cfg["triggers"][keyword] = response
        await self._update_config(guild_id, triggers=cfg["triggers"])

    async def _add_regex_trigger(self, guild_id: int, pattern: str, response: str) -> None:
        """Add regex trigger (validate pattern first)."""
        try:
            re.compile(pattern)
        except re.error as e:
            raise ValueError(f"Invalid regex: {e}") from e

        from easycord import ServerConfig

        cfg = await self._get_config(guild_id)
        cfg["regex_triggers"][pattern] = response
        await self._update_config(guild_id, regex_triggers=cfg["regex_triggers"])

    async def _remove_trigger(self, guild_id: int, keyword: str) -> bool:
        """Remove trigger. Return True if found."""
        from easycord import ServerConfig

        cfg = await self._get_config(guild_id)
        triggers = cfg.get("triggers", {})
        regex_triggers = cfg.get("regex_triggers", {})

        found = False
        if keyword in triggers:
            del triggers[keyword]
            found = True
        elif keyword in regex_triggers:
            del regex_triggers[keyword]
            found = True

        if found:
            await self._update_config(guild_id, triggers=triggers, regex_triggers=regex_triggers)
        return found
