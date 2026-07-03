"""Auto-role plugin — assign roles automatically when members join."""
from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

import discord

from easycord import Plugin, on, slash
from easycord.server_config import ServerConfigStore

if TYPE_CHECKING:
    from easycord import Context

logger = logging.getLogger(__name__)


def _missing_roles(configured_ids: list[int], guild: discord.Guild) -> list[int]:
    """Return IDs from configured_ids that no longer exist in the guild."""
    existing = {r.id for r in guild.roles}
    return [rid for rid in configured_ids if rid not in existing]


class AutoRolePlugin(Plugin):
    """Automatically assign roles when new members join the server.

    Configure one or more roles to be auto-assigned, with an optional delay
    before assignment. Per-guild configuration persisted as JSON.

    Quick start::

        from easycord.plugins.auto_role import AutoRolePlugin
        bot.add_plugin(AutoRolePlugin())

    Commands registered::

        /autorole_add    — Add a role to the auto-assign list
        /autorole_remove — Remove a role from the auto-assign list
        /autorole_list   — Show currently configured auto-roles
        /autorole_delay  — Set delay in seconds before assigning roles
    """

    def __init__(self, *, store_path: str = ".easycord/auto_role") -> None:
        super().__init__()
        self._store = ServerConfigStore(store_path)
        self._locks: dict[int, asyncio.Lock] = {}

    def _guild_lock(self, guild_id: int) -> asyncio.Lock:
        if guild_id not in self._locks:
            self._locks[guild_id] = asyncio.Lock()
        return self._locks[guild_id]

    # ── Event handler ─────────────────────────────────────────

    @on("member_join")
    async def _on_member_join(self, member: discord.Member) -> None:
        if member.bot:
            return
        guild = member.guild
        cfg = await self._store.load(guild.id)
        data = cfg.get_other("auto_role", {})
        role_ids: list[int] = data.get("role_ids", [])
        delay: int = data.get("delay_seconds", 0)
        if not role_ids:
            return
        if delay > 0:
            await asyncio.sleep(delay)
        roles = [role for rid in role_ids if (role := guild.get_role(rid)) is not None]
        if roles:
            try:
                await member.add_roles(*roles, reason="AutoRolePlugin")
            except discord.Forbidden:
                logger.warning("Missing permission to assign roles in guild %s", guild.id)

    # ── Slash commands ────────────────────────────────────────

    @slash(description="Add a role to the auto-assign list for new members.", permissions=["manage_guild"])
    async def autorole_add(self, ctx: "Context", role: discord.Role) -> None:
        if ctx.guild is None:
            await ctx.respond("This command only works in a server.", ephemeral=True)
            return
        async with self._guild_lock(ctx.guild.id):
            cfg = await self._store.load(ctx.guild.id)
            data = cfg.get_other("auto_role", {})
            role_ids: list[int] = data.get("role_ids", [])
            if role.id not in role_ids:
                role_ids = [*role_ids, role.id]
            data = {**data, "role_ids": role_ids}
            cfg.set_other("auto_role", data)
            await self._store.save(cfg)
        await ctx.respond(f"{role.mention} will be assigned to new members.", ephemeral=True)

    @slash(description="Remove a role from the auto-assign list.", permissions=["manage_guild"])
    async def autorole_remove(self, ctx: "Context", role: discord.Role) -> None:
        if ctx.guild is None:
            await ctx.respond("This command only works in a server.", ephemeral=True)
            return
        async with self._guild_lock(ctx.guild.id):
            cfg = await self._store.load(ctx.guild.id)
            data = cfg.get_other("auto_role", {})
            role_ids: list[int] = data.get("role_ids", [])
            new_role_ids = [rid for rid in role_ids if rid != role.id]
            data = {**data, "role_ids": new_role_ids}
            cfg.set_other("auto_role", data)
            await self._store.save(cfg)
        await ctx.respond(f"{role.mention} removed from auto-assign list.", ephemeral=True)

    @slash(description="Show currently configured auto-roles.", permissions=["manage_guild"])
    async def autorole_list(self, ctx: "Context") -> None:
        if ctx.guild is None:
            await ctx.respond("This command only works in a server.", ephemeral=True)
            return
        cfg = await self._store.load(ctx.guild.id)
        data = cfg.get_other("auto_role", {})
        role_ids: list[int] = data.get("role_ids", [])
        delay: int = data.get("delay_seconds", 0)
        if not role_ids:
            await ctx.respond("No auto-roles configured.", ephemeral=True)
            return
        role_mentions = [f"<@&{rid}>" for rid in role_ids]
        role_list = "\n".join(f"• {m}" for m in role_mentions)
        await ctx.respond(
            f"**Auto-roles** (delay: {delay}s):\n{role_list}",
            ephemeral=True,
        )

    @slash(description="Set delay in seconds before assigning auto-roles (0 = immediate).", permissions=["manage_guild"])
    async def autorole_delay(self, ctx: "Context", seconds: int) -> None:
        if ctx.guild is None:
            await ctx.respond("This command only works in a server.", ephemeral=True)
            return
        if seconds < 0:
            await ctx.respond("Delay must be 0 or greater.", ephemeral=True)
            return
        async with self._guild_lock(ctx.guild.id):
            cfg = await self._store.load(ctx.guild.id)
            data = cfg.get_other("auto_role", {})
            data = {**data, "delay_seconds": seconds}
            cfg.set_other("auto_role", data)
            await self._store.save(cfg)
        await ctx.respond(f"Auto-role delay set to **{seconds}** seconds.", ephemeral=True)
