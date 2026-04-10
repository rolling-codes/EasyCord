from __future__ import annotations

import logging

import discord

from .bot import EasyCord
from .middleware import (
    MiddlewareFn,
    error_handler_middleware,
    guild_only_middleware,
    logging_middleware,
    rate_limit_middleware,
)
from .plugin import Plugin


class Composer:
    """Fluent builder for composing an EasyCord bot.

    Chain configuration methods and call :meth:`build` to produce a ready-to-run
    :class:`~easycord.EasyCord` instance.

    Example::

        from easycord import Composer
        from my_bot.plugins import ModerationPlugin, FunPlugin

        bot = (
            Composer()
            .with_intents(discord.Intents.default())
            .use_logging()
            .use_error_handler()
            .use_rate_limit(max_calls=5, window_seconds=10.0)
            .use_guild_only()
            .load_plugin(ModerationPlugin())
            .load_plugin(FunPlugin())
            .build()
        )

        bot.run("YOUR_TOKEN")
    """

    def __init__(self) -> None:
        self._intents: discord.Intents | None = None
        self._sync_commands: bool = True
        self._middleware: list[MiddlewareFn] = []
        self._plugins: list[Plugin] = []

    # ── Bot options ───────────────────────────────────────────

    def with_intents(self, intents: discord.Intents) -> Composer:
        """Set the Discord gateway intents."""
        self._intents = intents
        return self

    def sync_commands(self, enabled: bool = True) -> Composer:
        """Enable or disable automatic slash-command syncing on startup."""
        self._sync_commands = enabled
        return self

    # ── Built-in middleware ───────────────────────────────────

    def use_logging(
        self,
        level: int = logging.INFO,
        fmt: str = "/{command} invoked by {user} in {guild}",
    ) -> Composer:
        """Add the built-in logging middleware."""
        self._middleware.append(logging_middleware(level=level, fmt=fmt))
        return self

    def use_guild_only(self) -> Composer:
        """Add the built-in guild-only guard (blocks DM invocations)."""
        self._middleware.append(guild_only_middleware())
        return self

    def use_rate_limit(
        self,
        max_calls: int = 5,
        window_seconds: float = 10.0,
    ) -> Composer:
        """Add the built-in per-user sliding-window rate limiter."""
        self._middleware.append(rate_limit_middleware(max_calls, window_seconds))
        return self

    def use_error_handler(
        self,
        message: str = "Something went wrong. Please try again.",
    ) -> Composer:
        """Add the built-in error-handler middleware."""
        self._middleware.append(error_handler_middleware(message))
        return self

    # ── Custom middleware & plugins ───────────────────────────

    def use(self, middleware: MiddlewareFn) -> Composer:
        """Add a custom middleware function."""
        self._middleware.append(middleware)
        return self

    def load_plugin(self, plugin: Plugin) -> Composer:
        """Queue a plugin to be loaded into the bot."""
        self._plugins.append(plugin)
        return self

    # ── Build ─────────────────────────────────────────────────

    def build(self) -> EasyCord:
        """Construct and return the fully configured :class:`~easycord.EasyCord` bot."""
        bot = EasyCord(
            intents=self._intents,
            sync_commands=self._sync_commands,
        )
        for mw in self._middleware:
            bot.use(mw)
        for plugin in self._plugins:
            bot.load_plugin(plugin)
        return bot
