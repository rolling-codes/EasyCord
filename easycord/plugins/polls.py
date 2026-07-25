"""Button-based polling plugin for bots."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

import discord

from easycord import Plugin, slash
from easycord.helpers.channel import SENDABLE_CHANNEL_TYPES
from easycord.server_config import ServerConfigStore
from ._shared import GuildLockManager, respond_error

if TYPE_CHECKING:
    from easycord import Context

logger = logging.getLogger(__name__)


def _poll_options(*options: str) -> list[str]:
    return [option for option in options if option.strip()]


def _is_valid_duration(duration: int) -> bool:
    return duration >= 5


def _tally(options: list[str], votes: dict[str, int]) -> list[int]:
    counts = [0] * len(options)
    for idx in votes.values():
        counts[idx] += 1
    return counts


def _bar(filled: int) -> str:
    return "█" * filled + "░" * (10 - filled)


def _format_option_line(option: str, count: int, total: int) -> str:
    pct = count / total
    bar = _bar(round(pct * 10))
    votes_str = f"{count} vote{'s' if count != 1 else ''} ({pct:.0%})"
    return f"**{option}**\n`{bar}` {votes_str}"


def build_poll_embed(
    question: str,
    options: list[str],
    votes: dict[str, int],
    *,
    closed: bool = False,
    seconds_remaining: float = 0.0,
) -> discord.Embed:
    """Build the poll embed — a bar-chart breakdown of current vote counts."""
    counts = _tally(options, votes)
    total = sum(counts) or 1
    lines = [
        _format_option_line(option, count, total)
        for option, count in zip(options, counts)
    ]

    color = discord.Color.greyple() if closed else discord.Color.blurple()
    footer = "📊 Poll closed" if closed else f"⏱️ Closes in {seconds_remaining:.0f}s"
    embed = discord.Embed(
        title=f"📊 {question}",
        description="\n\n".join(lines),
        color=color,
    )
    embed.set_footer(text=footer)
    return embed


class _PollView(discord.ui.View):
    """A persistent poll vote view. One vote per user; changing vote is supported.

    Vote state lives in the owning plugin's per-guild store, not on the view
    instance — this lets the view (and the votes) be reconstructed after a bot
    restart instead of being lost when the original instance goes away.
    """

    def __init__(
        self,
        plugin: "PollsPlugin",
        guild_id: int,
        message_id: int,
        question: str,
        options: list[str],
    ) -> None:
        super().__init__(timeout=None)
        self._plugin = plugin
        self._guild_id = guild_id
        self._message_id = message_id
        self.question = question
        self.options = options

        self._register_buttons()

    def _register_buttons(self) -> None:
        for option_index, option in enumerate(self.options):
            self.add_item(self._make_button(option, option_index))

    def _make_button(self, label: str, option_index: int) -> discord.ui.Button:
        button = discord.ui.Button(
            label=label,
            style=discord.ButtonStyle.primary,
            custom_id=f"poll:vote:{self._message_id}:{option_index}",
        )
        button.callback = self._make_callback(option_index)
        return button

    def _make_callback(self, option_index: int):
        async def callback(interaction: discord.Interaction) -> None:
            async with self._plugin._locks.lock(self._guild_id):
                cfg = await self._plugin._store.load(self._guild_id)
                polls: dict = cfg.get_other("polls", {})
                data: dict | None = polls.get(str(self._message_id))
                if not data or data.get("status") != "active":
                    await interaction.response.send_message(
                        "This poll has already closed.", ephemeral=True
                    )
                    return
                votes: dict = data.get("votes", {})
                votes[str(interaction.user.id)] = option_index
                data["votes"] = votes
                polls[str(self._message_id)] = data
                cfg.set_other("polls", polls)
                await self._plugin._store.save(cfg)

            end_time = datetime.fromisoformat(data["end_time"])
            remaining = max((end_time - datetime.now(timezone.utc)).total_seconds(), 0.0)
            embed = build_poll_embed(
                self.question, self.options, votes, seconds_remaining=remaining
            )
            await interaction.response.edit_message(embed=embed, view=self)
        return callback

    def disable_all(self) -> None:
        """Disable every button — used once the poll has closed."""
        for child in self.children:
            child.disabled = True  # type: ignore[union-attr]


class PollsPlugin(Plugin):
    """Create live button-based polls that close automatically after a timeout.

    Members can vote on up to five options; each member gets exactly one vote
    (changing vote is supported). Active polls are backed by per-guild storage
    and resume automatically if the bot restarts — votes already cast and the
    remaining time are preserved. When a poll closes, the embed updates to
    show a bar-chart breakdown of final results.

    Quick start::

        from easycord.plugins.polls import PollsPlugin
        bot.add_plugin(PollsPlugin())

    Slash commands registered
    -------------------------
    ``/poll`` — Create a poll. Provide a question, 2–5 options, and an optional
                duration in seconds (default 60). Guild-only.
    """

    def __init__(self, *, store_path: str = ".easycord/polls") -> None:
        super().__init__()
        self._store = ServerConfigStore(store_path)
        self._locks = GuildLockManager()
        # guild_id -> message_id -> Task
        self._timers: dict[int, dict[int, asyncio.Task]] = {}

    # ── Lifecycle ─────────────────────────────────────────────

    async def on_ready(self) -> None:
        """Re-register poll views and resume timers for all active polls."""
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
                polls: dict = cfg.get_other("polls", {})
            except Exception:
                logger.exception("PollsPlugin on_ready: failed to load config for guild %d", guild_id)
                continue

            for msg_id_str, data in list(polls.items()):
                try:
                    if data.get("status") != "active":
                        continue
                    message_id = int(msg_id_str)
                    view = _PollView(
                        self, guild_id, message_id, data["question"], data["options"]
                    )
                    try:
                        self.bot.add_view(view, message_id=message_id)
                    except Exception:
                        pass  # poll message may have been deleted; the timer still resumes
                    end_time = datetime.fromisoformat(data["end_time"])
                    remaining = (end_time - now).total_seconds()
                    if remaining > 0:
                        self._schedule_timer(guild_id, message_id, remaining)
                    else:
                        asyncio.create_task(self._close_poll(guild_id, message_id))
                except Exception:
                    logger.warning(
                        "PollsPlugin on_ready: skipping malformed poll %r in guild %d",
                        msg_id_str, guild_id,
                    )

    async def on_unload(self) -> None:
        """Cancel all in-flight poll timers."""
        for guild_timers in self._timers.values():
            for task in guild_timers.values():
                task.cancel()
        self._timers.clear()

    # ── Task scheduling ───────────────────────────────────────

    def _schedule_timer(self, guild_id: int, message_id: int, seconds: float) -> None:
        task = asyncio.create_task(self._poll_timer(guild_id, message_id, seconds))
        self._timers.setdefault(guild_id, {})[message_id] = task

    async def _poll_timer(self, guild_id: int, message_id: int, seconds: float) -> None:
        try:
            await asyncio.sleep(seconds)
            await self._close_poll(guild_id, message_id)
        except asyncio.CancelledError:
            pass  # timer was cancelled (plugin unload); nothing more to do

    async def _close_poll(self, guild_id: int, message_id: int) -> None:
        """Mark a poll closed in storage, then render the final results."""
        async with self._locks.lock(guild_id):
            cfg = await self._store.load(guild_id)
            polls: dict = cfg.get_other("polls", {})
            data: dict | None = polls.get(str(message_id))
            if not data or data.get("status") != "active":
                return
            data["status"] = "closed"
            polls[str(message_id)] = data
            cfg.set_other("polls", polls)
            await self._store.save(cfg)

        self._timers.get(guild_id, {}).pop(message_id, None)

        guild = self.bot.get_guild(guild_id)
        if guild is None:
            return
        channel = guild.get_channel(data["channel_id"])
        if not isinstance(channel, SENDABLE_CHANNEL_TYPES):
            return
        try:
            message = await channel.fetch_message(message_id)
        except discord.NotFound:
            return

        embed = build_poll_embed(
            data["question"], data["options"], data.get("votes", {}), closed=True
        )
        view = _PollView(self, guild_id, message_id, data["question"], data["options"])
        view.disable_all()
        try:
            await message.edit(embed=embed, view=view)
        except discord.HTTPException:
            pass  # message may have been deleted

    # ── Commands ─────────────────────────────────────────────

    @slash(
        description="Create a button-based poll. 2–5 options, optional duration in seconds.",
        guild_only=True,
        bot_permissions=["send_messages"],
    )
    async def poll(
        self,
        ctx: "Context",
        question: str,
        option1: str,
        option2: str,
        option3: str = "",
        option4: str = "",
        option5: str = "",
        duration: int = 60,
    ) -> None:
        options = _poll_options(option1, option2, option3, option4, option5)
        if len(options) < 2:
            await respond_error(ctx, ctx.t("polls.min_options", default="A poll needs at least 2 options."))
            return
        if not _is_valid_duration(duration):
            await respond_error(ctx, ctx.t("polls.min_duration", default="Duration must be at least 5 seconds."))
            return
        if ctx.guild is None:
            return
        channel = ctx.channel
        if not isinstance(channel, SENDABLE_CHANNEL_TYPES):
            await respond_error(ctx, ctx.t("polls.channel_required", default="This command must be used in a channel."))
            return

        guild_id = ctx.guild.id
        channel_id: int = channel.id
        end_dt = datetime.now(timezone.utc) + timedelta(seconds=duration)

        embed = build_poll_embed(question, options, {}, seconds_remaining=float(duration))
        await ctx.respond(embed=embed)
        message = await ctx.interaction.original_response()
        message_id = message.id

        async with self._locks.lock(guild_id):
            cfg = await self._store.load(guild_id)
            polls: dict = cfg.get_other("polls", {})
            polls[str(message_id)] = {
                "channel_id": channel_id,
                "question": question,
                "options": options,
                "votes": {},
                "end_time": end_dt.isoformat(),
                "status": "active",
            }
            cfg.set_other("polls", polls)
            await self._store.save(cfg)

        view = _PollView(self, guild_id, message_id, question, options)
        self.bot.add_view(view, message_id=message_id)
        await message.edit(embed=embed, view=view)
        self._schedule_timer(guild_id, message_id, float(duration))
