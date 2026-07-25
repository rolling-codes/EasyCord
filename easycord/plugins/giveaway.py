"""Button-based giveaway plugin for bots."""
from __future__ import annotations

import asyncio
import logging
import random
import re
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

import discord

from easycord import Plugin, slash
from easycord.helpers.channel import SENDABLE_CHANNEL_TYPES, send_safe
from easycord.server_config import ServerConfigStore
from ._shared import GuildLockManager, respond_error

if TYPE_CHECKING:
    from easycord import Context

logger = logging.getLogger(__name__)

_DURATION_RE = re.compile(r"^(\d+)(s|m|h|d)$", re.IGNORECASE)
_UNIT_SECONDS: dict[str, int] = {"s": 1, "m": 60, "h": 3600, "d": 86400}


def _parse_duration(value: str) -> int:
    """Parse a duration string like '30m', '2h', '1d' into seconds."""
    m = _DURATION_RE.match(value.strip())
    if not m:
        raise ValueError(
            f"Invalid duration {value!r}. Use a number followed by s, m, h, or d "
            "(e.g. '30m', '2h', '1d')."
        )
    return int(m.group(1)) * _UNIT_SECONDS[m.group(2).lower()]


def _pick_winners(entries: list[int], count: int) -> list[int]:
    """Return up to *count* unique winners sampled randomly from *entries*."""
    if not entries:
        return []
    return random.sample(entries, min(count, len(entries)))


def _build_embed(
    prize: str,
    end_ts: int,
    winner_count: int,
    entry_count: int,
    *,
    ended: bool = False,
) -> discord.Embed:
    color = discord.Color.greyple() if ended else discord.Color.gold()
    status_label = "Ended" if ended else "Ends"
    embed = discord.Embed(
        title="🎉 GIVEAWAY 🎉",
        description=(
            f"**Prize:** {prize}\n"
            f"**{status_label}:** <t:{end_ts}:R>\n"
            f"**Winners:** {winner_count}\n"
            f"**Entries:** {entry_count}"
        ),
        color=color,
    )
    if not ended:
        embed.set_footer(text="Click the button below to enter!")
    return embed


class _GiveawayView(discord.ui.View):
    """Persistent enter/leave toggle button for an active giveaway."""

    def __init__(
        self, plugin: GiveawayPlugin, guild_id: int, message_id: int
    ) -> None:
        super().__init__(timeout=None)
        self._plugin = plugin
        self._guild_id = guild_id
        self._message_id = message_id

        btn = discord.ui.Button(
            label="🎉 Enter",
            style=discord.ButtonStyle.green,
            custom_id=f"giveaway:enter:{message_id}",
        )
        btn.callback = self._toggle
        self.add_item(btn)

    async def _toggle(self, interaction: discord.Interaction) -> None:
        user_id = interaction.user.id
        async with self._plugin._locks.lock(self._guild_id):
            cfg = await self._plugin._store.load(self._guild_id)
            giveaways: dict = cfg.get_other("giveaways", {})
            data: dict | None = giveaways.get(str(self._message_id))
            if not data or data.get("status") != "active":
                await interaction.response.send_message(
                    "This giveaway has already ended.", ephemeral=True
                )
                return

            entries: list[int] = data.get("entries", [])
            if user_id in entries:
                entries.remove(user_id)
                verb = "left"
            else:
                entries.append(user_id)
                verb = "entered"
            data["entries"] = entries
            giveaways[str(self._message_id)] = data
            cfg.set_other("giveaways", giveaways)
            await self._plugin._store.save(cfg)

        end_ts = int(datetime.fromisoformat(data["end_time"]).timestamp())
        embed = _build_embed(
            data["prize"], end_ts, data["winner_count"], len(entries)
        )
        await interaction.response.edit_message(embed=embed, view=self)
        await interaction.followup.send(
            f"You have {verb} the giveaway!", ephemeral=True
        )


class GiveawayPlugin(Plugin):
    """Run timed giveaways with a persistent entry button.

    Members click a button to enter or leave. When the timer expires (or an
    admin force-ends the giveaway) the bot picks random winners and announces
    them. Active giveaways resume automatically if the bot restarts.

    Quick start::

        from easycord.plugins.giveaway import GiveawayPlugin
        bot.add_plugin(GiveawayPlugin())

    Slash commands registered
    -------------------------
    ``/giveaway``        — Start a giveaway in the current channel.
    ``/giveaway_end``    — Force-end a giveaway early by message ID.
    ``/giveaway_reroll`` — Re-pick winners from the same entry pool.
    """

    def __init__(self, *, store_path: str = ".easycord/giveaway") -> None:
        super().__init__()
        self._store = ServerConfigStore(store_path)
        self._locks = GuildLockManager()
        self._timers: dict[int, dict[int, asyncio.Task]] = {}

    async def on_ready(self) -> None:
        """Re-register entry views and resume timers for all active giveaways."""
        store_base = self._store._base
        if not store_base.exists():
            return
        now = datetime.now(timezone.utc)
        for path in store_base.glob("*.json"):
            try:
                guild_id = int(path.stem)
            except ValueError:
                continue
            cfg = await self._store.load(guild_id)
            giveaways: dict = cfg.get_other("giveaways", {})
            for msg_id_str, data in list(giveaways.items()):
                if data.get("status") != "active":
                    continue
                msg_id = int(msg_id_str)
                end_time = datetime.fromisoformat(data["end_time"])
                view = _GiveawayView(self, guild_id, msg_id)
                try:
                    self.bot.add_view(view, message_id=msg_id)
                except Exception:
                    pass  # entry message may have been deleted; the giveaway timer still resumes
                remaining = (end_time - now).total_seconds()
                if remaining > 0:
                    self._schedule_timer(guild_id, msg_id, remaining)
                else:
                    asyncio.create_task(self._end_giveaway(guild_id, msg_id))

    async def on_unload(self) -> None:
        """Cancel all in-flight giveaway timers."""
        for guild_timers in self._timers.values():
            for task in guild_timers.values():
                task.cancel()
        self._timers.clear()

    def _schedule_timer(
        self, guild_id: int, message_id: int, seconds: float
    ) -> None:
        task = asyncio.create_task(
            self._giveaway_timer(guild_id, message_id, seconds)
        )
        self._timers.setdefault(guild_id, {})[message_id] = task

    async def _giveaway_timer(
        self, guild_id: int, message_id: int, seconds: float
    ) -> None:
        try:
            await asyncio.sleep(seconds)
            await self._end_giveaway(guild_id, message_id)
        except asyncio.CancelledError:
            pass  # timer was cancelled (force-ended or plugin unload); nothing more to do

    async def _end_giveaway(self, guild_id: int, message_id: int) -> None:
        """Pick winners, update the embed, and post the announcement."""
        async with self._locks.lock(guild_id):
            cfg = await self._store.load(guild_id)
            giveaways: dict = cfg.get_other("giveaways", {})
            data: dict | None = giveaways.get(str(message_id))
            if not data or data.get("status") != "active":
                return
            entries: list[int] = data.get("entries", [])
            winners = _pick_winners(entries, data["winner_count"])
            data["status"] = "ended"
            data["winners"] = winners
            giveaways[str(message_id)] = data
            cfg.set_other("giveaways", giveaways)
            await self._store.save(cfg)

        guild = self.bot.get_guild(guild_id)
        if guild is None:
            return
        channel = guild.get_channel(data["channel_id"])
        if not isinstance(channel, discord.TextChannel):
            return
        try:
            message = await channel.fetch_message(message_id)
        except discord.NotFound:
            return

        end_ts = int(datetime.fromisoformat(data["end_time"]).timestamp())
        ended_embed = _build_embed(
            data["prize"], end_ts, data["winner_count"], len(entries), ended=True
        )

        closed_view = discord.ui.View()
        closed_btn = discord.ui.Button(
            label="🎉 Giveaway Ended",
            style=discord.ButtonStyle.grey,
            disabled=True,
            custom_id=f"giveaway:closed:{message_id}",
        )
        closed_view.add_item(closed_btn)

        try:
            await message.edit(embed=ended_embed, view=closed_view)
        except discord.HTTPException:
            pass  # message may have been deleted

        if winners:
            mentions = " ".join(f"<@{w}>" for w in winners)
            await send_safe(
                channel,
                log=logger,
                what="giveaway winner announcement",
                content=f"🎉 Congratulations {mentions}! You won **{data['prize']}**!",
            )
        else:
            await send_safe(
                channel,
                log=logger,
                what="giveaway winner announcement",
                content=f"🎉 Giveaway for **{data['prize']}** has ended — no entries were submitted.",
            )

        self._timers.get(guild_id, {}).pop(message_id, None)

    @slash(description="Start a giveaway in the current channel.", guild_only=True, bot_permissions=["send_messages"])
    async def giveaway(
        self,
        ctx: Context,
        prize: str,
        duration: str,
        winners: int = 1,
    ) -> None:
        """Start a new giveaway.

        Parameters
        ----------
        prize:
            What you're giving away (e.g. "Nitro", "Steam key").
        duration:
            How long the giveaway runs (e.g. "30m", "2h", "1d").
        winners:
            Number of winners to pick when it ends (default 1).
        """
        try:
            seconds = _parse_duration(duration)
        except ValueError as exc:
            await respond_error(ctx, str(exc))
            return
        if winners < 1:
            await respond_error(ctx, "Winner count must be at least 1.")
            return
        if ctx.guild is None:
            return

        end_dt = datetime.now(timezone.utc) + timedelta(seconds=seconds)
        end_ts = int(end_dt.timestamp())
        embed = _build_embed(prize, end_ts, winners, 0)

        await ctx.respond(embed=embed)
        message = await ctx.interaction.original_response()
        message_id = message.id
        guild_id = ctx.guild.id
        channel = ctx.channel
        if not isinstance(channel, SENDABLE_CHANNEL_TYPES):
            await respond_error(ctx, "This command must be used in a channel.")
            return
        channel_id: int = channel.id

        async with self._locks.lock(guild_id):
            cfg = await self._store.load(guild_id)
            giveaways: dict = cfg.get_other("giveaways", {})
            giveaways[str(message_id)] = {
                "channel_id": channel_id,
                "prize": prize,
                "end_time": end_dt.isoformat(),
                "winner_count": winners,
                "entries": [],
                "status": "active",
                "winners": [],
            }
            cfg.set_other("giveaways", giveaways)
            await self._store.save(cfg)

        view = _GiveawayView(self, guild_id, message_id)
        self.bot.add_view(view, message_id=message_id)
        await message.edit(embed=embed, view=view)
        self._schedule_timer(guild_id, message_id, float(seconds))

    @slash(description="Force-end a giveaway early and pick winners.", guild_only=True)
    async def giveaway_end(self, ctx: Context, message_id: str) -> None:
        """End an active giveaway before its timer expires."""
        try:
            msg_id = int(message_id)
        except ValueError:
            await ctx.respond(
                "Provide the message ID of the giveaway to end.", ephemeral=True
            )
            return
        if ctx.guild is None:
            return

        guild_id = ctx.guild.id
        async with self._locks.lock(guild_id):
            cfg = await self._store.load(guild_id)
            giveaways: dict = cfg.get_other("giveaways", {})
            if giveaways.get(str(msg_id), {}).get("status") != "active":
                await ctx.respond(
                    "No active giveaway found with that message ID.", ephemeral=True
                )
                return

        task = self._timers.get(guild_id, {}).pop(msg_id, None)
        if task:
            task.cancel()

        await ctx.respond("Ending the giveaway now…", ephemeral=True)
        await self._end_giveaway(guild_id, msg_id)

    @slash(description="Re-pick winners for an ended giveaway.", guild_only=True)
    async def giveaway_reroll(self, ctx: Context, message_id: str) -> None:
        """Pick new winners from the same entry pool as an ended giveaway."""
        try:
            msg_id = int(message_id)
        except ValueError:
            await ctx.respond(
                "Provide the message ID of the ended giveaway.", ephemeral=True
            )
            return
        if ctx.guild is None:
            return

        guild_id = ctx.guild.id
        async with self._locks.lock(guild_id):
            cfg = await self._store.load(guild_id)
            giveaways: dict = cfg.get_other("giveaways", {})
            data: dict | None = giveaways.get(str(msg_id))
            if not data or data.get("status") != "ended":
                await ctx.respond(
                    "No ended giveaway found with that message ID.", ephemeral=True
                )
                return
            entries: list[int] = data.get("entries", [])
            new_winners = _pick_winners(entries, data["winner_count"])
            data["winners"] = new_winners
            cfg.set_other("giveaways", giveaways)
            await self._store.save(cfg)

        if new_winners:
            mentions = " ".join(f"<@{w}>" for w in new_winners)
            await ctx.respond(f"🎉 New winners: {mentions}!")
        else:
            await respond_error(ctx, "No entries to pick from.")
