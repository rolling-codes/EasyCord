"""Bot shell wiring together the mixin modules."""
from __future__ import annotations

import asyncio
import os
import logging
from typing import Callable

import discord
from discord import app_commands

from .builtin_plugins import build_builtin_plugins
from .database import DatabaseConfig, EasyCordDatabase, MemoryDatabase, SQLiteDatabase
from .i18n import LocalizationManager
from .middleware import MiddlewareFn
from .plugin import Plugin
from ._bot_commands import _CommandsMixin
from ._bot_events import _EventsMixin
from ._bot_guild import _GuildMixin
from ._bot_plugins import _PluginsMixin
from .registry import InteractionRegistry
from .tools import ToolRegistry
from .builtin_tools import register_builtin_tools

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
        load_builtin_plugins: bool = False,
        database: EasyCordDatabase | None = None,
        db_backend: str | None = None,
        db_path: str | None = None,
        db_auto_sync_guilds: bool | None = None,
        localization: LocalizationManager | None = None,
        default_locale: str = "en-US",
        translations: dict | None = None,
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
        self.ai_tools: dict[str, dict] = {}
        self.tool_registry = ToolRegistry()
        try:
            register_builtin_tools(self.tool_registry)
        except Exception as e:
            logger.debug(f"Failed to register builtin AI tools: {e}")
        self._error_handler = None
        self.db = database or self._create_database(
            db_backend=db_backend,
            db_path=db_path,
            db_auto_sync_guilds=db_auto_sync_guilds,
        )
        self.localization: LocalizationManager | None = localization or (
            LocalizationManager(default_locale=default_locale, translations=translations)
            if translations
            else None
        )
        if load_builtin_plugins:
            self.load_builtin_plugins()

    def _create_database(
        self,
        *,
        db_backend: str | None,
        db_path: str | None,
        db_auto_sync_guilds: bool | None,
    ) -> EasyCordDatabase:
        config = DatabaseConfig.from_env()
        backend = db_backend or config.backend
        path = db_path or os.getenv("EASYCORD_DB_PATH") or config.path
        auto_sync = config.auto_sync_guilds if db_auto_sync_guilds is None else db_auto_sync_guilds

        if backend == "memory":
            return MemoryDatabase(auto_sync_guilds=auto_sync)
        if backend == "sqlite":
            return SQLiteDatabase(path=path, auto_sync_guilds=auto_sync)
        raise ValueError(
            f"Unknown database backend {backend!r}. Must be 'sqlite' or 'memory'."
        )

    def load_builtin_plugins(self) -> None:
        """Load the framework's bundled first-party plugins."""
        loaded_types = {type(plugin) for plugin in self._plugins}
        for plugin in build_builtin_plugins():
            if type(plugin) in loaded_types:
                continue
            self.add_plugin(plugin)
            loaded_types.add(type(plugin))

    async def setup_hook(self) -> None:
        await self.db.ensure_schema()
        if self.db.auto_sync_guilds:
            await self.db.sync_guilds([guild.id for guild in getattr(self, "guilds", [])])
        if self._auto_sync:
            await self.tree.sync()
        for plugin in self._plugins:
            await plugin.on_load()
            self._start_plugin_tasks(plugin)

    async def on_ready(self) -> None:
        if self.db.auto_sync_guilds:
            await self.db.sync_guilds([guild.id for guild in getattr(self, "guilds", [])])
        logger.info("Logged in as %s (ID: %s)", self.user, self.user.id)  # type: ignore[union-attr]

    async def close(self) -> None:  # type: ignore[override]
        await self.db.close()
        await super().close()

    def run(self, token: str, **kwargs) -> None:  # type: ignore[override]
        """Configure basic logging and start the bot."""
        logging.basicConfig(level=logging.INFO)
        super().run(token, **kwargs)


# Imported here to avoid a circular import at module level while still allowing
# the type annotation in add_group to resolve at runtime.
from .group import SlashGroup  # noqa: E402
