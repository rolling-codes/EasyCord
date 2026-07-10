"""Auto-respond to messages matching keywords or patterns."""
from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

import discord

from easycord import Plugin, on
from easycord.plugins._config_manager import PluginConfigManager

if TYPE_CHECKING:
    pass

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

    def __init__(self, *, store_path: str = ".easycord/auto-responder") -> None:
        super().__init__()
        self.config = PluginConfigManager(store_path)

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
        if not cfg.get("enabled", True):
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
        def _apply(cfg) -> None:
            section = cfg.get_other("auto_responder") or {}
            section.setdefault("triggers", {})[keyword] = response
            cfg.set_other("auto_responder", section)

        await self.config.store.mutate(guild_id, _apply)

    async def _add_regex_trigger(self, guild_id: int, pattern: str, response: str) -> None:
        """Add regex trigger (validate pattern first)."""
        try:
            re.compile(pattern)
        except re.error as e:
            raise ValueError(f"Invalid regex: {e}") from e

        def _apply(cfg) -> None:
            section = cfg.get_other("auto_responder") or {}
            section.setdefault("regex_triggers", {})[pattern] = response
            cfg.set_other("auto_responder", section)

        await self.config.store.mutate(guild_id, _apply)

    async def _remove_trigger(self, guild_id: int, keyword: str) -> bool:
        """Remove trigger. Return True if found."""
        def _apply(cfg) -> bool:
            section = cfg.get_other("auto_responder") or {}
            triggers = section.get("triggers", {})
            regex_triggers = section.get("regex_triggers", {})
            found = False
            if keyword in triggers:
                del triggers[keyword]
                found = True
            elif keyword in regex_triggers:
                del regex_triggers[keyword]
                found = True
            if found:
                cfg.set_other("auto_responder", section)
            return found

        return await self.config.store.mutate(guild_id, _apply)
