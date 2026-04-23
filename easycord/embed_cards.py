"""Reusable embed wrappers that can bundle views with embeds."""
from __future__ import annotations

import datetime
from dataclasses import dataclass
from typing import Iterable

import discord

_STYLE_MAP: dict[str, discord.ButtonStyle] = {
    "primary": discord.ButtonStyle.primary,
    "secondary": discord.ButtonStyle.secondary,
    "success": discord.ButtonStyle.success,
    "danger": discord.ButtonStyle.danger,
    "link": discord.ButtonStyle.link,
}


@dataclass(slots=True)
class _ButtonSpec:
    label: str
    custom_id: str | None
    style: str
    url: str | None


@dataclass(slots=True)
class _SelectSpec:
    custom_id: str
    placeholder: str | None
    options: list[tuple[str, str, str | None]]
    min_values: int
    max_values: int


class EmbedCard:
    """Wrap an existing embed and attach buttons or selects to it.

    Use this when you already have a prepared ``discord.Embed`` but want a
    reusable object that also manages the associated ``discord.ui.View``.

    Example::

        card = (
            EmbedCard.from_embed(embed)
            .button("Approve", custom_id="approve", style="success")
            .button("Reject", custom_id="reject", style="danger")
        )
        await ctx.respond(**card.to_kwargs())
    """

    def __init__(self, embed: discord.Embed | None = None) -> None:
        self._embed = embed or discord.Embed()
        self._buttons: list[_ButtonSpec] = []
        self._selects: list[_SelectSpec] = []

    @classmethod
    def from_embed(cls, embed: discord.Embed) -> EmbedCard:
        """Wrap an existing embed object."""
        return cls(embed=embed)

    def title(self, text: str) -> EmbedCard:
        self._embed.title = text
        return self

    def description(self, text: str) -> EmbedCard:
        self._embed.description = text
        return self

    def field(self, name: str, value: str, inline: bool = True) -> EmbedCard:
        self._embed.add_field(name=name, value=value, inline=inline)
        return self

    def footer(self, text: str) -> EmbedCard:
        self._embed.set_footer(text=text)
        return self

    def color(self, color: discord.Color) -> EmbedCard:
        self._embed.color = color
        return self

    def thumbnail(self, url: str) -> EmbedCard:
        self._embed.set_thumbnail(url=url)
        return self

    def image(self, url: str) -> EmbedCard:
        self._embed.set_image(url=url)
        return self

    def author(
        self,
        name: str,
        *,
        icon_url: str | None = None,
        url: str | None = None,
    ) -> EmbedCard:
        self._embed.set_author(name=name, icon_url=icon_url, url=url)
        return self

    def timestamp(self, value: datetime.datetime | None = None) -> EmbedCard:
        self._embed.timestamp = value
        return self

    def button(
        self,
        label: str,
        custom_id: str | None = None,
        *,
        style: str = "primary",
        url: str | None = None,
    ) -> EmbedCard:
        if style == "link" and not url:
            raise ValueError("link buttons require a URL")
        if style != "link" and url is not None:
            raise ValueError("only link buttons may include a URL")
        self._buttons.append(_ButtonSpec(label, custom_id, style, url))
        return self

    def link(self, label: str, url: str) -> EmbedCard:
        """Convenience helper for link buttons."""
        return self.button(label, style="link", url=url)

    def select(
        self,
        custom_id: str,
        *,
        placeholder: str | None = None,
        options: Iterable[tuple[str, str] | tuple[str, str, str | None]] = (),
        min_values: int = 1,
        max_values: int = 1,
    ) -> EmbedCard:
        normalized: list[tuple[str, str, str | None]] = []
        for option in options:
            if len(option) == 2:
                label, value = option
                description = None
            else:
                label, value, description = option
            normalized.append((label, value, description))
        if not normalized:
            raise ValueError("select menus require at least one option")
        self._selects.append(_SelectSpec(custom_id, placeholder, normalized, min_values, max_values))
        return self

    def _build_view(self) -> discord.ui.View | None:
        if not self._buttons and not self._selects:
            return None
        view = discord.ui.View()
        for spec in self._buttons:
            button = discord.ui.Button(
                label=spec.label,
                style=_STYLE_MAP.get(spec.style, discord.ButtonStyle.primary),
                custom_id=spec.custom_id,
                url=spec.url,
            )
            view.add_item(button)
        for spec in self._selects:
            select = discord.ui.Select(
                custom_id=spec.custom_id,
                placeholder=spec.placeholder,
                min_values=spec.min_values,
                max_values=spec.max_values,
                options=[
                    discord.SelectOption(label=label, value=value, description=description)
                    for label, value, description in spec.options
                ],
            )
            view.add_item(select)
        return view

    def build(self) -> tuple[discord.Embed, discord.ui.View | None]:
        """Return the wrapped embed and an optional view."""
        return self._embed, self._build_view()

    def to_kwargs(self) -> dict[str, object]:
        """Return kwargs suitable for ``ctx.respond`` or ``channel.send``."""
        embed, view = self.build()
        payload: dict[str, object] = {"embed": embed}
        if view is not None:
            payload["view"] = view
        return payload

    async def respond(self, ctx, *, content: str | None = None, ephemeral: bool = False, **kwargs) -> None:
        """Send the embed card through a framework context."""
        await ctx.respond(content=content, ephemeral=ephemeral, **self.to_kwargs(), **kwargs)


class InfoEmbed(EmbedCard):
    """Pre-styled embed card for neutral informational content."""

    def __init__(self, embed: discord.Embed | None = None) -> None:
        super().__init__(embed or discord.Embed(color=discord.Color.blurple()))


class SuccessEmbed(EmbedCard):
    """Pre-styled embed card for positive confirmations."""

    def __init__(self, embed: discord.Embed | None = None) -> None:
        super().__init__(embed or discord.Embed(color=discord.Color.green()))


class WarningEmbed(EmbedCard):
    """Pre-styled embed card for cautionary notices."""

    def __init__(self, embed: discord.Embed | None = None) -> None:
        super().__init__(embed or discord.Embed(color=discord.Color.orange()))


class ErrorEmbed(EmbedCard):
    """Pre-styled embed card for failures and rejected actions."""

    def __init__(self, embed: discord.Embed | None = None) -> None:
        super().__init__(embed or discord.Embed(color=discord.Color.red()))
