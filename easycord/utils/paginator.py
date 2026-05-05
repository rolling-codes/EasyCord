"""Simple interactive paginator for embed and text pages."""
from __future__ import annotations

from dataclasses import dataclass
from math import ceil
from typing import Iterable

import discord


@dataclass(frozen=True)
class _Page:
    """Internal normalized page representation."""

    embed: discord.Embed


class Paginator:
    """Interactive paginator with easy constructors.

    Parameters
    ----------
    pages:
        List of embeds to paginate.
    owner_only:
        When ``True`` only the invoking user can navigate pages.
    timeout:
        View timeout in seconds.
    """

    def __init__(
        self,
        pages: list[discord.Embed],
        *,
        owner_only: bool = True,
        timeout: float = 120.0,
    ) -> None:
        if not pages:
            raise ValueError("Paginator requires at least one page.")
        self._pages = [_Page(embed=embed) for embed in pages]
        self._owner_only = owner_only
        self._timeout = timeout
        self._index = 0

    @property
    def page_count(self) -> int:
        """Return the total number of pages."""
        return len(self._pages)

    @property
    def pages(self) -> list[discord.Embed]:
        """Return a copy of paginator embeds for inspection/testing."""
        return [p.embed for p in self._pages]

    @staticmethod
    def _chunk_lines(lines: list[str], per_page: int) -> list[list[str]]:
        if per_page <= 0:
            raise ValueError("per_page must be greater than 0.")
        if not lines:
            return [[]]
        return [lines[i : i + per_page] for i in range(0, len(lines), per_page)]

    @classmethod
    def from_lines(
        cls,
        lines: Iterable[str],
        *,
        per_page: int = 10,
        title: str = "Pages",
        owner_only: bool = True,
        timeout: float = 120.0,
    ) -> "Paginator":
        """Build a paginator from text lines."""
        line_list = [str(line) for line in lines]
        chunks = cls._chunk_lines(line_list, per_page=per_page)
        total = max(1, ceil(max(len(line_list), 1) / per_page))
        embeds: list[discord.Embed] = []
        for idx, chunk in enumerate(chunks, start=1):
            body = "\n".join(chunk) if chunk else "_No entries_"
            embed = discord.Embed(
                title=title,
                description=body,
                color=discord.Color.blurple(),
            )
            embed.set_footer(text=f"Page {idx}/{total}")
            embeds.append(embed)
        return cls(
            embeds,
            owner_only=owner_only,
            timeout=timeout,
        )

    @classmethod
    def from_embeds(
        cls,
        embed_list: Iterable[discord.Embed],
        *,
        owner_only: bool = True,
        timeout: float = 120.0,
    ) -> "Paginator":
        """Build a paginator directly from embeds."""
        embeds = list(embed_list)
        return cls(
            embeds,
            owner_only=owner_only,
            timeout=timeout,
        )

    async def send(self, ctx) -> None:
        """Send the paginator through a command context."""
        if self.page_count == 1:
            await ctx.respond(embed=self._pages[0].embed)
            return

        owner_id = getattr(getattr(ctx, "user", None), "id", None)
        view = _PaginatorView(
            paginator=self,
            owner_id=owner_id,
            owner_only=self._owner_only,
            timeout=self._timeout,
        )

        await ctx.respond(embed=self._pages[self._index].embed, view=view)
        try:
            view.message = await ctx.interaction.original_response()
        except Exception:
            view.message = None

    def _move_first(self) -> None:
        self._index = 0

    def _move_prev(self) -> None:
        self._index = max(0, self._index - 1)

    def _move_next(self) -> None:
        self._index = min(self.page_count - 1, self._index + 1)

    def _move_last(self) -> None:
        self._index = self.page_count - 1

    def _current_embed(self) -> discord.Embed:
        return self._pages[self._index].embed


class _PaginatorView(discord.ui.View):
    """Internal pagination view."""

    def __init__(
        self,
        *,
        paginator: Paginator,
        owner_id: int | None,
        owner_only: bool,
        timeout: float,
    ) -> None:
        super().__init__(timeout=timeout)
        self.paginator = paginator
        self.owner_id = owner_id
        self.owner_only = owner_only
        self.message: discord.Message | None = None
        self._sync_buttons()

    def _sync_buttons(self) -> None:
        last_index = self.paginator.page_count - 1
        self.first_btn.disabled = self.paginator._index == 0
        self.prev_btn.disabled = self.paginator._index == 0
        self.next_btn.disabled = self.paginator._index == last_index
        self.last_btn.disabled = self.paginator._index == last_index

    async def _guard_owner(self, interaction: discord.Interaction) -> bool:
        if not self.owner_only:
            return True
        if self.owner_id is None:
            return True
        if interaction.user.id == self.owner_id:
            return True
        await interaction.response.send_message(
            "Only the command invoker can use this paginator.",
            ephemeral=True,
        )
        return False

    async def _apply(self, interaction: discord.Interaction) -> None:
        self._sync_buttons()
        await interaction.response.edit_message(
            embed=self.paginator._current_embed(),
            view=self,
        )

    @discord.ui.button(label="⏮️", style=discord.ButtonStyle.secondary)
    async def first_btn(
        self,
        interaction: discord.Interaction,
        _button: discord.ui.Button,
    ) -> None:
        if not await self._guard_owner(interaction):
            return
        self.paginator._move_first()
        await self._apply(interaction)

    @discord.ui.button(label="◀️", style=discord.ButtonStyle.secondary)
    async def prev_btn(
        self,
        interaction: discord.Interaction,
        _button: discord.ui.Button,
    ) -> None:
        if not await self._guard_owner(interaction):
            return
        self.paginator._move_prev()
        await self._apply(interaction)

    @discord.ui.button(label="▶️", style=discord.ButtonStyle.secondary)
    async def next_btn(
        self,
        interaction: discord.Interaction,
        _button: discord.ui.Button,
    ) -> None:
        if not await self._guard_owner(interaction):
            return
        self.paginator._move_next()
        await self._apply(interaction)

    @discord.ui.button(label="⏭️", style=discord.ButtonStyle.secondary)
    async def last_btn(
        self,
        interaction: discord.Interaction,
        _button: discord.ui.Button,
    ) -> None:
        if not await self._guard_owner(interaction):
            return
        self.paginator._move_last()
        await self._apply(interaction)

    @discord.ui.button(label="⏹️", style=discord.ButtonStyle.danger)
    async def stop_btn(
        self,
        interaction: discord.Interaction,
        _button: discord.ui.Button,
    ) -> None:
        if not await self._guard_owner(interaction):
            return
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(view=self)
        self.stop()

    async def on_timeout(self) -> None:
        for child in self.children:
            child.disabled = True
        if self.message is not None:
            try:
                await self.message.edit(view=self)
            except Exception:
                pass
