"""Server statistics display channels — auto-updating voice channel counters."""
from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

import discord

from easycord import Plugin, slash
from easycord.server_config import ServerConfigStore
from ._shared import GuildLockManager, respond_error

if TYPE_CHECKING:
    from easycord import Context

logger = logging.getLogger(__name__)

_UPDATE_INTERVAL = 600  # 10 minutes — Discord rate-limits channel edits


def _stat_name(label: str, value: int) -> str:
    """Format a stat channel name, e.g. '📊 Members: 1234'."""
    return f"{label}: {value}"


def _online_count(guild: discord.Guild) -> int:
    """Count non-bot members whose status is not offline."""
    return sum(
        1
        for m in guild.members
        if m.status != discord.Status.offline and not m.bot
    )


class ServerStatsPlugin(Plugin):
    """Display live server statistics as read-only voice channels.

    Running ``/stats_setup`` creates three voice channels that update every
    10 minutes with member count, online count, and boost count.
    ``/stats_teardown`` removes the channels and stops updates.

    Quick start::

        from easycord.plugins.server_stats import ServerStatsPlugin
        bot.add_plugin(ServerStatsPlugin())

    Slash commands registered
    -------------------------
    ``/stats_setup``    — Create stat channels and start auto-update (manage_guild).
    ``/stats_teardown`` — Delete stat channels and stop updates (manage_guild).
    """

    def __init__(self, *, store_path: str = ".easycord/server_stats") -> None:
        super().__init__()
        self._store = ServerConfigStore(store_path)
        self._locks = GuildLockManager()
        self._loops: dict[int, asyncio.Task] = {}

    def _start_loop(self, guild_id: int) -> None:
        """Start the background update loop for a guild (cancels any existing one)."""
        existing = self._loops.get(guild_id)
        if existing and not existing.done():
            existing.cancel()
        task = asyncio.create_task(self._update_loop(guild_id))
        self._loops[guild_id] = task

    async def on_ready(self) -> None:
        """Restart update loops for all guilds that have stats configured."""
        store_base = self._store._base
        if not store_base.exists():
            return
        for path in store_base.glob("*.json"):
            try:
                guild_id = int(path.stem)
            except ValueError:
                continue
            cfg = await self._store.load(guild_id)
            data: dict = cfg.get_other("server_stats", {})
            if data.get("member_channel_id"):
                self._start_loop(guild_id)

    async def on_unload(self) -> None:
        """Cancel all background stat update tasks."""
        for task in self._loops.values():
            task.cancel()
        self._loops.clear()

    async def _update_loop(self, guild_id: int) -> None:
        """Background loop: refresh stat channels every 10 minutes."""
        try:
            while True:
                await self._refresh_stats(guild_id)
                await asyncio.sleep(_UPDATE_INTERVAL)
        except asyncio.CancelledError:
            pass  # loop was cancelled (plugin unload or guild teardown); stop quietly

    async def _refresh_stats(self, guild_id: int) -> None:
        """Fetch current stats and update the channel names."""
        guild = self.bot.get_guild(guild_id)
        if guild is None:
            return

        cfg = await self._store.load(guild_id)
        data: dict = cfg.get_other("server_stats", {})

        member_ch = guild.get_channel(data.get("member_channel_id", 0))
        online_ch = guild.get_channel(data.get("online_channel_id", 0))
        boost_ch = guild.get_channel(data.get("boost_channel_id", 0))

        count = guild.member_count or 0
        online = _online_count(guild)
        boosts = guild.premium_subscription_count or 0

        try:
            if member_ch:
                await member_ch.edit(name=_stat_name("📊 Members", count))
            if online_ch:
                await online_ch.edit(name=_stat_name("🟢 Online", online))
            if boost_ch:
                await boost_ch.edit(name=_stat_name("💎 Boosts", boosts))
        except discord.Forbidden:
            logger.error("Missing permission to edit stat channels in guild %s", guild_id)
        except discord.HTTPException as exc:
            logger.error("Failed to update stat channels in guild %s: %s", guild_id, exc)

    @slash(description="Create stat display channels and start auto-update.", guild_only=True, require_admin=True)
    async def stats_setup(self, ctx: Context) -> None:
        """Create three voice channels showing member count, online count, and boosts."""
        if ctx.guild is None:
            await respond_error(ctx, "This command can only be used in a server.")
            return

        guild = ctx.guild
        guild_id = guild.id

        try:
            member_ch = await guild.create_voice_channel(
                name=_stat_name("📊 Members", guild.member_count or 0),
                reason="ServerStatsPlugin setup",
            )
            online_ch = await guild.create_voice_channel(
                name=_stat_name("🟢 Online", _online_count(guild)),
                reason="ServerStatsPlugin setup",
            )
            boost_ch = await guild.create_voice_channel(
                name=_stat_name("💎 Boosts", guild.premium_subscription_count or 0),
                reason="ServerStatsPlugin setup",
            )
        except discord.Forbidden:
            await ctx.respond(
                "Bot lacks permission to create voice channels.", ephemeral=True
            )
            return
        except discord.HTTPException as exc:
            await respond_error(ctx, f"Failed to create stat channels: {exc}")
            return

        async with self._locks.lock(guild_id):
            cfg = await self._store.load(guild_id)
            cfg.set_other(
                "server_stats",
                {
                    "member_channel_id": member_ch.id,
                    "online_channel_id": online_ch.id,
                    "boost_channel_id": boost_ch.id,
                },
            )
            await self._store.save(cfg)

        self._start_loop(guild_id)
        await ctx.respond("✅ Stat channels created and update loop started.", ephemeral=True)

    @slash(description="Delete stat display channels and stop auto-update.", guild_only=True, require_admin=True)
    async def stats_teardown(self, ctx: Context) -> None:
        """Remove all three stat channels and cancel the background update loop."""
        if ctx.guild is None:
            await respond_error(ctx, "This command can only be used in a server.")
            return

        guild = ctx.guild
        guild_id = guild.id

        cfg = await self._store.load(guild_id)
        data: dict = cfg.get_other("server_stats", {})

        if not data:
            await ctx.respond(
                "Server stats are not configured. Run `/stats_setup` first.", ephemeral=True
            )
            return

        # Cancel update loop
        task = self._loops.pop(guild_id, None)
        if task:
            task.cancel()

        # Delete stat channels
        for key in ("member_channel_id", "online_channel_id", "boost_channel_id"):
            ch_id = data.get(key, 0)
            if not ch_id:
                continue
            channel = guild.get_channel(ch_id)
            if channel is None:
                continue
            try:
                await channel.delete(reason="ServerStatsPlugin teardown")
            except discord.Forbidden:
                logger.warning("No permission to delete stat channel %s in guild %s", ch_id, guild_id)
            except discord.HTTPException as exc:
                logger.warning("Failed to delete stat channel %s: %s", ch_id, exc)

        # Remove config
        async with self._locks.lock(guild_id):
            cfg = await self._store.load(guild_id)
            cfg.remove_other("server_stats")
            await self._store.save(cfg)

        await ctx.respond("✅ Stat channels removed and update loop stopped.", ephemeral=True)
