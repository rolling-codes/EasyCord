from __future__ import annotations

import discord


class Context:
    """Wraps a ``discord.Interaction`` and gives you a simple response API.

    EasyCord passes a ``Context`` as the first argument to every slash command::

        @bot.slash(description="Ping the bot")
        async def ping(ctx):
            await ctx.respond("Pong!")

    For commands that take a while, call ``defer()`` first so Discord doesn't
    time out while you work (you then have 15 minutes to follow up)::

        @bot.slash(description="Generate a report")
        async def report(ctx):
            await ctx.defer()                   # tells Discord "I'm working on it"
            data = await fetch_data()
            await ctx.respond(f"Done: {data}")  # follows up automatically
    """

    def __init__(self, interaction: discord.Interaction) -> None:
        self.interaction = interaction
        self._responded = False

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
        follow-up messages automatically.

        Parameters
        ----------
        content:
            The text message to send.
        ephemeral:
            If ``True``, only the user who ran the command can see the reply.
        embed:
            A ``discord.Embed`` to attach instead of (or alongside) text.
        """
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
        call ``respond()`` when you're ready. You have up to 15 minutes.

        Has no effect if the interaction has already been responded to.
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

        Example — a simple embed with fields::

            await ctx.send_embed(
                "Server Stats",
                fields=[("Members", "150"), ("Online", "42")],
                footer="Updated just now",
                color=discord.Color.green(),
            )
        """
        embed = discord.Embed(title=title, description=description, color=color)
        for field in (fields or []):
            name, value, *rest = field
            embed.add_field(name=name, value=value, inline=rest[0] if rest else True)
        if footer:
            embed.set_footer(text=footer)
        await self.respond(embed=embed, ephemeral=ephemeral, **kwargs)
