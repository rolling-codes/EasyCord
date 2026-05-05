"""Fluent builder for a discord.ui.View containing buttons."""
from __future__ import annotations

import discord

_STYLE_MAP: dict[str, discord.ButtonStyle] = {
    "primary": discord.ButtonStyle.primary,
    "secondary": discord.ButtonStyle.secondary,
    "success": discord.ButtonStyle.success,
    "danger": discord.ButtonStyle.danger,
    "link": discord.ButtonStyle.link,
}


class ButtonRowBuilder:
    """Fluent builder that produces a ``discord.ui.View`` containing buttons.

    Handlers are wired via ``@bot.component(custom_id)``. For link buttons
    pass ``style="link"`` and ``url="https://..."`` instead of ``custom_id``::

        view = (ButtonRowBuilder()
            .button("Approve", custom_id="approve", style="success")
            .button("Deny", custom_id="deny", style="danger")
            .build())
        await ctx.respond("Approve?", view=view)
    """

    def __init__(self) -> None:
        self._buttons: list[dict] = []

    def button(
        self,
        label: str,
        custom_id: str | None = None,
        style: str = "primary",
        url: str | None = None,
    ) -> ButtonRowBuilder:
        self._buttons.append(
            {"label": label, "custom_id": custom_id, "style": style, "url": url}
        )
        return self

    def build(self) -> discord.ui.View:
        view = discord.ui.View()
        for b in self._buttons:
            btn = discord.ui.Button(
                label=b["label"],
                style=_STYLE_MAP.get(b["style"], discord.ButtonStyle.primary),
                custom_id=b["custom_id"],
                url=b["url"],
            )
            view.add_item(btn)
        return view
