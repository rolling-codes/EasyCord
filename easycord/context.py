"""Context object wrapping discord.Interaction with a simple response API.

The ``Context`` class is assembled from four focused mixins:

- ``_context_base.BaseContext``      — core properties and response helpers
- ``_context_ui.UIMixin``            — modals, confirmation buttons, paginators, select menus
- ``_context_moderation.ModerationMixin`` — kick/ban/timeout, role management, purge
- ``_context_channels.ChannelMixin`` — channel locks, threads, reactions, pins, crossposts

Add new groups of Discord helpers by creating a new ``*Mixin`` module and
adding it to the MRO below.
"""
from __future__ import annotations

import discord

from ._context_base import BaseContext
from ._context_channels import ChannelMixin
from ._context_moderation import ModerationMixin
from ._context_ui import UIMixin


class Context(UIMixin, ChannelMixin, ModerationMixin, BaseContext):
    """Wraps a ``discord.Interaction`` and gives you a full response/moderation API.

    This framework passes a ``Context`` as the first argument to every slash command::

        @bot.slash(description="Ping the bot")
        async def ping(ctx):
            await ctx.respond("Pong!")

    For commands that take a while, call ``defer()`` first so Discord doesn't
    time out while you work (you then have 15 minutes to follow up)::

        @bot.slash(description="Generate a report")
        async def report(ctx):
            await ctx.defer()
            data = await fetch_data()
            await ctx.respond(f"Done: {data}")
    """

    def __init__(self, interaction: discord.Interaction) -> None:
        super().__init__(interaction)
