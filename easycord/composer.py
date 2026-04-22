"""Fluent builder for composing an EasyCord bot."""
from __future__ import annotations

import logging

import discord

from . import middleware as _mw
from .bot import Bot
from .middleware import MiddlewareFn
from .plugin import Plugin


class Composer:
    """Fluent builder for composing a :class:`~easycord.Bot`.

    Chain configuration methods and call :meth:`build` to produce a
    ready-to-run bot instance.

    Example::

        from easycord import Composer
        from my_bot.plugins import ModerationPlugin, FunPlugin

        bot = (
            Composer()
            .intents(discord.Intents.default())
            .log()
            .catch_errors()
            .rate_limit(limit=5, window=10.0)
            .guild_only()
            .add_plugin(ModerationPlugin())
            .add_plugin(FunPlugin())
            .build()
        )

        bot.run("YOUR_TOKEN")
    """

    def __init__(self) -> None:
        self._intents: discord.Intents | None = None
        self._auto_sync: bool = True
        self._middleware: list[MiddlewareFn] = []
        self._plugins: list[Plugin] = []
        self._groups: list = []

    # ── Bot options ───────────────────────────────────────────

    def intents(self, intents: discord.Intents) -> Composer:
        """Set the Discord gateway intents."""
        self._intents = intents
        return self

    def auto_sync(self, enabled: bool = True) -> Composer:
        """Enable or disable automatic slash-command syncing on startup."""
        self._auto_sync = enabled
        return self

    # ── Built-in middleware ───────────────────────────────────

    def log(
        self,
        level: int = logging.INFO,
        fmt: str = "/{command} invoked by {user} in {guild}",
    ) -> Composer:
        """Add the built-in logging middleware."""
        self._middleware.append(_mw.log_middleware(level=level, fmt=fmt))
        return self

    def guild_only(self) -> Composer:
        """Add the built-in guild-only guard (blocks DM invocations)."""
        self._middleware.append(_mw.guild_only())
        return self

    def dm_only(self) -> Composer:
        """Add the built-in DM-only guard (blocks guild invocations)."""
        self._middleware.append(_mw.dm_only())
        return self

    def rate_limit(
        self,
        limit: int = 5,
        window: float = 10.0,
    ) -> Composer:
        """Add the built-in per-user sliding-window rate limiter."""
        self._middleware.append(_mw.rate_limit(limit, window))
        return self

    def catch_errors(
        self,
        message: str = "Something went wrong. Please try again.",
    ) -> Composer:
        """Add the built-in error-handler middleware."""
        self._middleware.append(_mw.catch_errors(message))
        return self

    def admin_only(
        self,
        message: str = "This command requires administrator permissions.",
    ) -> Composer:
        """Add the built-in administrator-only guard."""
        self._middleware.append(_mw.admin_only(message))
        return self

    def allowed_roles(self, *role_ids: int, message: str = "You don't have the required role to use this command.") -> Composer:
        """Add the built-in role-allowlist guard."""
        self._middleware.append(_mw.allowed_roles(*role_ids, message=message))
        return self

    def channel_only(
        self,
        *channel_ids: int,
        message: str = "This command cannot be used in this channel.",
    ) -> Composer:
        """Add the built-in channel-allowlist guard."""
        self._middleware.append(_mw.channel_only(*channel_ids, message=message))
        return self

    # ── Custom middleware, plugins & groups ───────────────────

    def use(self, middleware: MiddlewareFn) -> Composer:
        """Add a custom middleware function."""
        self._middleware.append(middleware)
        return self

    def add_plugin(self, plugin: Plugin) -> Composer:
        """Queue a plugin to be added to the bot."""
        self._plugins.append(plugin)
        return self

    def add_plugins(self, *plugins: Plugin) -> Composer:
        """Queue several plugins to be added to the bot."""
        self._plugins.extend(plugins)
        return self

    def add_group(self, group) -> Composer:
        """Queue a SlashGroup to be added to the bot."""
        self._groups.append(group)
        return self

    def add_groups(self, *groups) -> Composer:
        """Queue several SlashGroup namespaces to be added to the bot."""
        self._groups.extend(groups)
        return self

    # ── Build ─────────────────────────────────────────────────

    def build(self) -> Bot:
        """Construct and return the fully configured :class:`~easycord.Bot`."""
        bot = Bot(
            intents=self._intents,
            auto_sync=self._auto_sync,
        )
        for mw in self._middleware:
            bot.use(mw)
        for plugin in self._plugins:
            bot.add_plugin(plugin)
        for group in self._groups:
            bot.add_group(group)
        return bot
