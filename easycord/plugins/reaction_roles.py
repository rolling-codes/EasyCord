"""Reaction roles — auto-assign roles when users react with emoji."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord

from easycord import Plugin, on
from easycord.server_config import ServerConfigStore

if TYPE_CHECKING:
    from easycord import Context

logger = logging.getLogger(__name__)


class ReactionRolesPlugin(Plugin):
    """Auto-assign roles based on emoji reactions.

    Setup reaction role mappings via config commands. When users react to
    designated messages, they're automatically granted/revoked the mapped role.
    Per-guild and per-message configuration.

    Quick start::

        from easycord.plugins.reaction_roles import ReactionRolesPlugin

        bot.add_plugin(ReactionRolesPlugin())

    Then in Discord::

        /reaction_role_set <message_id> <emoji> <role>
        /reaction_role_list <message_id>
        /reaction_role_remove <message_id> <emoji>
    """

    def __init__(self):
        super().__init__()
        self.config_store = ServerConfigStore(".easycord/reaction-roles")

    async def on_load(self) -> None:
        """Initialize reaction roles plugin."""
        logger.info("ReactionRolesPlugin loaded")

    async def _get_mappings(self, guild_id: int, message_id: int) -> dict[str, int]:
        """Get emoji->role_id mappings for a message."""
        from easycord import ServerConfig

        cfg_obj = await self.config_store.load(guild_id)
        all_mappings = cfg_obj.get_other("reaction_roles", {})
        return all_mappings.get(str(message_id), {})

    async def _set_mapping(self, guild_id: int, message_id: int, emoji: str, role_id: int) -> None:
        """Add/update emoji->role mapping for a message."""
        from easycord import ServerConfig

        cfg_obj = await self.config_store.load(guild_id)
        all_mappings = cfg_obj.get_other("reaction_roles", {})

        if str(message_id) not in all_mappings:
            all_mappings[str(message_id)] = {}

        all_mappings[str(message_id)][emoji] = role_id
        cfg_obj.set_other("reaction_roles", all_mappings)
        await self.config_store.save(cfg_obj)

    async def _remove_mapping(self, guild_id: int, message_id: int, emoji: str) -> None:
        """Remove emoji->role mapping for a message."""
        from easycord import ServerConfig

        cfg_obj = await self.config_store.load(guild_id)
        all_mappings = cfg_obj.get_other("reaction_roles", {})

        if str(message_id) in all_mappings and emoji in all_mappings[str(message_id)]:
            del all_mappings[str(message_id)][emoji]
            cfg_obj.set_other("reaction_roles", all_mappings)
            await self.config_store.save(cfg_obj)

    @on("raw_reaction_add")
    async def _on_reaction_add(self, payload: discord.RawReactionActionEvent) -> None:
        """Handle member adding reaction."""
        if payload.guild_id is None or payload.user_id == self.bot.user.id:
            return

        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return

        mappings = await self._get_mappings(guild.id, payload.message_id)
        if not mappings:
            return

        emoji_str = str(payload.emoji)
        role_id = mappings.get(emoji_str)
        if not role_id:
            return

        member = guild.get_member(payload.user_id)
        if not member:
            return

        role = guild.get_role(role_id)
        if not role:
            logger.warning("Role %s not found in guild %s", role_id, guild.id)
            return

        try:
            await member.add_roles(role, reason="ReactionRolesPlugin")
            logger.info("Added role %s to %s via reaction %s", role.name, member, emoji_str)
        except discord.Forbidden:
            logger.error("No permission to add role %s to %s", role.name, member)
        except discord.HTTPException as e:
            logger.error("Failed to add role: %s", e)

    @on("raw_reaction_remove")
    async def _on_reaction_remove(self, payload: discord.RawReactionActionEvent) -> None:
        """Handle member removing reaction."""
        if payload.guild_id is None or payload.user_id == self.bot.user.id:
            return

        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return

        mappings = await self._get_mappings(guild.id, payload.message_id)
        if not mappings:
            return

        emoji_str = str(payload.emoji)
        role_id = mappings.get(emoji_str)
        if not role_id:
            return

        member = guild.get_member(payload.user_id)
        if not member:
            return

        role = guild.get_role(role_id)
        if not role:
            return

        try:
            await member.remove_roles(role, reason="ReactionRolesPlugin")
            logger.info("Removed role %s from %s via reaction %s", role.name, member, emoji_str)
        except discord.Forbidden:
            logger.error("No permission to remove role %s from %s", role.name, member)
        except discord.HTTPException as e:
            logger.error("Failed to remove role: %s", e)

    @on("raw_message_delete")
    async def _on_message_delete(self, payload: discord.RawMessageDeleteEvent) -> None:
        """Clean up mappings when message deleted."""
        if payload.guild_id is None:
            return

        from easycord import ServerConfig

        cfg_obj = await self.config_store.load(payload.guild_id)
        all_mappings = cfg_obj.get_other("reaction_roles", {})

        if str(payload.message_id) in all_mappings:
            del all_mappings[str(payload.message_id)]
            cfg_obj.set_other("reaction_roles", all_mappings)
            await self.config_store.save(cfg_obj)
            logger.info("Cleaned up reaction roles for deleted message %s", payload.message_id)

    @on("guild_role_delete")
    async def _on_role_delete(self, role: discord.Role) -> None:
        """Clean up deleted role from all mappings."""
        from easycord import ServerConfig

        cfg_obj = await self.config_store.load(role.guild.id)
        all_mappings = cfg_obj.get_other("reaction_roles", {})

        modified = False
        for message_id, mappings in list(all_mappings.items()):
            for emoji, role_id in list(mappings.items()):
                if role_id == role.id:
                    del mappings[emoji]
                    modified = True
            if not mappings:
                del all_mappings[message_id]

        if modified:
            cfg_obj.set_other("reaction_roles", all_mappings)
            await self.config_store.save(cfg_obj)
            logger.info("Cleaned up deleted role %s from reaction roles", role.name)
