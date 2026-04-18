"""Interactive UI helpers for Context: modals, confirmation buttons, paginators, select menus."""
from __future__ import annotations

import asyncio
import types as _types

import discord


class UIMixin:
    """Mixin that adds interactive Discord UI methods to Context.

    Requires ``self.interaction`` and ``self._responded`` from BaseContext,
    and ``self.respond()`` for sending the initial message.
    """

    async def ask_form(
        self,
        title: str,
        **fields: dict,
    ) -> dict[str, str] | None:
        """Show a modal form and return submitted values as a ``dict``.

        Each keyword argument becomes a text input field. Pass a ``dict``
        with ``discord.ui.TextInput`` kwargs as the value. ``style`` may be
        a string such as ``"short"`` or ``"paragraph"``.

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

        await self.interaction.response.send_modal(ModalClass(title=title))  # type: ignore[attr-defined]
        self._responded = True  # type: ignore[attr-defined]

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
        await self.respond(prompt, ephemeral=ephemeral, view=view)  # type: ignore[attr-defined]
        return await future

    async def paginate(
        self,
        pages: list[str | discord.Embed],
        *,
        timeout: float = 120,
        ephemeral: bool = False,
    ) -> None:
        """Show a multi-page browsable message with Prev / Next buttons.

        ``pages`` may be a list of strings or ``discord.Embed`` objects, or a mix.

        Example::

            await ctx.paginate(["Page 1", "Page 2", "Page 3"])
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

        await self.respond(**_kw(0), ephemeral=ephemeral, view=view)  # type: ignore[attr-defined]

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
        await self.respond(prompt, ephemeral=ephemeral, view=view)  # type: ignore[attr-defined]
        return await future

    async def prompt(
        self,
        label: str,
        *,
        placeholder: str | None = None,
        max_length: int | None = None,
        timeout: float = 660,
    ) -> str | None:
        """Show a single-field modal and return the submitted text, or ``None`` on timeout.

        Shortcut for :meth:`ask_form` when only one text input is needed::

            text = await ctx.prompt("What's your reason?", placeholder="Enter reason…")
            if text:
                await ctx.respond(f"Reason: {text}")
        """
        field: dict = {"label": label}
        if placeholder is not None:
            field["placeholder"] = placeholder
        if max_length is not None:
            field["max_length"] = max_length
        result = await self.ask_form(label, value=field)  # type: ignore[attr-defined]
        return result["value"] if result else None

    async def send_buttons(
        self,
        prompt: str,
        buttons: list[str | dict],
        *,
        timeout: float = 60,
        ephemeral: bool = False,
    ) -> str | None:
        """Show a row of labeled buttons and return the value of the clicked one.

        ``buttons`` may be a list of strings or dicts with ``label``,
        optional ``value`` (defaults to label), and optional ``style``
        (``"green"``, ``"red"``, ``"blue"``, or ``"gray"``; defaults to gray).

        Returns ``None`` if timed out.  Maximum 5 buttons (Discord limit).

        Example::

            action = await ctx.send_buttons(
                "Confirm action?",
                buttons=[
                    {"label": "Approve", "value": "approve", "style": "green"},
                    {"label": "Deny",    "value": "deny",    "style": "red"},
                ],
                timeout=30,
                ephemeral=True,
            )
        """
        _style_map = {
            "green": discord.ButtonStyle.green,
            "red": discord.ButtonStyle.red,
            "blue": discord.ButtonStyle.blurple,
            "gray": discord.ButtonStyle.secondary,
            "grey": discord.ButtonStyle.secondary,
        }

        future: asyncio.Future[str | None] = asyncio.get_running_loop().create_future()
        _fut = future

        view = discord.ui.View(timeout=timeout)

        for btn_spec in buttons[:5]:
            if isinstance(btn_spec, str):
                label = btn_spec
                value = btn_spec
                style = discord.ButtonStyle.secondary
            else:
                label = btn_spec.get("label", str(btn_spec))
                value = btn_spec.get("value", label)
                style = _style_map.get(
                    btn_spec.get("style", "gray"), discord.ButtonStyle.secondary
                )

            button = discord.ui.Button(label=label, style=style)
            _val = value

            async def _callback(
                interaction: discord.Interaction, v: str = _val
            ) -> None:
                await interaction.response.edit_message(view=discord.ui.View())
                if not _fut.done():
                    _fut.set_result(v)
                view.stop()

            button.callback = _callback
            view.add_item(button)

        async def on_timeout() -> None:
            if not _fut.done():
                _fut.set_result(None)

        view.on_timeout = on_timeout  # type: ignore[method-assign]

        await self.respond(prompt, ephemeral=ephemeral, view=view)  # type: ignore[attr-defined]
        return await future
