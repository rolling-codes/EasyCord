"""Channel, thread, reaction, and message-management helpers for Context."""
from __future__ import annotations

import discord


class ChannelMixin:
    """Mixin that adds channel, thread, reaction, and message helpers to Context.

    Requires ``self.channel``, ``self.guild``, and ``self.interaction`` from BaseContext.
    """

    # ── Channel management ────────────────────────────────────

    async def slowmode(self, seconds: int, *, reason: str | None = None) -> None:
        """Set the slowmode delay on the current channel. Pass ``0`` to disable.

        The maximum Discord allows is ``21600`` (6 hours).
        """
        if not isinstance(self.channel, discord.TextChannel):  # type: ignore[attr-defined]
            raise RuntimeError("slowmode can only be used in a text channel")
        await self.channel.edit(slowmode_delay=seconds, reason=reason)  # type: ignore[attr-defined]

    async def _set_channel_lock(self, send_messages: bool, *, reason: str | None = None) -> None:
        if not isinstance(self.channel, discord.TextChannel) or self.guild is None:  # type: ignore[attr-defined]
            raise RuntimeError("lock/unlock can only be used in a guild text channel")
        overwrite = self.channel.overwrites_for(self.guild.default_role)  # type: ignore[attr-defined]
        if overwrite.send_messages == send_messages:
            return  # already in the desired state — skip the API call
        overwrite.send_messages = send_messages
        await self.channel.set_permissions(  # type: ignore[attr-defined]
            self.guild.default_role, overwrite=overwrite, reason=reason  # type: ignore[attr-defined]
        )

    async def lock_channel(self, *, reason: str | None = None) -> None:
        """Prevent @everyone from sending messages in the current channel.

        Preserves any existing per-role overrides. No-op if already locked.
        """
        await self._set_channel_lock(False, reason=reason)

    async def unlock_channel(self, *, reason: str | None = None) -> None:
        """Restore @everyone's ability to send messages in the current channel.

        No-op if the channel is already unlocked.
        """
        await self._set_channel_lock(True, reason=reason)

    # ── Threads & history ─────────────────────────────────────

    async def create_thread(
        self,
        name: str,
        *,
        auto_archive_minutes: int = 1440,
        reason: str | None = None,
    ) -> discord.Thread:
        """Create a public thread in the current channel and return it.

        ``auto_archive_minutes`` must be one of ``60``, ``1440`` (default),
        ``4320``, or ``10080``.
        """
        if not isinstance(self.channel, discord.TextChannel):  # type: ignore[attr-defined]
            raise RuntimeError("create_thread can only be used in a text channel")
        return await self.channel.create_thread(  # type: ignore[attr-defined]
            name=name,
            auto_archive_duration=auto_archive_minutes,
            reason=reason,
        )

    async def fetch_messages(self, limit: int = 10) -> list[discord.Message]:
        """Return the ``limit`` most recent messages in the current channel."""
        if not isinstance(self.channel, discord.abc.Messageable):  # type: ignore[attr-defined]
            raise RuntimeError("fetch_messages can only be used in a messageable channel")
        return [m async for m in self.channel.history(limit=limit)]  # type: ignore[attr-defined]

    # ── Reactions ─────────────────────────────────────────────

    async def react(self, message: discord.Message, emoji: str) -> None:
        """Add a reaction to a message."""
        await message.add_reaction(emoji)

    async def unreact(self, message: discord.Message, emoji: str) -> None:
        """Remove the bot's own reaction from a message."""
        await message.remove_reaction(emoji, self.interaction.client.user)  # type: ignore[attr-defined, arg-type]

    async def clear_reactions(self, message: discord.Message) -> None:
        """Remove all reactions from a message. Requires ``manage_messages``."""
        await message.clear_reactions()

    # ── Message management ────────────────────────────────────

    async def delete_message(
        self,
        message: discord.Message,
        *,
        delay: float | None = None,
    ) -> None:
        """Delete a specific message, optionally after a delay in seconds."""
        await message.delete(delay=delay)

    async def pin(self, message: discord.Message, *, reason: str | None = None) -> None:
        """Pin a message in the current channel. Requires ``manage_messages``."""
        await message.pin(reason=reason)

    async def unpin(self, message: discord.Message, *, reason: str | None = None) -> None:
        """Unpin a pinned message from the current channel. Requires ``manage_messages``."""
        await message.unpin(reason=reason)

    async def crosspost(self, message: discord.Message) -> None:
        """Publish (crosspost) a message from an announcement channel to all followers.

        The channel must be a ``discord.TextChannel`` with the ``news`` type.
        """
        await message.publish()

    # ── Typing indicator ──────────────────────────────────────────────────────

    def typing(self):
        """Return a context manager that shows the typing indicator in the current channel.

        Use with ``async with``::

            async with ctx.typing():
                data = await fetch_data()
                await ctx.respond(data)
        """
        if self.channel is None:  # type: ignore[attr-defined]
            raise RuntimeError("typing requires a channel context")
        return self.channel.typing()  # type: ignore[attr-defined]

    async def fetch_pinned_messages(self) -> list[discord.Message]:
        """Return all pinned messages in the current channel."""
        if self.channel is None:  # type: ignore[attr-defined]
            raise RuntimeError("fetch_pinned_messages requires a channel context")
        return await self.channel.pins()  # type: ignore[attr-defined]
