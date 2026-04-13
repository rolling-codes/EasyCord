"""Core Context object wrapping discord.Interaction with a simple response API."""
from __future__ import annotations

import discord


class BaseContext:
    """Core wrapper around ``discord.Interaction``.

    Provides read-only properties and the fundamental response helpers
    (``respond``, ``defer``, ``send_embed``, ``dm``, ``send_to``,
    ``send_file``, ``edit_response``).

    All higher-level mixins (UI, moderation, channels) inherit from this class.
    """

    def __init__(self, interaction: discord.Interaction) -> None:
        self.interaction = interaction
        self._responded = False
        self._force_ephemeral = False

    # ── Read-only properties ──────────────────────────────────

    @property
    def user(self) -> discord.User | discord.Member:
        """The user who ran the command."""
        return self.interaction.user

    @property
    def guild(self) -> discord.Guild | None:
        """The server the command was run in, or ``None`` if it was in a DM."""
        return self.interaction.guild

    @property
    def channel(self) -> discord.abc.Messageable | None:
        """The channel the command was run in."""
        return self.interaction.channel  # type: ignore[return-value]

    @property
    def command_name(self) -> str | None:
        """The name of the slash command that was invoked."""
        cmd = self.interaction.command
        return cmd.name if cmd is not None else None

    @property
    def data(self) -> dict | None:
        """The raw interaction data from Discord."""
        return self.interaction.data  # type: ignore[return-value]

    @property
    def voice_channel(self) -> discord.VoiceChannel | discord.StageChannel | None:
        """The voice channel the command invoker is currently in, or ``None``.

        Only works inside a guild; returns ``None`` in DMs or if the member's
        voice state is not cached.
        """
        member = self.interaction.user
        if isinstance(member, discord.Member) and member.voice:
            return member.voice.channel  # type: ignore[return-value]
        return None

    # ── Responding ────────────────────────────────────────────

    async def respond(
        self,
        content: str | None = None,
        *,
        ephemeral: bool = False,
        embed: discord.Embed | None = None,
        **kwargs,
    ) -> None:
        """Send a reply to the command.

        The first call sends an initial response; any further calls send
        follow-up messages automatically. If the command was registered with
        ``ephemeral=True``, all responses are forced ephemeral automatically.
        """
        ephemeral = ephemeral or self._force_ephemeral
        if not self._responded:
            self._responded = True
            await self.interaction.response.send_message(
                content, ephemeral=ephemeral, embed=embed, **kwargs
            )
        else:
            await self.interaction.followup.send(
                content, ephemeral=ephemeral, embed=embed, **kwargs
            )

    async def defer(self, *, ephemeral: bool = False) -> None:
        """Acknowledge the interaction without sending a visible reply yet.

        Use this at the start of commands that take more than 3 seconds, then
        call ``respond()`` when you're ready. Has no effect if already responded.
        """
        if self._responded:
            return
        self._responded = True
        await self.interaction.response.defer(ephemeral=ephemeral)

    async def send_embed(
        self,
        title: str,
        description: str | None = None,
        *,
        fields: list[tuple] | None = None,
        footer: str | None = None,
        color: discord.Color = discord.Color.blue(),
        ephemeral: bool = False,
        **kwargs,
    ) -> None:
        """Build and send a Discord embed in one call.

        ``fields`` is a list of ``(name, value)`` or ``(name, value, inline)``
        tuples. ``inline`` defaults to ``True`` when omitted.
        """
        embed = discord.Embed(title=title, description=description, color=color)
        for field in (fields or []):
            name, value, *rest = field
            embed.add_field(name=name, value=value, inline=rest[0] if rest else True)
        if footer:
            embed.set_footer(text=footer)
        await self.respond(embed=embed, ephemeral=ephemeral, **kwargs)

    async def dm(
        self,
        content: str | None = None,
        *,
        embed: discord.Embed | None = None,
        **kwargs,
    ) -> None:
        """Send a direct message to the user who invoked the command."""
        try:
            await self.user.send(content, embed=embed, **kwargs)
        except discord.Forbidden:
            raise RuntimeError(
                f"Cannot send a DM to {self.user} — they have DMs disabled or have blocked the bot."
            ) from None

    async def send_to(
        self,
        channel_id: int,
        content: str | None = None,
        **kwargs,
    ) -> None:
        """Send a message to any channel by ID.

        Looks up the channel from the client cache first; falls back to an API fetch.
        """
        try:
            channel = (
                self.interaction.client.get_channel(channel_id)
                or await self.interaction.client.fetch_channel(channel_id)
            )
        except discord.NotFound:
            raise RuntimeError(f"Channel {channel_id} does not exist.") from None
        except discord.Forbidden:
            raise RuntimeError(
                f"Bot does not have permission to access channel {channel_id}."
            ) from None
        await channel.send(content, **kwargs)  # type: ignore[union-attr]

    async def send_file(
        self,
        path: str,
        *,
        filename: str | None = None,
        content: str | None = None,
        ephemeral: bool = False,
    ) -> None:
        """Send a file attachment as the command response."""
        file = discord.File(path, filename=filename)
        await self.respond(content, file=file, ephemeral=ephemeral)

    async def edit_response(
        self,
        content: str | None = None,
        *,
        embed: discord.Embed | None = None,
        **kwargs,
    ) -> None:
        """Edit the bot's original response to this interaction.

        Useful for "Loading…" patterns — defer, do work, then edit in the result.
        """
        await self.interaction.edit_original_response(content=content, embed=embed, **kwargs)

    # ── Member lookup ─────────────────────────────────────────

    @property
    def guild_id(self) -> int | None:
        """The ID of the guild the command was run in, or ``None`` in DMs.

        Shortcut for ``ctx.guild.id`` that is safe to call without a guild check.
        """
        return self.guild.id if self.guild else None

    @property
    def is_admin(self) -> bool:
        """``True`` if the invoking member has the administrator permission.

        Always ``False`` in DMs or when the member is not cached.
        """
        m = self.member
        return m is not None and m.guild_permissions.administrator

    @property
    def member(self) -> discord.Member | None:
        """The invoking user as a ``discord.Member``, or ``None`` in DMs.

        Unlike ``ctx.user`` (typed ``User | Member``), this property always
        returns a ``Member`` when the command is used inside a server, giving
        access to guild-specific info such as ``.roles``, ``.nick``, and
        ``.guild_permissions`` without an extra cast or lookup.
        """
        u = self.interaction.user
        return u if isinstance(u, discord.Member) else None

    def get_member(self, user_id: int) -> discord.Member | None:
        """Look up a guild member from the local cache without an API call.

        Returns ``None`` if the member is not cached or the command was run in a DM.
        """
        return self.guild.get_member(user_id) if self.guild else None
