"""
EasyCord — a developer-friendly framework for building Discord bots.

Quick start::

    from easycord import EasyCord
    from easycord.middleware import logging_middleware

    bot = EasyCord()
    bot.use(logging_middleware())

    @bot.slash(description="Ping the bot")
    async def ping(ctx):
        await ctx.respond("Pong!")

    bot.run("YOUR_TOKEN")
"""

from .bot import EasyCord
from .composer import Composer
from .context import Context
from .decorators import on, slash
from .plugin import Plugin
from .server_config import ServerConfig, ServerConfigStore

__all__ = [
    "EasyCord",
    "Composer",
    "Context",
    "Plugin",
    "slash",
    "on",
    "ServerConfig",
    "ServerConfigStore",
]
