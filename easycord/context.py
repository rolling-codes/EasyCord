"""Context object wrapping discord.Interaction with a simple response API."""
from __future__ import annotations

import asyncio
import datetime
import types as _types

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

    async def dm(
        self,
        content: str | None = None,
        *,
        embed: discord.Embed | None = None,
        **kwargs,
    ) -> None:
        """Send a direct message to the user who invoked the command.

        Example::

            @bot.slash(description="Send yourself a reminder")
            async def remind(ctx, message: str):
                await ctx.dm(f"Reminder: {message}")
                await ctx.respond("Reminder sent!", ephemeral=True)
        """
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

        Looks up the channel from the client cache first; falls back to a
        Discord API fetch if it is not cached.

        Example::

            @bot.slash(description="Post to the logs channel")
            async def log(ctx, message: str):
                await ctx.send_to(LOG_CHANNEL_ID, f"**Log:** {message}")
                await ctx.respond("Posted.", ephemeral=True)
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

    # ── Interactive UI ────────────────────────────────────────

    async def ask_form(
        self,
        title: str,
        **fields: dict,
    ) -> dict[str, str] | None:
        """Show a modal form and return submitted values as a ``dict``.

        Each keyword argument becomes a text input field. Pass a ``dict``
        with ``discord.ui.TextInput`` kwargs (``label``, ``max_length``,
        ``style``, etc.) as the value. ``style`` may be a string such as
        ``"short"`` or ``"paragraph"``.

        Returns ``None`` if the user dismisses or the modal times out.

        Example::

            result = await ctx.ask_form(
                "Feedback",
                subject=dict(label="Subject", max_length=100),
                body=dict(label="Body", style="paragraph"),
            )
            if result:
                await ctx.respond(f"Got: {result['subject']}")
        """
        future: asyncio.Future[dict[str, str] | None] = asyncio.get_running_loop().create_future()

        # Build TextInput items keyed by field name (used as custom_id).
        attrs: dict = {}
        for name, config in fields.items():
            cfg = dict(config)
            style_raw = cfg.pop("style", discord.TextStyle.short)
            if isinstance(style_raw, str):
                style_raw = getattr(discord.TextStyle, style_raw, discord.TextStyle.short)
            attrs[name] = discord.ui.TextInput(
                label=cfg.pop("label", name),
                custom_id=name,
                style=style_raw,
                **cfg,
            )

        _fut = future

        async def on_submit(self, interaction: discord.Interaction) -> None:
            await interaction.response.defer()
            if not _fut.done():
                _fut.set_result(
                    {c.custom_id: c.value for c in self.children
                     if isinstance(c, discord.ui.TextInput)}
                )

        async def on_timeout(*_) -> None:
            if not _fut.done():
                _fut.set_result(None)

        attrs["on_submit"] = on_submit
        attrs["on_timeout"] = on_timeout

        ModalClass = _types.new_class(
            "_DynamicModal",
            (discord.ui.Modal,),
            {},
            lambda ns: ns.update(attrs),
        )

        await self.interaction.response.send_modal(ModalClass(title=title))
        self._responded = True

        try:
            return await asyncio.wait_for(future, timeout=660)
        except asyncio.TimeoutError:
            return None

    async def confirm(
        self,
        prompt: str,
        *,
        timeout: float = 30,
        yes_label: str = "Yes",
        no_label: str = "Cancel",
        ephemeral: bool = False,
    ) -> bool | None:
        """Show a Yes/No button prompt and return the user's choice.

        Returns ``True`` (yes), ``False`` (no/cancel), or ``None`` (timed out).

        Example::

            confirmed = await ctx.confirm(f"Ban {member.mention}?", timeout=30)
            if confirmed:
                await member.ban()
            elif confirmed is False:
                await ctx.respond("Cancelled.", ephemeral=True)
        """
        future: asyncio.Future[bool | None] = asyncio.get_running_loop().create_future()
        _fut = future
        _yes = yes_label
        _no = no_label

        class _ConfirmView(discord.ui.View):
            @discord.ui.button(label=_yes, style=discord.ButtonStyle.green)
            async def yes_btn(self, interaction: discord.Interaction, *_) -> None:
                await interaction.response.edit_message(view=discord.ui.View())
                if not _fut.done():
                    _fut.set_result(True)
                self.stop()

            @discord.ui.button(label=_no, style=discord.ButtonStyle.red)
            async def no_btn(self, interaction: discord.Interaction, *_) -> None:
                await interaction.response.edit_message(view=discord.ui.View())
                if not _fut.done():
                    _fut.set_result(False)
                self.stop()

            async def on_timeout(self) -> None:
                if not _fut.done():
                    _fut.set_result(None)

        view = _ConfirmView(timeout=timeout)
        await self.respond(prompt, ephemeral=ephemeral, view=view)
        return await future

    async def paginate(
        self,
        pages: list[str | discord.Embed],
        *,
        timeout: float = 120,
        ephemeral: bool = False,
    ) -> None:
        """Show a multi-page browsable message with Prev / Next buttons.

        ``pages`` may be a list of strings or ``discord.Embed`` objects,
        or a mix of both.

        Example::

            await ctx.paginate(["Page 1", "Page 2", "Page 3"])

            embeds = [discord.Embed(title=f"Entry {i}") for i in range(10)]
            await ctx.paginate(embeds, timeout=60)
        """
        if not pages:
            return

        idx = [0]
        n = len(pages)

        def _kw(i: int) -> dict:
            page = pages[i]
            if isinstance(page, discord.Embed):
                return {"embed": page, "content": None}
            return {"content": str(page), "embed": None}

        prev_btn = discord.ui.Button(
            label="◀", style=discord.ButtonStyle.secondary, disabled=True
        )
        next_btn = discord.ui.Button(
            label="▶", style=discord.ButtonStyle.secondary, disabled=n <= 1
        )

        async def on_prev(interaction: discord.Interaction) -> None:
            idx[0] = max(0, idx[0] - 1)
            prev_btn.disabled = idx[0] == 0
            next_btn.disabled = idx[0] == n - 1
            await interaction.response.edit_message(**_kw(idx[0]), view=view)

        async def on_next(interaction: discord.Interaction) -> None:
            idx[0] = min(n - 1, idx[0] + 1)
            prev_btn.disabled = idx[0] == 0
            next_btn.disabled = idx[0] == n - 1
            await interaction.response.edit_message(**_kw(idx[0]), view=view)

        prev_btn.callback = on_prev
        next_btn.callback = on_next

        view = discord.ui.View(timeout=timeout)
        view.add_item(prev_btn)
        view.add_item(next_btn)

        await self.respond(**_kw(0), ephemeral=ephemeral, view=view)

    async def choose(
        self,
        prompt: str,
        options: list[str | dict],
        *,
        timeout: float = 60,
        placeholder: str = "Select an option",
        ephemeral: bool = False,
    ) -> str | None:
        """Show a select-menu prompt and return the chosen value, or ``None`` on timeout.

        ``options`` may be a list of strings or dicts with ``label``, ``value``,
        and optional ``description`` keys.

        Example::

            choice = await ctx.choose("Pick a color", ["Red", "Green", "Blue"])
            if choice:
                await ctx.respond(f"You picked {choice}!")
        """
        future: asyncio.Future[str | None] = asyncio.get_running_loop().create_future()
        _fut = future

        select_options = []
        for opt in options:
            if isinstance(opt, str):
                select_options.append(discord.SelectOption(label=opt, value=opt))
            else:
                select_options.append(discord.SelectOption(
                    label=opt.get("label", str(opt)),
                    value=opt.get("value", opt.get("label", str(opt))),
                    description=opt.get("description"),
                ))

        class _ChooseView(discord.ui.View):
            @discord.ui.select(placeholder=placeholder, options=select_options)
            async def select_menu(self, interaction: discord.Interaction, select: discord.ui.Select) -> None:
                await interaction.response.edit_message(view=discord.ui.View())
                if not _fut.done():
                    _fut.set_result(select.values[0])
                self.stop()

            async def on_timeout(self) -> None:
                if not _fut.done():
                    _fut.set_result(None)

        view = _ChooseView(timeout=timeout)
        await self.respond(prompt, ephemeral=ephemeral, view=view)
        return await future

    # ── Moderation ────────────────────────────────────────────

    async def kick(self, member: discord.Member, *, reason: str | None = None) -> None:
        """Kick a member from the server.

        Example::

            @bot.slash(description="Kick a member", permissions=["kick_members"])
            async def kick(ctx, member: discord.Member, reason: str = "No reason"):
                await ctx.kick(member, reason=reason)
                await ctx.respond(f"Kicked {member.display_name}.", ephemeral=True)
        """
        await member.kick(reason=reason)

    async def ban(
        self,
        member: discord.Member,
        *,
        reason: str | None = None,
        delete_message_days: int = 0,
    ) -> None:
        """Ban a member from the server.

        Parameters
        ----------
        delete_message_days:
            Number of days of the member's messages to delete (0–7).
        """
        await member.ban(reason=reason, delete_message_days=delete_message_days)

    async def timeout(
        self,
        member: discord.Member,
        duration: float,
        *,
        reason: str | None = None,
    ) -> None:
        """Temporarily mute a member. ``duration`` is in seconds.

        Example::

            await ctx.timeout(member, 300, reason="Spamming")  # 5-minute timeout
        """
        until = discord.utils.utcnow() + datetime.timedelta(seconds=duration)
        await member.timeout(until, reason=reason)

    async def unban(self, user: discord.User, *, reason: str | None = None) -> None:
        """Unban a user from the server by their User object.

        Example::

            user = await bot.fetch_user(user_id)
            await ctx.unban(user, reason="Appeal accepted")
        """
        if self.guild is None:
            raise RuntimeError("unban requires a guild context")
        await self.guild.unban(user, reason=reason)

    async def set_nickname(
        self,
        member: discord.Member,
        nickname: str | None,
        *,
        reason: str | None = None,
    ) -> None:
        """Set or clear a member's server nickname. Pass ``None`` to reset to default.

        Example::

            await ctx.set_nickname(member, "Cool Person")
            await ctx.set_nickname(member, None)  # reset
        """
        await member.edit(nick=nickname, reason=reason)

    async def move_member(
        self,
        member: discord.Member,
        channel_id: int | None,
        *,
        reason: str | None = None,
    ) -> None:
        """Move a member to a voice channel by ID, or disconnect them (pass ``None``).

        Accepts both ``VoiceChannel`` and ``StageChannel`` targets.

        Example::

            await ctx.move_member(member, AFK_CHANNEL_ID)
            await ctx.move_member(member, None)  # disconnect
        """
        if channel_id is None:
            await member.edit(voice_channel=None, reason=reason)
        else:
            channel = self.interaction.client.get_channel(channel_id)
            if not isinstance(channel, (discord.VoiceChannel, discord.StageChannel)):
                raise ValueError(f"Channel {channel_id} is not a voice or stage channel, or was not found")
            await member.edit(voice_channel=channel, reason=reason)

    # ── Role management ───────────────────────────────────────

    def _resolve_role(self, role_id: int) -> discord.Role:
        """Return a Role from this guild by ID, raising clear errors if not found."""
        if self.guild is None:
            raise RuntimeError("This method requires a guild context")
        role = self.guild.get_role(role_id)
        if role is None:
            raise ValueError(f"Role {role_id} not found in this server")
        return role

    async def add_role(
        self,
        member: discord.Member,
        role_id: int,
        *,
        reason: str | None = None,
    ) -> None:
        """Add a role to a member by role ID.

        Example::

            await ctx.add_role(member, VERIFIED_ROLE_ID)
        """
        await member.add_roles(self._resolve_role(role_id), reason=reason)

    async def remove_role(
        self,
        member: discord.Member,
        role_id: int,
        *,
        reason: str | None = None,
    ) -> None:
        """Remove a role from a member by role ID.

        Example::

            await ctx.remove_role(member, MUTED_ROLE_ID)
        """
        await member.remove_roles(self._resolve_role(role_id), reason=reason)

    async def create_role(
        self,
        name: str,
        *,
        color: discord.Color = discord.Color.default(),
        hoist: bool = False,
        mentionable: bool = False,
        reason: str | None = None,
    ) -> discord.Role:
        """Create a new role in the server and return it.

        Example::

            role = await ctx.create_role("VIP", color=discord.Color.gold(), hoist=True, mentionable=True)
            await ctx.add_role(member, role.id)
        """
        if self.guild is None:
            raise RuntimeError("create_role requires a guild context")
        return await self.guild.create_role(
            name=name, color=color, hoist=hoist, mentionable=mentionable, reason=reason
        )

    async def delete_role(self, role_id: int, *, reason: str | None = None) -> None:
        """Delete a role from the server by role ID.

        Example::

            await ctx.delete_role(OLD_ROLE_ID, reason="Role retired")
        """
        await self._resolve_role(role_id).delete(reason=reason)

    # ── Message management ────────────────────────────────────

    async def purge(self, limit: int = 10) -> int:
        """Bulk-delete recent messages in the current channel or thread. Returns count deleted.

        Example::

            @bot.slash(description="Clear messages", permissions=["manage_messages"])
            async def clear(ctx, count: int = 10):
                deleted = await ctx.purge(count)
                await ctx.respond(f"Deleted {deleted} messages.", ephemeral=True)
        """
        if not isinstance(self.channel, (discord.TextChannel, discord.Thread)):
            raise RuntimeError("purge can only be used in a text channel or thread")
        deleted = await self.channel.purge(limit=limit)
        return len(deleted)

    async def send_file(
        self,
        path: str,
        *,
        filename: str | None = None,
        content: str | None = None,
        ephemeral: bool = False,
    ) -> None:
        """Send a file attachment as the command response.

        Example::

            @bot.slash(description="Send the log file")
            async def logs(ctx):
                await ctx.send_file("bot.log", content="Here are the logs:")
        """
        file = discord.File(path, filename=filename)
        await self.respond(content, file=file, ephemeral=ephemeral)

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

        Example::

            @bot.slash(description="Open a support thread")
            async def support(ctx, topic: str):
                thread = await ctx.create_thread(f"Support: {topic}")
                await ctx.respond(f"Thread created: {thread.mention}", ephemeral=True)
        """
        if not isinstance(self.channel, discord.TextChannel):
            raise RuntimeError("create_thread can only be used in a text channel")
        return await self.channel.create_thread(
            name=name,
            auto_archive_duration=auto_archive_minutes,
            reason=reason,
        )

    async def fetch_messages(self, limit: int = 10) -> list[discord.Message]:
        """Return the ``limit`` most recent messages in the current channel.

        Example::

            @bot.slash(description="Show recent messages", permissions=["manage_messages"])
            async def recent(ctx, count: int = 5):
                messages = await ctx.fetch_messages(count)
                summary = "\\n".join(f"{m.author}: {m.content[:50]}" for m in messages)
                await ctx.respond(summary or "No messages.", ephemeral=True)
        """
        if not isinstance(self.channel, discord.abc.Messageable):
            raise RuntimeError("fetch_messages can only be used in a messageable channel")
        return [m async for m in self.channel.history(limit=limit)]

    # ── Channel management ────────────────────────────────────

    async def slowmode(self, seconds: int, *, reason: str | None = None) -> None:
        """Set the slowmode delay on the current channel. Pass ``0`` to disable.

        The maximum Discord allows is ``21600`` (6 hours).

        Example::

            @bot.slash(description="Set slowmode", permissions=["manage_channels"])
            async def slow(ctx, seconds: int = 10):
                await ctx.slowmode(seconds)
                await ctx.respond(f"Slowmode set to {seconds}s.", ephemeral=True)
        """
        if not isinstance(self.channel, discord.TextChannel):
            raise RuntimeError("slowmode can only be used in a text channel")
        await self.channel.edit(slowmode_delay=seconds, reason=reason)

    async def _set_channel_lock(self, send_messages: bool, *, reason: str | None = None) -> None:
        if not isinstance(self.channel, discord.TextChannel) or self.guild is None:
            raise RuntimeError("lock/unlock can only be used in a guild text channel")
        overwrite = self.channel.overwrites_for(self.guild.default_role)
        if overwrite.send_messages == send_messages:
            return  # already in the desired state — skip the API call
        overwrite.send_messages = send_messages
        await self.channel.set_permissions(self.guild.default_role, overwrite=overwrite, reason=reason)

    async def lock_channel(self, *, reason: str | None = None) -> None:
        """Prevent @everyone from sending messages in the current channel.

        Preserves any existing per-role overrides. No-op if already locked.

        Example::

            @bot.slash(description="Lock the channel", permissions=["manage_channels"])
            async def lock(ctx):
                await ctx.lock_channel(reason="Ongoing incident")
                await ctx.respond("Channel locked.", ephemeral=True)
        """
        await self._set_channel_lock(False, reason=reason)

    async def unlock_channel(self, *, reason: str | None = None) -> None:
        """Restore @everyone's ability to send messages in the current channel.

        No-op if the channel is already unlocked.

        Example::

            @bot.slash(description="Unlock the channel", permissions=["manage_channels"])
            async def unlock(ctx):
                await ctx.unlock_channel()
                await ctx.respond("Channel unlocked.", ephemeral=True)
        """
        await self._set_channel_lock(True, reason=reason)

    # ── Reactions ─────────────────────────────────────────────

    async def react(self, message: discord.Message, emoji: str) -> None:
        """Add a reaction to a message.

        Example::

            messages = await ctx.fetch_messages(1)
            await ctx.react(messages[0], "👍")
        """
        await message.add_reaction(emoji)

    async def unreact(self, message: discord.Message, emoji: str) -> None:
        """Remove the bot's own reaction from a message.

        Example::

            await ctx.unreact(message, "👍")
        """
        await message.remove_reaction(emoji, self.interaction.client.user)  # type: ignore[arg-type]

    async def clear_reactions(self, message: discord.Message) -> None:
        """Remove all reactions from a message.

        Requires the ``manage_messages`` permission.

        Example::

            await ctx.clear_reactions(message)
        """
        await message.clear_reactions()

    async def delete_message(
        self,
        message: discord.Message,
        *,
        delay: float | None = None,
    ) -> None:
        """Delete a specific message, optionally after a delay in seconds.

        Example::

            messages = await ctx.fetch_messages(1)
            await ctx.delete_message(messages[0])
            await ctx.delete_message(message, delay=5.0)  # delete after 5 seconds
        """
        await message.delete(delay=delay)

    # ── Invoker voice state ───────────────────────────────────

    @property
    def voice_channel(self) -> discord.VoiceChannel | discord.StageChannel | None:
        """The voice channel the command invoker is currently in, or ``None``.

        Only works inside a guild; returns ``None`` in DMs or if the member's
        voice state is not cached.

        Example::

            @bot.slash(description="Join my voice channel")
            async def join(ctx):
                if ctx.voice_channel is None:
                    await ctx.respond("You're not in a voice channel.", ephemeral=True)
                else:
                    await ctx.respond(f"You're in {ctx.voice_channel.name}.")
        """
        member = self.interaction.user
        if isinstance(member, discord.Member) and member.voice:
            return member.voice.channel  # type: ignore[return-value]
        return None

    # ── Response editing ──────────────────────────────────────

    async def edit_response(
        self,
        content: str | None = None,
        *,
        embed: discord.Embed | None = None,
        **kwargs,
    ) -> None:
        """Edit the bot's original response to this interaction.

        Useful for "Loading…" patterns — defer, do work, then edit in the result.

        Example::

            @bot.slash(description="Generate a report")
            async def report(ctx):
                await ctx.defer()
                data = await fetch_data()
                await ctx.edit_response(f"Report ready: {data}")
        """
        await self.interaction.edit_original_response(content=content, embed=embed, **kwargs)

    # ── Message pinning ───────────────────────────────────────

    async def pin(self, message: discord.Message, *, reason: str | None = None) -> None:
        """Pin a message in the current channel.

        Requires the ``manage_messages`` permission.

        Example::

            messages = await ctx.fetch_messages(1)
            await ctx.pin(messages[0], reason="Important announcement")
        """
        await message.pin(reason=reason)

    async def unpin(self, message: discord.Message, *, reason: str | None = None) -> None:
        """Unpin a pinned message from the current channel.

        Requires the ``manage_messages`` permission.

        Example::

            await ctx.unpin(message)
        """
        await message.unpin(reason=reason)

    # ── Announcement channels ─────────────────────────────────

    async def crosspost(self, message: discord.Message) -> None:
        """Publish (crosspost) a message from an announcement channel to all followers.

        The channel must be a ``discord.TextChannel`` with the ``news`` type.

        Example::

            @bot.slash(description="Publish the latest news", permissions=["manage_messages"])
            async def publish(ctx):
                messages = await ctx.fetch_messages(1)
                await ctx.crosspost(messages[0])
                await ctx.respond("Published!", ephemeral=True)
        """
        await message.publish()

    # ── Member & ban helpers ──────────────────────────────────

    def get_member(self, user_id: int) -> discord.Member | None:
        """Look up a guild member from the local cache without an API call.

        Returns ``None`` if the member is not cached or the command was run in a DM.

        Example::

            member = ctx.get_member(stored_id)
            if member:
                await ctx.respond(f"Found: {member.display_name}")
        """
        return self.guild.get_member(user_id) if self.guild else None

    async def fetch_bans(self, limit: int | None = None) -> list[discord.BanEntry]:
        """Return a list of ban entries for the current guild.

        Parameters
        ----------
        limit:
            Maximum number of entries to fetch. ``None`` fetches all bans.

        Example::

            bans = await ctx.fetch_bans(limit=50)
            summary = "\\n".join(str(b.user) for b in bans)
            await ctx.respond(summary or "No bans.", ephemeral=True)
        """
        if self.guild is None:
            raise RuntimeError("fetch_bans requires a guild context")
        return [entry async for entry in self.guild.bans(limit=limit)]
