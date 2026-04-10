"""Decorators for marking Plugin methods as slash commands or event handlers."""
from __future__ import annotations

from typing import Callable


def slash(
    name: str | None = None,
    *,
    description: str = "No description provided.",
    guild_id: int | None = None,
) -> Callable:
    """Mark a Plugin method as a slash command.

    Parameters
    ----------
    name:
        The command name shown in Discord. Defaults to the method name.
    description:
        Short description shown in the Discord command picker.
    guild_id:
        Register the command in one specific server only. Useful during
        development because server commands update instantly (global commands
        can take up to 1 hour).

    Example::

        class MyPlugin(Plugin):

            @slash(description="Roll a dice")
            async def roll(self, ctx, sides: int = 6):
                import random
                await ctx.respond(f"You rolled {random.randint(1, sides)}!")
    """

    def decorator(func: Callable) -> Callable:
        func._is_slash = True
        func._slash_name = name or func.__name__
        func._slash_desc = description
        func._slash_guild = guild_id
        return func

    return decorator


def on(event: str) -> Callable:
    """Mark a Plugin method as an event handler.

    Use the event name without the ``on_`` prefix. Any arguments that
    discord.py normally passes to ``on_<event>`` are forwarded to your method.

    Example::

        class MyPlugin(Plugin):

            @on("member_join")
            async def welcome(self, member):
                await member.send(f"Welcome to {member.guild.name}!")

            @on("message")
            async def echo(self, message):
                if "hello bot" in message.content.lower():
                    await message.reply("Hello!")
    """

    def decorator(func: Callable) -> Callable:
        func._is_event = True
        func._event_name = event
        return func

    return decorator
