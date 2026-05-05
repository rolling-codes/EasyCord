"""Role persistence — restore member roles after rejoin."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord

from easycord import Plugin, on
from easycord.plugins._config_manager import PluginConfigManager

if TYPE_CHECKING:
    from easycord import Context

logger = logging.getLogger(__name__)

_DEFAULTS = {
    "enabled": True,
}


class RolePersistencePlugin(Plugin):
    """Remember member roles and restore them if they rejoin.

    When a member leaves, their roles are saved. If they rejoin,
    their roles are automatically restored.

    Quick start::

        from easycord.plugins.role_persistence import RolePersistencePlugin

        bot.add_plugin(RolePersistencePlugin())

    No commands — automatic on member join/leave.
    """

    def __init__(self):
        super().__init__()
        self.config = PluginConfigManager(".easycord/role-persistence")

    async def on_load(self) -> None:
        """Initialize role persistence plugin."""
        logger.info("RolePersistencePlugin loaded")

    async def _get_config(self, guild_id: int) -> dict:
        """Get config for guild."""
        return await self.config.get(guild_id, "role_persistence", _DEFAULTS)

    @on("member_remove")
    async def _on_member_remove(self, member: discord.Member) -> None:
        """Save member's roles when they leave."""
        cfg = await self._get_config(member.guild.id)
        if not cfg.get("enabled"):
            return

        if member.bot:
            return

        # Get managed/assignable roles (skip @everyone, @here, @bot roles)
        roles = [r.id for r in member.roles if r.is_assignable() and not r.managed]

        if roles:
            cfg_obj = await self.config.store.load(member.guild.id)
            saved_roles = cfg_obj.get_other("saved_roles", {})
            saved_roles[str(member.id)] = roles
            cfg_obj.set_other("saved_roles", saved_roles)
            await self.config.store.save(cfg_obj)
            logger.info("Saved %d roles for member %s in guild %s", len(roles), member.id, member.guild.id)

    @on("member_join")
    async def _on_member_join(self, member: discord.Member) -> None:
        """Restore member's previous roles on rejoin."""
        cfg = await self._get_config(member.guild.id)
        if not cfg.get("enabled"):
            return

        if member.bot:
            return

        cfg_obj = await self.config.store.load(member.guild.id)
        saved_roles = cfg_obj.get_other("saved_roles", {})
        role_ids = saved_roles.get(str(member.id), [])

        if not role_ids:
            return

        roles_to_add = []
        for role_id in role_ids:
            role = member.guild.get_role(role_id)
            if role:
                roles_to_add.append(role)

        if roles_to_add:
            try:
                await member.add_roles(*roles_to_add, reason="RolePersistencePlugin: restoring roles")
                logger.info("Restored %d roles for member %s in guild %s", len(roles_to_add), member.id, member.guild.id)
            except discord.Forbidden:
                logger.error("Cannot restore roles for member %s in guild %s", member.id, member.guild.id)
            except discord.HTTPException as e:
                logger.error("Failed to restore roles: %s", e)

            # Clean up saved roles
            del saved_roles[str(member.id)]
            cfg_obj.set_other("saved_roles", saved_roles)
            await self.config.store.save(cfg_obj)
