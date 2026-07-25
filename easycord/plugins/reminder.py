"""Per-user reminder plugin for bots."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

import discord

from easycord import Plugin, slash
from easycord.helpers.channel import SENDABLE_CHANNEL_TYPES
from easycord.server_config import ServerConfigStore
from ._shared import respond_error
from easycord.plugins.giveaway import _parse_duration  # noqa: F401 — re-exported for tests

if TYPE_CHECKING:
    from easycord import Context

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pure functions
# ---------------------------------------------------------------------------

def _reminder_embed(reminder: dict) -> discord.Embed:
    """Return a Discord embed for the reminder delivery message."""
    message = reminder.get("message", "")
    fire_at_str = reminder.get("fire_at", "")
    try:
        fire_dt = datetime.fromisoformat(fire_at_str)
        ts = int(fire_dt.timestamp())
        time_str = f"<t:{ts}:f>"
    except (ValueError, TypeError):
        time_str = "unknown time"

    embed = discord.Embed(
        title="⏰ Reminder",
        description=message,
        color=discord.Color.blurple(),
    )
    embed.set_footer(text=f"Reminder set for {time_str}")
    return embed


# ---------------------------------------------------------------------------
# Plugin
# ---------------------------------------------------------------------------

class ReminderPlugin(Plugin):
    """Set personal reminders that fire after a given duration.

    Members use ``/remind`` to schedule a reminder.  The reminder is saved to
    per-guild storage so it survives bot restarts.  On reconnect the bot
    re-schedules all pending reminders, firing immediately if overdue.

    Quick start::

        from easycord.plugins.reminder import ReminderPlugin
        bot.add_plugin(ReminderPlugin())

    Slash commands registered
    -------------------------
    ``/remind``           — Set a reminder (e.g. "30m", "2h").
    ``/reminders``        — List your pending reminders.
    ``/reminder_cancel``  — Cancel a pending reminder by its ID.
    """

    def __init__(self, *, store_path: str = ".easycord/reminder") -> None:
        super().__init__()
        self._store = ServerConfigStore(store_path)
        self._locks: dict[int, asyncio.Lock] = {}
        # guild_id -> reminder_id -> Task
        self._tasks: dict[int, dict[int, asyncio.Task]] = {}

    def _guild_lock(self, guild_id: int) -> asyncio.Lock:
        if guild_id not in self._locks:
            self._locks[guild_id] = asyncio.Lock()
        return self._locks[guild_id]

    # ── Lifecycle ─────────────────────────────────────────────

    async def on_ready(self) -> None:
        """Re-schedule all pending reminders from persistent storage."""
        store_base = self._store._base
        if not store_base.exists():
            return
        now = datetime.now(timezone.utc)
        for path in store_base.glob("*.json"):
            try:
                guild_id = int(path.stem)
            except ValueError:
                continue
            try:
                cfg = await self._store.load(guild_id)
                data: dict = cfg.get_other("reminders", {})
                for reminder in data.get("reminders", []):
                    if reminder.get("done"):
                        continue
                    reminder_id = reminder.get("id")
                    fire_at_str = reminder.get("fire_at")
                    if reminder_id is None or not fire_at_str:
                        continue
                    try:
                        fire_at = datetime.fromisoformat(fire_at_str)
                    except ValueError:
                        continue
                    remaining = (fire_at - now).total_seconds()
                    delay = max(remaining, 0.0)
                    self._schedule(guild_id, reminder_id, delay)
            except Exception:
                logger.exception("ReminderPlugin on_ready failed for guild %d", guild_id)

    async def on_unload(self) -> None:
        """Cancel all in-flight reminder tasks."""
        for guild_tasks in self._tasks.values():
            for task in guild_tasks.values():
                task.cancel()
        self._tasks.clear()

    # ── Task scheduling ───────────────────────────────────────

    def _schedule(
        self, guild_id: int, reminder_id: int, seconds: float
    ) -> asyncio.Task:
        task = asyncio.create_task(
            self._fire_after(guild_id, reminder_id, seconds)
        )
        self._tasks.setdefault(guild_id, {})[reminder_id] = task
        return task

    async def _fire_after(
        self, guild_id: int, reminder_id: int, seconds: float
    ) -> None:
        try:
            await asyncio.sleep(seconds)
            await self._deliver_reminder(guild_id, reminder_id)
        except asyncio.CancelledError:
            pass  # reminder was cancelled or plugin is unloading; nothing more to do
        except Exception:
            logger.exception(
                "ReminderPlugin _fire_after failed for reminder %d in guild %d",
                reminder_id,
                guild_id,
            )
        finally:
            self._tasks.get(guild_id, {}).pop(reminder_id, None)

    async def _deliver_reminder(self, guild_id: int, reminder_id: int) -> None:
        """Load reminder from store, send the message, mark it done."""
        async with self._guild_lock(guild_id):
            cfg = await self._store.load(guild_id)
            data: dict = cfg.get_other("reminders", {})
            reminders: list[dict] = data.get("reminders", [])

            target: dict | None = None
            for r in reminders:
                if r.get("id") == reminder_id:
                    target = r
                    break

            if target is None or target.get("done"):
                return

            target["done"] = True
            cfg.set_other("reminders", data)
            await self._store.save(cfg)

        # Deliver outside the lock
        channel_id: int | None = target.get("channel_id")
        user_id: int | None = target.get("user_id")

        if channel_id is None or user_id is None:
            return

        try:
            guild = self.bot.get_guild(guild_id)
        except RuntimeError:
            return
        if guild is None:
            return

        channel = guild.get_channel(channel_id)
        if not isinstance(channel, discord.TextChannel):
            return

        embed = _reminder_embed(target)
        try:
            await channel.send(content=f"<@{user_id}>", embed=embed)
        except discord.HTTPException:
            logger.exception(
                "Failed to deliver reminder %d in channel %d", reminder_id, channel_id
            )

    # ── Slash commands ────────────────────────────────────────

    @slash(description="Set a reminder. Use durations like 30m, 2h, 1d.", guild_only=True)
    async def remind(self, ctx: Context, when: str, message: str) -> None:
        if ctx.guild is None:
            return

        try:
            seconds = _parse_duration(when)
        except ValueError as exc:
            await respond_error(ctx, str(exc))
            return

        guild_id = ctx.guild.id
        user_id = ctx.user.id
        channel = ctx.channel
        if not isinstance(channel, SENDABLE_CHANNEL_TYPES):
            await respond_error(ctx, "This command must be used in a channel.")
            return
        channel_id: int = channel.id

        now = datetime.now(timezone.utc)
        fire_at = now + timedelta(seconds=seconds)

        async with self._guild_lock(guild_id):
            cfg = await self._store.load(guild_id)
            data: dict = cfg.get_other("reminders", {})
            next_id: int = data.get("next_id", 1)
            reminders: list[dict] = data.get("reminders", [])

            reminder: dict = {
                "id": next_id,
                "user_id": user_id,
                "channel_id": channel_id,
                "message": message,
                "fire_at": fire_at.isoformat(),
                "done": False,
            }
            reminders.append(reminder)
            data["next_id"] = next_id + 1
            data["reminders"] = reminders
            cfg.set_other("reminders", data)
            await self._store.save(cfg)

        self._schedule(guild_id, next_id, float(seconds))

        embed = discord.Embed(
            title="⏰ Reminder set!",
            description=message,
            color=discord.Color.green(),
        )
        embed.set_footer(text=f"ID: {next_id} · Fires in {when}")
        await ctx.respond(embed=embed, ephemeral=True)

    @slash(description="List your pending reminders.", guild_only=True)
    async def reminders(self, ctx: Context) -> None:
        if ctx.guild is None:
            return
        guild_id = ctx.guild.id
        user_id = ctx.user.id

        async with self._guild_lock(guild_id):
            cfg = await self._store.load(guild_id)
            data: dict = cfg.get_other("reminders", {})
            all_reminders: list[dict] = data.get("reminders", [])

        pending = [
            r for r in all_reminders
            if r.get("user_id") == user_id and not r.get("done")
        ]

        if not pending:
            await respond_error(ctx, "You have no pending reminders.")
            return

        lines: list[str] = []
        for r in pending:
            rid = r.get("id", "?")
            msg = r.get("message", "")
            fire_at_str = r.get("fire_at", "")
            try:
                fire_dt = datetime.fromisoformat(fire_at_str)
                ts = int(fire_dt.timestamp())
                time_str = f"<t:{ts}:R>"
            except (ValueError, TypeError):
                time_str = "unknown"
            lines.append(f"**#{rid}** — {msg} (fires {time_str})")

        embed = discord.Embed(
            title="⏰ Your Reminders",
            description="\n".join(lines),
            color=discord.Color.blurple(),
        )
        await ctx.respond(embed=embed, ephemeral=True)

    @slash(description="Cancel a pending reminder by its ID.", guild_only=True)
    async def reminder_cancel(self, ctx: Context, id: int) -> None:
        if ctx.guild is None:
            return
        guild_id = ctx.guild.id
        user_id = ctx.user.id

        async with self._guild_lock(guild_id):
            cfg = await self._store.load(guild_id)
            data: dict = cfg.get_other("reminders", {})
            reminders: list[dict] = data.get("reminders", [])

            target: dict | None = None
            for r in reminders:
                if r.get("id") == id and r.get("user_id") == user_id and not r.get("done"):
                    target = r
                    break

            if target is None:
                await respond_error(ctx, f"No pending reminder with ID {id} found.")
                return

            target["done"] = True
            cfg.set_other("reminders", data)
            await self._store.save(cfg)

        # Cancel the in-flight task if it exists
        task = self._tasks.get(guild_id, {}).pop(id, None)
        if task:
            task.cancel()

        await ctx.respond(f"Reminder #{id} cancelled.", ephemeral=True)
