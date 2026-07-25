"""Recurring announcement plugin for bots."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

import discord

from easycord import Plugin, slash
from easycord.server_config import ServerConfigStore
from easycord.plugins.giveaway import _parse_duration
from ._shared import respond_error

if TYPE_CHECKING:
    from easycord import Context

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------

def _next_fire(now: datetime, interval_seconds: int) -> datetime:
    """Return now + interval as the initial fire time."""
    return now + timedelta(seconds=interval_seconds)


def _announcement_embed(ann: dict) -> discord.Embed:
    """Format a summary embed for an announcement entry."""
    embed = discord.Embed(
        title=f"Announcement #{ann['id']}",
        description=ann["message"],
        color=discord.Color.blurple(),
    )
    embed.add_field(
        name="Channel",
        value=f"<#{ann['channel_id']}>",
        inline=True,
    )
    embed.add_field(
        name="Interval",
        value=f"{ann['interval_seconds']}s",
        inline=True,
    )
    embed.add_field(
        name="Next fire",
        value=f"<t:{int(datetime.fromisoformat(ann['next_fire']).timestamp())}:R>",
        inline=True,
    )
    embed.add_field(
        name="Active",
        value="Yes" if ann.get("active", True) else "No",
        inline=True,
    )
    return embed


# ---------------------------------------------------------------------------
# Plugin
# ---------------------------------------------------------------------------

class ScheduledAnnouncementsPlugin(Plugin):
    """Post recurring messages into a channel on a configurable schedule.

    Quick start::

        from easycord.plugins.scheduled_announcements import ScheduledAnnouncementsPlugin
        bot.add_plugin(ScheduledAnnouncementsPlugin())

    Slash commands registered
    -------------------------
    ``/announcement_add``    — Schedule a recurring announcement.
    ``/announcement_list``   — List all scheduled announcements with IDs.
    ``/announcement_remove`` — Remove and cancel a scheduled announcement.
    """

    def __init__(self, *, store_path: str = ".easycord/announcements") -> None:
        super().__init__()
        self._store = ServerConfigStore(store_path)
        self._locks: dict[int, asyncio.Lock] = {}
        # guild_id -> ann_id -> task
        self._tasks: dict[int, dict[int, asyncio.Task]] = {}

    def _guild_lock(self, guild_id: int) -> asyncio.Lock:
        if guild_id not in self._locks:
            self._locks[guild_id] = asyncio.Lock()
        return self._locks[guild_id]

    # ------------------------------------------------------------------ #
    # Lifecycle                                                            #
    # ------------------------------------------------------------------ #

    async def on_ready(self) -> None:
        """Resume loops for all active announcements after a bot restart."""
        store_base = self._store._base
        if not store_base.exists():
            return
        for path in store_base.glob("*.json"):
            try:
                guild_id = int(path.stem)
            except ValueError:
                continue
            cfg = await self._store.load(guild_id)
            data = cfg.get_other("announcements", {})
            for ann in data.get("items", []):
                if ann.get("active", True):
                    self._start_task(guild_id, ann["id"])

    async def on_unload(self) -> None:
        """Cancel all in-flight announcement tasks."""
        for guild_tasks in self._tasks.values():
            for task in guild_tasks.values():
                task.cancel()
        self._tasks.clear()

    # ------------------------------------------------------------------ #
    # Task management                                                      #
    # ------------------------------------------------------------------ #

    def _start_task(self, guild_id: int, ann_id: int) -> None:
        task = asyncio.create_task(self._announcement_loop(guild_id, ann_id))
        self._tasks.setdefault(guild_id, {})[ann_id] = task

    def _cancel_task(self, guild_id: int, ann_id: int) -> None:
        task = self._tasks.get(guild_id, {}).pop(ann_id, None)
        if task:
            task.cancel()

    async def _announcement_loop(self, guild_id: int, ann_id: int) -> None:
        try:
            while True:
                # Load announcement and compute sleep time
                cfg = await self._store.load(guild_id)
                data = cfg.get_other("announcements", {})
                ann = next(
                    (a for a in data.get("items", []) if a["id"] == ann_id), None
                )
                if not ann or not ann.get("active", True):
                    return
                now = datetime.now(timezone.utc)
                next_fire = datetime.fromisoformat(ann["next_fire"])
                wait = max(0.0, (next_fire - now).total_seconds())
                await asyncio.sleep(wait)

                # Send the message
                guild = self.bot.get_guild(guild_id)
                if guild:
                    ch = guild.get_channel(ann["channel_id"])
                    if isinstance(ch, discord.TextChannel):
                        try:
                            await ch.send(ann["message"])
                        except (discord.Forbidden, discord.HTTPException) as e:
                            logger.warning("Announcement %d in guild %d failed to send: %s", ann_id, guild_id, e)

                # Advance next_fire
                async with self._guild_lock(guild_id):
                    cfg = await self._store.load(guild_id)
                    data = cfg.get_other("announcements", {})
                    for a in data.get("items", []):
                        if a["id"] == ann_id:
                            a["next_fire"] = (
                                datetime.fromisoformat(a["next_fire"])
                                + timedelta(seconds=a["interval_seconds"])
                            ).isoformat()
                    cfg.set_other("announcements", data)
                    await self._store.save(cfg)
        except asyncio.CancelledError:
            pass  # loop was cancelled (plugin unload); stop quietly

    # ------------------------------------------------------------------ #
    # Commands                                                             #
    # ------------------------------------------------------------------ #

    @slash(
        description="Schedule a recurring announcement in a channel.",
        guild_only=True,
    )
    async def announcement_add(
        self,
        ctx: "Context",
        channel: discord.TextChannel,
        interval: str,
        message: str,
    ) -> None:
        """Add a new recurring announcement.

        Parameters
        ----------
        channel:
            The channel to post the announcement in.
        interval:
            How often to post (e.g. ``30m``, ``2h``, ``1d``).
        message:
            The text content of the announcement.
        """
        if not getattr(ctx, "is_admin", False) and not (
            ctx.member and ctx.member.guild_permissions.manage_guild
        ):
            await ctx.respond(
                "You need the **Manage Guild** permission to add announcements.",
                ephemeral=True,
            )
            return

        try:
            interval_seconds = _parse_duration(interval)
        except ValueError as exc:
            await respond_error(ctx, str(exc))
            return

        if ctx.guild is None:
            return

        guild_id = ctx.guild.id
        now = datetime.now(timezone.utc)

        async with self._guild_lock(guild_id):
            cfg = await self._store.load(guild_id)
            data = cfg.get_other("announcements", {})
            next_id = data.get("next_id", 1)
            items: list[dict] = data.get("items", [])
            ann: dict = {
                "id": next_id,
                "channel_id": channel.id,
                "interval_seconds": interval_seconds,
                "message": message,
                "next_fire": _next_fire(now, interval_seconds).isoformat(),
                "active": True,
            }
            items.append(ann)
            data["next_id"] = next_id + 1
            data["items"] = items
            cfg.set_other("announcements", data)
            await self._store.save(cfg)

        self._start_task(guild_id, next_id)
        await ctx.respond(
            f"Announcement #{next_id} scheduled in {channel.mention} every `{interval}`.",
            ephemeral=True,
        )

    @slash(
        description="List all scheduled announcements.",
        guild_only=True,
    )
    async def announcement_list(self, ctx: "Context") -> None:
        """Show all recurring announcements for this guild."""
        if not getattr(ctx, "is_admin", False) and not (
            ctx.member and ctx.member.guild_permissions.manage_guild
        ):
            await ctx.respond(
                "You need the **Manage Guild** permission to view announcements.",
                ephemeral=True,
            )
            return

        if ctx.guild is None:
            return

        cfg = await self._store.load(ctx.guild.id)
        data = cfg.get_other("announcements", {})
        items: list[dict] = data.get("items", [])

        if not items:
            await respond_error(ctx, "No announcements scheduled.")
            return

        embeds = [_announcement_embed(ann) for ann in items]
        await ctx.respond(embeds=embeds, ephemeral=True)

    @slash(
        description="Remove a scheduled announcement by ID.",
        guild_only=True,
    )
    async def announcement_remove(self, ctx: "Context", id: int) -> None:
        """Cancel and delete a recurring announcement.

        Parameters
        ----------
        id:
            The numeric ID shown by ``/announcement_list``.
        """
        if not getattr(ctx, "is_admin", False) and not (
            ctx.member and ctx.member.guild_permissions.manage_guild
        ):
            await ctx.respond(
                "You need the **Manage Guild** permission to remove announcements.",
                ephemeral=True,
            )
            return

        if ctx.guild is None:
            return

        guild_id = ctx.guild.id

        async with self._guild_lock(guild_id):
            cfg = await self._store.load(guild_id)
            data = cfg.get_other("announcements", {})
            items: list[dict] = data.get("items", [])
            original_len = len(items)
            items = [a for a in items if a["id"] != id]
            if len(items) == original_len:
                await ctx.respond(
                    f"No announcement with ID {id} found.", ephemeral=True
                )
                return
            data["items"] = items
            cfg.set_other("announcements", data)
            await self._store.save(cfg)

        self._cancel_task(guild_id, id)
        await ctx.respond(
            f"Announcement #{id} removed.", ephemeral=True
        )
