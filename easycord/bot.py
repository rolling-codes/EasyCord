"""Bot shell wiring together the mixin modules."""
from __future__ import annotations

import asyncio
import logging
from typing import Callable

import discord
from discord import app_commands

from .middleware import MiddlewareFn
from .plugin import Plugin
from ._bot_commands import _CommandsMixin
from ._bot_events import _EventsMixin
from ._bot_guild import _GuildMixin
from ._bot_plugins import _PluginsMixin
from .i18n import LocalizationManager
from .registry import InteractionRegistry

logger = logging.getLogger("easycord")


class Bot(_EventsMixin, _GuildMixin, _PluginsMixin, _CommandsMixin, discord.Client):
    """
    The main bot — a discord.Client with slash commands,
    middleware, event listeners, and plugins built in.

    Quick start::

        import os
        from easycord import Bot
        from easycord.middleware import log_middleware, catch_errors

        bot = Bot()
        bot.use(log_middleware())
        bot.use(catch_errors())

        @bot.slash(description="Ping the bot")
        async def ping(ctx):
            await ctx.respond("Pong!")

        bot.run(os.environ["DISCORD_TOKEN"])

    Parameters
    ----------
    intents:
        Discord gateway intents. Defaults to ``discord.Intents.default()``.
    auto_sync:
        Automatically sync slash commands with Discord on startup (default ``True``).
        Set to ``False`` during development to avoid hitting Discord's sync rate limit.
    """

    def __init__(
        self,
        *,
        intents: discord.Intents | None = None,
        auto_sync: bool = True,
        localization: LocalizationManager | None = None,
        default_locale: str = "en-US",
        translations: dict[str, dict[str, str]] | None = None,
        **kwargs,
    ) -> None:
        super().__init__(intents=intents or discord.Intents.default(), **kwargs)
        self.tree = app_commands.CommandTree(self)
        self._auto_sync = auto_sync
        self._middleware: list[MiddlewareFn] = []
        self._event_handlers: dict[str, list[Callable]] = {}
        self._plugins: list[Plugin] = []
        self._task_handles: dict[int, list[asyncio.Task]] = {}
        self._webhooks: dict[int, discord.Webhook] = {}
        self.registry = InteractionRegistry()
        self._error_handler = None
        self.localization = localization or LocalizationManager(
            default_locale=default_locale,
            translations=translations,
        )
        self.i18n = self.localization

    async def setup_hook(self) -> None:
        if self._auto_sync:
            await self.tree.sync()
        for plugin in self._plugins:
            await plugin.on_load()
            self._start_plugin_tasks(plugin)

    async def on_ready(self) -> None:
        logger.info("Logged in as %s (ID: %s)", self.user, self.user.id)  # type: ignore[union-attr]

    def run(self, token: str, **kwargs) -> None:  # type: ignore[override]
        """Configure basic logging and start the bot."""
        logging.basicConfig(level=logging.INFO)
        super().run(token, **kwargs)


# Imported here to avoid a circular import at module level while still allowing
# the type annotation in add_group to resolve at runtime.
from .group import SlashGroup  # noqa: E402
