from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .bot import Bot
    from .context import Context


class Plugin:
    """Base class for grouping related slash commands and event handlers.

    Subclass ``Plugin``, decorate methods with ``@slash`` and ``@on``, then
    add it to your bot with ``bot.add_plugin()``. Commands and handlers are
    registered automatically.

    Declare dependencies on other plugins with ``requires``::

        class InventoryPlugin(Plugin):
            requires = ("economy",)   # economy must be loaded first

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

    requires: tuple[str, ...] = ()
    """Plugin names that must be loaded before this plugin.

    ``add_plugin()`` raises :exc:`PluginDependencyError` if any required
    plugin is not already registered on the bot.
    """

    def __init__(self) -> None:
        self._bot: Bot | None = None
        self._instance_id: str = f"{self.__class__.__name__}_{id(self)}"
        if not hasattr(self, "name"):
            self.name = self.__class__.__name__.lower()
        if not hasattr(self, "version"):
            self.version = "1.0.0"
        if not hasattr(self, "author"):
            self.author = "Unknown"
        if not hasattr(self, "description"):
            self.description = "No description provided."

    def id(self, raw: str) -> str:
        """Namespace a string with this plugin's name.

        Returns ``f"{self.name}:{raw}"``.
        """
        return f"{self.name}:{raw}"

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
        """Called after the plugin is registered with add_plugin().

        During initial startup this fires inside setup_hook() — the bot is not
        yet fully ready and guild data is not available. Use on_ready() if you
        need the bot to be connected and guilds to be populated.

        Override this to run setup code (e.g. connecting to a database).
        """

    async def on_ready(self) -> None:
        """Called every time the bot becomes ready (after reconnects).

        Override this to run periodic setup code or check bot state.
        Called after on_load() on the first ready, then on every reconnect.
        """

    async def on_unload(self) -> None:
        """Called once when the plugin is removed with ``bot.remove_plugin()``.

        Override this to run teardown code (e.g. closing connections).
        """

    async def on_reload(self) -> None:
        """Called on the new instance immediately after a hot-reload swap.

        Override to re-initialize state that doesn't survive re-instantiation —
        cached data, open connections, middleware state, etc.  The plugin is
        fully registered and ``self.bot`` is available when this fires.

        Example::

            class MyPlugin(Plugin):
                async def on_load(self):
                    self.cache = await fetch_data()

                async def on_reload(self):
                    self.cache = await fetch_data()   # re-warm the cache
        """

    async def on_error(self, ctx: "Context", exc: Exception) -> None:
        """Called when any slash command in this plugin raises an unhandled exception.

        Override to add plugin-scoped error handling.  The per-command
        ``@command_error`` handler takes priority; this hook fires only when no
        per-command handler is registered.  The global ``@bot.on_error`` handler
        fires only when this hook is also absent (i.e. not overridden).

        Example::

            class MyPlugin(Plugin):
                async def on_error(self, ctx, exc):
                    await ctx.respond(f"Plugin error: {exc}", ephemeral=True)
        """
