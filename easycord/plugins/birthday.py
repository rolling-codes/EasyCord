"""Birthday announcement plugin for bots."""
from __future__ import annotations

import asyncio
import datetime
import logging
from typing import TYPE_CHECKING

import discord

from easycord import Plugin, slash
from easycord.server_config import ServerConfigStore

if TYPE_CHECKING:
    from easycord import Context

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pure functions
# ---------------------------------------------------------------------------

def _validate_date(month: int, day: int) -> bool:
    """Return True if month/day is a valid calendar date.

    Feb 29 is accepted as valid (leap-year special case).
    """
    if month < 1 or month > 12:
        return False
    if day < 1:
        return False
    # Days per month (non-leap year), Feb 29 is allowed specially.
    max_days = [0, 31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    return day <= max_days[month]


def _days_until(month: int, day: int, today: datetime.date) -> int:
    """Return days until the next occurrence of month/day from today (0 = today)."""
    this_year = today.year
    try:
        candidate = datetime.date(this_year, month, day)
    except ValueError:
        # Feb 29 in a non-leap year — push to next leap year
        candidate = datetime.date(this_year + 1, month, day)
        # Advance until we find a valid date
        for delta in range(4):
            try:
                candidate = datetime.date(this_year + delta, month, day)
                if candidate >= today:
                    return (candidate - today).days
            except ValueError:
                continue
        return (candidate - today).days

    if candidate < today:
        try:
            candidate = datetime.date(this_year + 1, month, day)
        except ValueError:
            # Next year is still not a leap year for Feb 29
            for delta in range(2, 6):
                try:
                    candidate = datetime.date(this_year + delta, month, day)
                    break
                except ValueError:
                    continue
    return (candidate - today).days


def _sort_upcoming(
    birthdays: dict, today: datetime.date
) -> list[tuple[int, int, int]]:
    """Return list of (user_id, month, day) sorted by days_until ascending."""
    result: list[tuple[int, int, int]] = []
    for user_id_str, info in birthdays.items():
        try:
            user_id = int(user_id_str)
        except (ValueError, TypeError):
            continue
        month = info.get("month")
        day = info.get("day")
        if month is None or day is None:
            continue
        result.append((user_id, month, day))
    result.sort(key=lambda t: _days_until(t[1], t[2], today))
    return result


# ---------------------------------------------------------------------------
# Plugin
# ---------------------------------------------------------------------------

class BirthdayPlugin(Plugin):
    """Announce member birthdays and optionally assign a birthday role.

    Members register their birthday with ``/birthday_set``.  A single
    background loop wakes at midnight UTC each day and posts announcements
    in the configured channel.

    Quick start::

        from easycord.plugins.birthday import BirthdayPlugin
        bot.add_plugin(BirthdayPlugin())

    Slash commands registered
    -------------------------
    ``/birthday_set``     — Register your birthday (month + day).
    ``/birthday_unset``   — Remove your birthday.
    ``/birthday_channel`` — Set the announcement channel (manage_guild).
    ``/birthday_role``    — Set a role assigned on birthday day (manage_guild).
    ``/birthday_list``    — Show upcoming birthdays this month.
    """

    def __init__(self, *, store_path: str = ".easycord/birthday") -> None:
        super().__init__()
        self._store = ServerConfigStore(store_path)
        self._locks: dict[int, asyncio.Lock] = {}
        self._loop_task: asyncio.Task | None = None

    def _guild_lock(self, guild_id: int) -> asyncio.Lock:
        if guild_id not in self._locks:
            self._locks[guild_id] = asyncio.Lock()
        return self._locks[guild_id]

    # ── Lifecycle ─────────────────────────────────────────────

    async def on_ready(self) -> None:
        """Start the single global daily-check loop (idempotent)."""
        if self._loop_task is None or self._loop_task.done():
            self._loop_task = asyncio.create_task(self._daily_check_loop())

    async def on_unload(self) -> None:
        """Cancel the daily-check loop."""
        if self._loop_task is not None:
            self._loop_task.cancel()
            self._loop_task = None

    # ── Background loop ───────────────────────────────────────

    @staticmethod
    def _seconds_until_midnight_utc() -> float:
        """Return seconds from now until the next UTC midnight."""
        now = datetime.datetime.now(datetime.timezone.utc)
        tomorrow = (now + datetime.timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        return (tomorrow - now).total_seconds()

    async def _daily_check_loop(self) -> None:
        """Wake at midnight UTC and fire birthday announcements."""
        try:
            while True:
                sleep_secs = self._seconds_until_midnight_utc()
                await asyncio.sleep(sleep_secs)
                await self._run_birthday_checks()
        except asyncio.CancelledError:
            pass

    async def _run_birthday_checks(self) -> None:
        """Check all guild configs and send birthday announcements for today."""
        store_base = self._store._base
        if not store_base.exists():
            return
        today = datetime.datetime.now(datetime.timezone.utc).date()
        for path in store_base.glob("*.json"):
            try:
                guild_id = int(path.stem)
            except ValueError:
                continue
            try:
                await self._check_guild_birthdays(guild_id, today)
            except Exception:
                logger.exception("Birthday check failed for guild %d", guild_id)

    async def _check_guild_birthdays(
        self, guild_id: int, today: datetime.date
    ) -> None:
        async with self._guild_lock(guild_id):
            cfg = await self._store.load(guild_id)
            data: dict = cfg.get_other("birthday", {})
            channel_id: int | None = data.get("channel_id")
            role_id: int | None = data.get("role_id")
            birthdays: dict = data.get("birthdays", {})
            role_assigned: dict = data.get("role_assigned", {})

            if not channel_id:
                return

            today_celebrants: list[int] = [
                int(uid)
                for uid, info in birthdays.items()
                if info.get("month") == today.month and info.get("day") == today.day
            ]
            if not today_celebrants:
                return

            # Mark role assignments so we know to remove them in 24h
            today_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
            for uid in today_celebrants:
                role_assigned[str(uid)] = today_iso
            data["role_assigned"] = role_assigned
            cfg.set_other("birthday", data)
            await self._store.save(cfg)

        # Fetch Discord objects outside the lock
        try:
            guild = self.bot.get_guild(guild_id)
        except RuntimeError:
            return
        if guild is None:
            return

        channel = guild.get_channel(channel_id)
        if not isinstance(channel, discord.TextChannel):
            return

        role = guild.get_role(role_id) if role_id else None

        for uid in today_celebrants:
            member = guild.get_member(uid)
            mention = f"<@{uid}>"

            embed = discord.Embed(
                title="🎂 Happy Birthday!",
                description=f"Today is {mention}'s birthday! Wish them well!",
                color=discord.Color.gold(),
            )
            embed.set_footer(text=f"🎉 {today.strftime('%B %d')}")
            try:
                await channel.send(embed=embed)
            except discord.HTTPException:
                logger.exception("Failed to send birthday message for user %d", uid)

            if role and member:
                try:
                    await member.add_roles(role, reason="BirthdayPlugin birthday role")
                    asyncio.create_task(
                        self._remove_role_after(guild_id, uid, role.id, 86400)
                    )
                except discord.HTTPException:
                    logger.exception("Failed to assign birthday role to %d", uid)

    async def _remove_role_after(
        self, guild_id: int, user_id: int, role_id: int, seconds: float
    ) -> None:
        """Remove birthday role from a member after *seconds*."""
        try:
            await asyncio.sleep(seconds)
            try:
                guild = self.bot.get_guild(guild_id)
            except RuntimeError:
                return
            if guild is None:
                return
            member = guild.get_member(user_id)
            if member is None:
                return
            role = guild.get_role(role_id)
            if role is None:
                return
            await member.remove_roles(role, reason="BirthdayPlugin birthday role expired")
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception(
                "Failed to remove birthday role from user %d in guild %d",
                user_id,
                guild_id,
            )

    # ── Slash commands ────────────────────────────────────────

    @slash(description="Register your birthday (month 1-12, day 1-31).", guild_only=True)
    async def birthday_set(
        self, ctx: Context, month: int, day: int
    ) -> None:
        if ctx.guild is None:
            return
        if not _validate_date(month, day):
            await ctx.respond(
                f"Invalid date: month={month}, day={day}. "
                "Month must be 1–12 and day must be valid for that month.",
                ephemeral=True,
            )
            return

        guild_id = ctx.guild.id
        user_id = ctx.user.id

        async with self._guild_lock(guild_id):
            cfg = await self._store.load(guild_id)
            data: dict = cfg.get_other("birthday", {})
            birthdays: dict = data.get("birthdays", {})
            birthdays[str(user_id)] = {"month": month, "day": day}
            data["birthdays"] = birthdays
            cfg.set_other("birthday", data)
            await self._store.save(cfg)

        await ctx.respond(
            f"Your birthday has been set to {month:02d}/{day:02d}!",
            ephemeral=True,
        )

    @slash(description="Remove your registered birthday.", guild_only=True)
    async def birthday_unset(self, ctx: Context) -> None:
        if ctx.guild is None:
            return
        guild_id = ctx.guild.id
        user_id = ctx.user.id

        async with self._guild_lock(guild_id):
            cfg = await self._store.load(guild_id)
            data: dict = cfg.get_other("birthday", {})
            birthdays: dict = data.get("birthdays", {})
            if str(user_id) not in birthdays:
                await ctx.respond("You don't have a birthday registered.", ephemeral=True)
                return
            birthdays.pop(str(user_id), None)
            data["birthdays"] = birthdays
            cfg.set_other("birthday", data)
            await self._store.save(cfg)

        await ctx.respond("Your birthday has been removed.", ephemeral=True)

    @slash(
        description="Set the channel for birthday announcements.",
        guild_only=True,
        permissions=["manage_guild"],
    )
    async def birthday_channel(
        self, ctx: Context, channel: discord.TextChannel
    ) -> None:
        if ctx.guild is None:
            return
        guild_id = ctx.guild.id

        async with self._guild_lock(guild_id):
            cfg = await self._store.load(guild_id)
            data: dict = cfg.get_other("birthday", {})
            data["channel_id"] = channel.id
            cfg.set_other("birthday", data)
            await self._store.save(cfg)

        await ctx.respond(
            f"Birthday announcements will be posted in {channel.mention}.",
            ephemeral=True,
        )

    @slash(
        description="Set the role assigned to members on their birthday (optional).",
        guild_only=True,
        permissions=["manage_guild"],
    )
    async def birthday_role(
        self, ctx: Context, role: discord.Role
    ) -> None:
        if ctx.guild is None:
            return
        guild_id = ctx.guild.id

        async with self._guild_lock(guild_id):
            cfg = await self._store.load(guild_id)
            data: dict = cfg.get_other("birthday", {})
            data["role_id"] = role.id
            cfg.set_other("birthday", data)
            await self._store.save(cfg)

        await ctx.respond(
            f"{role.mention} will be assigned to members on their birthday.",
            ephemeral=True,
        )

    @slash(description="List upcoming birthdays this month.", guild_only=True)
    async def birthday_list(self, ctx: Context) -> None:
        if ctx.guild is None:
            return
        guild_id = ctx.guild.id

        async with self._guild_lock(guild_id):
            cfg = await self._store.load(guild_id)
            data: dict = cfg.get_other("birthday", {})
            birthdays: dict = data.get("birthdays", {})

        today = datetime.datetime.now(datetime.timezone.utc).date()
        sorted_entries = _sort_upcoming(birthdays, today)

        if not sorted_entries:
            await ctx.respond("No birthdays have been registered yet.", ephemeral=True)
            return

        lines: list[str] = []
        for user_id, month, day in sorted_entries[:20]:
            days = _days_until(month, day, today)
            label = "today!" if days == 0 else f"in {days} day{'s' if days != 1 else ''}"
            lines.append(f"<@{user_id}> — {month:02d}/{day:02d} ({label})")

        embed = discord.Embed(
            title="🎂 Upcoming Birthdays",
            description="\n".join(lines),
            color=discord.Color.gold(),
        )
        await ctx.respond(embed=embed, ephemeral=True)
