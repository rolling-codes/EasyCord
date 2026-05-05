"""Fluent builder for discord.Embed."""
from __future__ import annotations

import discord


class EmbedBuilder:
    """Fluent builder that produces a ``discord.Embed``.

    Call ``.build()`` to get the finished embed::

        embed = (EmbedBuilder()
            .title("Hello")
            .description("World")
            .field("Score", "100")
            .footer("Bot v2.8")
            .color(discord.Color.green())
            .build())
        await ctx.respond(embed=embed)
    """

    def __init__(self) -> None:
        self._title: str | None = None
        self._description: str | None = None
        self._fields: list[tuple[str, str, bool]] = []
        self._footer: str | None = None
        self._color: discord.Color = discord.Color.blue()

    def title(self, text: str) -> EmbedBuilder:
        self._title = text
        return self

    def description(self, text: str) -> EmbedBuilder:
        self._description = text
        return self

    def field(self, name: str, value: str, inline: bool = True) -> EmbedBuilder:
        self._fields.append((name, value, inline))
        return self

    def footer(self, text: str) -> EmbedBuilder:
        self._footer = text
        return self

    def color(self, color: discord.Color) -> EmbedBuilder:
        self._color = color
        return self

    def build(self) -> discord.Embed:
        if self._title is None:
            raise ValueError("EmbedBuilder requires a title")
        embed = discord.Embed(
            title=self._title,
            description=self._description,
            color=self._color,
        )
        for name, value, inline in self._fields:
            embed.add_field(name=name, value=value, inline=inline)
        if self._footer is not None:
            embed.set_footer(text=self._footer)
        return embed
