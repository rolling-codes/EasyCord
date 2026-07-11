"""Role persistence — restore member roles after rejoin."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord

from easycord import Plugin, on
from easycord.plugins._config_manager import PluginConfigManager

if TYPE_CHECKING:
    pass

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
        # A stored section can exist without the "enabled" key (manual config
        # edit / partial update); absence must not read as disabled (B-020).
        if not cfg.get("enabled", True):
            return

        if member.bot:
            return

        # Record the member's role set. Exclude only @everyone and managed
        # (integration / booster) roles. Do NOT filter by the bot's current
        # hierarchy here — a role that is above the bot at leave time should
        # still be remembered; assignability is re-checked at restore time.
        roles = [r.id for r in member.roles if not r.is_default() and not r.managed]
        if not roles:
            return

        def _apply(cfg) -> None:
            saved_roles = cfg.get_other("saved_roles", {})
            saved_roles[str(member.id)] = roles
            cfg.set_other("saved_roles", saved_roles)

        await self.config.store.mutate(member.guild.id, _apply)
        logger.info("Saved %d roles for member %s in guild %s", len(roles), member.id, member.guild.id)

    @on("member_join")
    async def _on_member_join(self, member: discord.Member) -> None:
        """Restore member's previous roles on rejoin."""
        cfg = await self._get_config(member.guild.id)
        # Absence of "enabled" must not read as disabled (B-020).
        if not cfg.get("enabled", True):
            return

        if member.bot:
            return

        cfg_obj = await self.config.store.load(member.guild.id)
        role_ids = cfg_obj.get_other("saved_roles", {}).get(str(member.id))
        if not role_ids:
            return

        # Resolve saved IDs against the guild's current roles. Assignability is
        # checked here (at restore), not at save time, so a role that was above
        # the bot when the member left can still be restored once the bot's
        # position improves.
        resolved = [role for rid in role_ids if (role := member.guild.get_role(rid))]
        roles_to_add = [r for r in resolved if r.is_assignable()]

        restored_ok = False
        if roles_to_add:
            try:
                await member.add_roles(*roles_to_add, reason="RolePersistencePlugin: restoring roles")
                restored_ok = True
                logger.info("Restored %d roles for member %s in guild %s", len(roles_to_add), member.id, member.guild.id)
            except discord.Forbidden:
                logger.error("Cannot restore roles for member %s in guild %s", member.id, member.guild.id)
            except discord.HTTPException as e:
                logger.error("Failed to restore roles: %s", e)

        # Drop the saved record only when the restore actually succeeded, or when
        # none of the saved roles still exist in the guild (a stale entry that can
        # never be restored). A Forbidden/HTTP failure — or roles that exist but
        # aren't currently assignable — keep the record so a later rejoin retries.
        if restored_ok or not resolved:
            def _cleanup(cfg) -> None:
                saved_roles = cfg.get_other("saved_roles", {})
                saved_roles.pop(str(member.id), None)
                cfg.set_other("saved_roles", saved_roles)

            await self.config.store.mutate(member.guild.id, _cleanup)
