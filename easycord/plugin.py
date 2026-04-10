from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .bot import Bot


class Plugin:
    """Base class for grouping related slash commands and event handlers.

    Subclass ``Plugin``, decorate methods with ``@slash`` and ``@on``, then
    add it to your bot with ``bot.add_plugin()``. Commands and handlers are
    registered automatically.

    Example::

        from easycord import Plugin, slash, on

        class GreetPlugin(Plugin):

            async def on_load(self):
                print(f"GreetPlugin ready on {self.bot.user}")

            @slash(description="Say hello to someone")
            async def hello(self, ctx, name: str):
                await ctx.respond(f"Hello, {name}!")

            @on("member_join")
            async def welcome(self, member):
                await member.send(f"Welcome to {member.guild.name}!")

        bot.add_plugin(GreetPlugin())
    """

    def __init__(self) -> None:
        self._bot: Bot | None = None

    @property
    def bot(self) -> Bot:
        """The bot this plugin is attached to.

        Raises ``RuntimeError`` if accessed before the plugin is added to a bot.
        """
        if self._bot is None:
            raise RuntimeError(
                "Plugin has not been added to a bot yet. "
                "Call bot.add_plugin() before accessing self.bot."
            )
        return self._bot

    async def on_load(self) -> None:
        """Called once after the plugin is added and the bot is ready.

        Override this to run setup code (e.g. connecting to a database).
        """

    async def on_unload(self) -> None:
        """Called once when the plugin is removed with ``bot.remove_plugin()``.

        Override this to run teardown code (e.g. closing connections).
        """
