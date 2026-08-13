"""Thread-based support ticket system plugin."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import discord

from easycord import Plugin, slash
from easycord.helpers.channel import send_safe
from easycord.helpers.embed import EmbedBuilder
from easycord.server_config import ServerConfigStore
from ._shared import GuildLockManager, get_id, respond_error, set_id

if TYPE_CHECKING:
    from easycord import Context

logger = logging.getLogger(__name__)


def _format_duration(seconds: float) -> str:
    """Format a number of seconds into a human-readable string like '2h 15m'."""
    minutes, secs = divmod(int(seconds), 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h {minutes}m"
    if minutes:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


def _format_transcript(messages: list[discord.Message]) -> str:
    """Format a list of Discord messages into a plain-text transcript."""
    lines: list[str] = []
    for msg in sorted(messages, key=lambda m: m.created_at):
        ts = msg.created_at.strftime("%H:%M")
        content = msg.content or "[embed/attachment]"
        lines.append(f"[{ts}] {msg.author.display_name}: {content}")
    return "\n".join(lines)


def _is_support(member: discord.Member, support_role_id: int | None) -> bool:
    """Return True if *member* has the support role or manage_threads permission."""
    if member.guild_permissions.manage_threads:
        return True
    if support_role_id is None:
        return False
    return any(r.id == support_role_id for r in member.roles)


def _ticket_embed(data: dict) -> discord.Embed:
    claimed = (
        f"<@{data['claimed_by']}>" if data.get("claimed_by") else "Unclaimed"
    )
    return EmbedBuilder.success(
        f"🎫 Ticket #{data['ticket_number']}",
        (
            f"**Created by:** <@{data['creator_id']}>\n"
            f"**Status:** {data.get('status', 'open').capitalize()}\n"
            f"**Claimed by:** {claimed}\n"
            f"**Topic:** {data.get('topic') or 'No topic provided'}"
        ),
    )


class _TicketView(discord.ui.View):
    """Persistent Claim / Close control panel posted inside each ticket thread."""

    def __init__(
        self, plugin: TicketsPlugin, guild_id: int, thread_id: int
    ) -> None:
        super().__init__(timeout=None)
        self._plugin = plugin
        self._guild_id = guild_id
        self._thread_id = thread_id

        claim_btn = discord.ui.Button(
            label="✋ Claim",
            style=discord.ButtonStyle.primary,
            custom_id=f"ticket:claim:{thread_id}",
        )
        claim_btn.callback = self._on_claim

        close_btn = discord.ui.Button(
            label="🔒 Close",
            style=discord.ButtonStyle.red,
            custom_id=f"ticket:close:{thread_id}",
        )
        close_btn.callback = self._on_close

        self.add_item(claim_btn)
        self.add_item(close_btn)

    async def _on_claim(self, interaction: discord.Interaction) -> None:
        if interaction.guild is None:
            await interaction.response.send_message("This button can only be used in a server.", ephemeral=True)
            return
        guild = interaction.guild
        member = guild.get_member(interaction.user.id)
        if member is None:
            await interaction.response.send_message(
                "Could not verify your membership.", ephemeral=True
            )
            return

        async with self._plugin._locks.lock(self._guild_id):
            cfg = await self._plugin._store.load(self._guild_id)
            tickets: dict = cfg.get_other("tickets", {})
            data: dict | None = tickets.get(str(self._thread_id))
            if not data or data.get("status") != "open":
                await interaction.response.send_message(
                    "This ticket is no longer open.", ephemeral=True
                )
                return
            support_role_id: int | None = get_id(cfg, "support_role_id")
            if not _is_support(member, support_role_id):
                await interaction.response.send_message(
                    "Only support team members can claim tickets.", ephemeral=True
                )
                return
            data["claimed_by"] = interaction.user.id
            tickets[str(self._thread_id)] = data
            cfg.set_other("tickets", tickets)
            await self._plugin._store.save(cfg)

        await interaction.response.edit_message(embed=_ticket_embed(data), view=self)

    async def _on_close(self, interaction: discord.Interaction) -> None:
        guild = interaction.guild
        member = guild.get_member(interaction.user.id) if guild else None
        if member is None:
            await interaction.response.send_message(
                "Could not verify your membership.", ephemeral=True
            )
            return

        async with self._plugin._locks.lock(self._guild_id):
            cfg = await self._plugin._store.load(self._guild_id)
            tickets: dict = cfg.get_other("tickets", {})
            data: dict | None = tickets.get(str(self._thread_id))
            if not data or data.get("status") != "open":
                await interaction.response.send_message(
                    "This ticket is already closed.", ephemeral=True
                )
                return
            support_role_id: int | None = get_id(cfg, "support_role_id")
            log_channel_id: int | None = get_id(cfg, "log_channel_id")
            if not _is_support(member, support_role_id):
                await interaction.response.send_message(
                    "Only support team members can close tickets.", ephemeral=True
                )
                return
            data["status"] = "closed"
            data["closed_at"] = datetime.now(timezone.utc).isoformat()
            tickets[str(self._thread_id)] = data
            cfg.set_other("tickets", tickets)
            await self._plugin._store.save(cfg)

        await interaction.response.send_message("Closing ticket…")
        thread = interaction.channel
        if not isinstance(thread, discord.Thread):
            return

        await self._plugin._finish_close(thread, data, log_channel_id, guild)


class TicketsPlugin(Plugin):
    """Thread-based support ticket system.

    Members open a private thread for their support request. The support team
    can claim and close tickets. A transcript is posted to a log channel when
    a ticket closes.

    Quick start::

        from easycord.plugins.tickets import TicketsPlugin
        bot.add_plugin(TicketsPlugin())

    Slash commands registered
    -------------------------
    ``/ticket_setup``  — Configure support role and log channel (admin only).
    ``/ticket_open``   — Open a new support ticket.
    ``/ticket_close``  — Close the current ticket and post a transcript.
    ``/ticket_claim``  — Claim this ticket as your own.
    ``/ticket_add``    — Add a user to the current ticket thread.
    """

    def __init__(self, *, store_path: str = ".easycord/tickets") -> None:
        super().__init__()
        self._store = ServerConfigStore(store_path)
        self._locks = GuildLockManager()

    async def on_ready(self) -> None:
        """Re-register ticket panel views for all open tickets after reconnect."""
        store_base = self._store._base
        if not store_base.exists():
            return
        for path in store_base.glob("*.json"):
            try:
                guild_id = int(path.stem)
            except ValueError:
                continue
            cfg = await self._store.load(guild_id)
            tickets: dict = cfg.get_other("tickets", {})
            for thread_id_str, data in tickets.items():
                if data.get("status") != "open":
                    continue
                thread_id = int(thread_id_str)
                panel_msg_id: int | None = data.get("panel_message_id")
                view = _TicketView(self, guild_id, thread_id)
                try:
                    self.bot.add_view(view, message_id=panel_msg_id)
                except Exception:
                    pass  # panel message may have been deleted; the ticket itself still works

    async def _finish_close(
        self,
        thread: discord.Thread,
        data: dict,
        log_channel_id: int | None,
        guild: discord.Guild | None,
    ) -> None:
        """Post the transcript and archive the thread. Called after DB update."""
        opened_at = datetime.fromisoformat(data["opened_at"])
        duration = _format_duration(
            (datetime.now(timezone.utc) - opened_at).total_seconds()
        )

        try:
            # Capture the most recent 100 messages (the resolution), not the
            # oldest 100. _format_transcript re-sorts by created_at, so the
            # transcript stays chronological and the [-3800:] tail keeps the end
            # of the conversation.
            raw: list[discord.Message] = [
                msg async for msg in thread.history(limit=100, oldest_first=False)
            ]
        except discord.HTTPException:
            raw = []

        transcript = _format_transcript(raw)

        if log_channel_id and guild is not None:
            log_channel = guild.get_channel(log_channel_id)
            if isinstance(log_channel, discord.TextChannel):
                claimer = (
                    f"<@{data['claimed_by']}>"
                    if data.get("claimed_by")
                    else "Unclaimed"
                )
                log_builder = EmbedBuilder(
                    f"📋 Ticket #{data['ticket_number']} Transcript",
                    (
                        f"**Creator:** <@{data['creator_id']}>\n"
                        f"**Claimed by:** {claimer}\n"
                        f"**Duration:** {duration}"
                    ),
                    discord.Color.red(),
                )
                if transcript:
                    body = transcript if len(transcript) <= 3800 else transcript[-3800:] + "\n[truncated]"
                    log_builder.add_field(
                        name="Transcript",
                        value=f"```\n{body}\n```",
                        inline=False,
                    )
                await send_safe(log_channel, log=logger, what="ticket log", embed=log_builder.build())

        try:
            await thread.edit(archived=True, locked=True, reason="Ticket closed")
        except discord.HTTPException:
            pass  # thread may already be archived/deleted; DB state is already updated

    @slash(description="Set the support role and transcript log channel.", guild_only=True, require_admin=True)
    async def ticket_setup(
        self,
        ctx: Context,
        support_role: discord.Role,
        log_channel: discord.TextChannel,
    ) -> None:
        """Configure the ticket system for this server (admin only)."""
        if ctx.guild is None:
            return

        guild_id = ctx.guild.id
        async with self._locks.lock(guild_id):
            cfg = await self._store.load(guild_id)
            set_id(cfg, "support_role_id", support_role.id)
            set_id(cfg, "log_channel_id", log_channel.id)
            await self._store.save(cfg)

        await ctx.respond(
            f"Ticket system configured.\n"
            f"**Support role:** {support_role.mention}\n"
            f"**Log channel:** {log_channel.mention}",
            ephemeral=True,
        )

    @slash(description="Open a new support ticket.", guild_only=True, bot_permissions=["create_private_threads"])
    async def ticket_open(self, ctx: Context, topic: str = "") -> None:
        """Create a private thread for your support request."""
        if ctx.guild is None:
            return
        if not isinstance(ctx.channel, discord.TextChannel):
            await ctx.respond(
                "Tickets can only be opened in a text channel.", ephemeral=True
            )
            return

        guild_id = ctx.guild.id

        async with self._locks.lock(guild_id):
            cfg = await self._store.load(guild_id)
            counter: int = cfg.get_other("ticket_counter", 0) + 1
            cfg.set_other("ticket_counter", counter)
            support_role_id: int | None = get_id(cfg, "support_role_id")
            await self._store.save(cfg)

        ticket_number = counter
        safe_name = ctx.user.name.lower()[:20].replace(" ", "-")
        thread_name = f"ticket-{ticket_number}-{safe_name}"

        try:
            thread = await ctx.channel.create_thread(
                name=thread_name,
                auto_archive_duration=10080,
                type=discord.ChannelType.private_thread,
                reason=f"Ticket #{ticket_number} opened by {ctx.user}",
            )
        except discord.HTTPException as exc:
            await respond_error(ctx, f"Failed to create ticket: {exc}")
            return

        await thread.add_user(ctx.user)

        if support_role_id:
            role = ctx.guild.get_role(support_role_id)
            if role:
                for member in role.members:
                    try:
                        await thread.add_user(member)
                    except discord.HTTPException:
                        pass  # member may have left or already be in the thread; skip and continue with the rest

        data: dict = {
            "ticket_number": ticket_number,
            "creator_id": ctx.user.id,
            "claimed_by": None,
            "status": "open",
            "opened_at": datetime.now(timezone.utc).isoformat(),
            "topic": topic.strip() or None,
            "panel_message_id": None,
        }

        view = _TicketView(self, guild_id, thread.id)
        panel_msg = await send_safe(thread, log=logger, what="ticket panel", embed=_ticket_embed(data), view=view)
        if panel_msg is not None:
            data["panel_message_id"] = panel_msg.id

        async with self._locks.lock(guild_id):
            cfg = await self._store.load(guild_id)
            tickets: dict = cfg.get_other("tickets", {})
            tickets[str(thread.id)] = data
            cfg.set_other("tickets", tickets)
            await self._store.save(cfg)

        if panel_msg is not None:
            self.bot.add_view(view, message_id=panel_msg.id)
        await ctx.respond(
            f"Your ticket has been opened: {thread.mention}", ephemeral=True
        )

    @slash(description="Close the current ticket thread.", guild_only=True, bot_permissions=["manage_threads"])
    async def ticket_close(self, ctx: Context, reason: str = "") -> None:
        """Close this support ticket and post a transcript to the log channel."""
        if ctx.guild is None:
            return
        if not isinstance(ctx.channel, discord.Thread):
            await ctx.respond(
                "Run this inside a ticket thread.", ephemeral=True
            )
            return

        member = ctx.member
        if member is None:
            return

        guild_id = ctx.guild.id
        thread_id = ctx.channel.id

        async with self._locks.lock(guild_id):
            cfg = await self._store.load(guild_id)
            tickets: dict = cfg.get_other("tickets", {})
            data: dict | None = tickets.get(str(thread_id))
            if not data or data.get("status") != "open":
                await respond_error(ctx, "This is not an open ticket.")
                return
            support_role_id: int | None = get_id(cfg, "support_role_id")
            log_channel_id: int | None = get_id(cfg, "log_channel_id")
            if not _is_support(member, support_role_id):
                await ctx.respond(
                    "Only support team members can close tickets.", ephemeral=True
                )
                return
            data["status"] = "closed"
            data["closed_at"] = datetime.now(timezone.utc).isoformat()
            if reason:
                data["close_reason"] = reason
            tickets[str(thread_id)] = data
            cfg.set_other("tickets", tickets)
            await self._store.save(cfg)

        await ctx.respond("Closing ticket…")
        await self._finish_close(ctx.channel, data, log_channel_id, ctx.guild)

    @slash(description="Claim this ticket (support team only).", guild_only=True)
    async def ticket_claim(self, ctx: Context) -> None:
        """Assign yourself as the handler for the current ticket."""
        if ctx.guild is None:
            return
        if not isinstance(ctx.channel, discord.Thread):
            await ctx.respond(
                "Run this inside a ticket thread.", ephemeral=True
            )
            return

        member = ctx.member
        if member is None:
            return

        guild_id = ctx.guild.id
        thread_id = ctx.channel.id

        async with self._locks.lock(guild_id):
            cfg = await self._store.load(guild_id)
            tickets: dict = cfg.get_other("tickets", {})
            data: dict | None = tickets.get(str(thread_id))
            if not data or data.get("status") != "open":
                await respond_error(ctx, "This is not an open ticket.")
                return
            support_role_id: int | None = get_id(cfg, "support_role_id")
            if not _is_support(member, support_role_id):
                await ctx.respond(
                    "Only support team members can claim tickets.", ephemeral=True
                )
                return
            data["claimed_by"] = ctx.user.id
            tickets[str(thread_id)] = data
            cfg.set_other("tickets", tickets)
            await self._store.save(cfg)

        await ctx.respond(f"Ticket claimed by {ctx.user.mention}.")

    @slash(description="Add a user to this ticket thread.", guild_only=True, bot_permissions=["manage_threads"])
    async def ticket_add(self, ctx: Context, user: discord.Member) -> None:
        """Add a member to the current ticket thread (support team only)."""
        if ctx.guild is None:
            return
        if not isinstance(ctx.channel, discord.Thread):
            await ctx.respond(
                "Run this inside a ticket thread.", ephemeral=True
            )
            return

        member = ctx.member
        if member is None:
            return

        guild_id = ctx.guild.id
        async with self._locks.lock(guild_id):
            cfg = await self._store.load(guild_id)
            support_role_id: int | None = get_id(cfg, "support_role_id")
            if not _is_support(member, support_role_id):
                await ctx.respond(
                    "Only support team members can add users to tickets.",
                    ephemeral=True,
                )
                return

        try:
            await ctx.channel.add_user(user)
            await ctx.respond(f"Added {user.mention} to the ticket.")
        except discord.HTTPException as exc:
            await respond_error(ctx, f"Failed to add user: {exc}")
