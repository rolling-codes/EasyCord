"""Fluent builder for a discord.ui.View containing a select menu."""
from __future__ import annotations

import discord


class SelectMenuBuilder:
    """Fluent builder that produces a ``discord.ui.View`` containing a select menu.

    The handler is wired via ``@bot.component(custom_id)``::

        view = (SelectMenuBuilder()
            .placeholder("Pick one")
            .option("Option A", value="a")
            .option("Option B", value="b")
            .build(custom_id="my_select"))
        await ctx.respond("Choose:", view=view)
    """

    def __init__(self) -> None:
        self._placeholder: str | None = None
        self._options: list[tuple[str, str]] = []

    def placeholder(self, text: str) -> SelectMenuBuilder:
        self._placeholder = text
        return self

    def option(self, label: str, value: str) -> SelectMenuBuilder:
        self._options.append((label, value))
        return self

    def build(self, custom_id: str) -> discord.ui.View:
        if not self._options:
            raise ValueError("SelectMenuBuilder requires at least one option")
        select = discord.ui.Select(
            custom_id=custom_id,
            placeholder=self._placeholder,
            options=[discord.SelectOption(label=lbl, value=val) for lbl, val in self._options],
        )
        view = discord.ui.View()
        view.add_item(select)
        return view
