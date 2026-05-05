"""High-level manager presets for secure and convenient bot setup."""
from __future__ import annotations

import logging

from .bot import Bot
from .composer import Composer
from .middleware import MiddlewareFn
from . import middleware as _mw
from .plugin import Plugin


class SecurityManager:
    """Build and apply a conservative middleware security baseline."""

    def __init__(
        self,
        *,
        log_level: int = logging.INFO,
        log_format: str = "/{command} invoked by {user} in {guild}",
        rate_limit: int = 5,
        rate_window: float = 10.0,
    ) -> None:
        self.log_level = log_level
        self.log_format = log_format
        self.rate_limit = rate_limit
        self.rate_window = rate_window

    def build(self) -> list[MiddlewareFn]:
        """Return middleware in the order they should execute."""
        return [
            _mw.log_middleware(level=self.log_level, fmt=self.log_format),
            _mw.catch_errors(),
            _mw.rate_limit(limit=self.rate_limit, window=self.rate_window),
        ]

    def apply(self, bot: Bot) -> Bot:
        """Apply this security baseline to a bot instance."""
        for middleware in self.build():
            bot.use(middleware)
        return bot

    def apply_to_composer(self, composer: Composer) -> Composer:
        """Apply this security baseline to a composer."""
        for middleware in self.build():
            composer.use(middleware)
        return composer


class FrameworkManager:
    """One-call convenience manager for common bot bootstraps."""

    @staticmethod
    def bootstrap(
        *,
        composer: Composer | None = None,
        secure: bool = True,
        guild_only: bool = False,
        builtin_plugins: bool = False,
        plugins: tuple[Plugin, ...] = (),
    ) -> Composer:
        """Return a composer with optional security and convenience presets."""
        result = composer or Composer()
        if secure:
            result.secure_defaults()
        if guild_only:
            result.guild_only()
        if builtin_plugins:
            result.builtin_plugins(True)
        if plugins:
            result.add_plugins(*plugins)
        return result

    @staticmethod
    def build_bot(
        *,
        composer: Composer | None = None,
        secure: bool = True,
        guild_only: bool = False,
        builtin_plugins: bool = False,
        plugins: tuple[Plugin, ...] = (),
    ) -> Bot:
        """Build a bot directly from the convenience bootstrap options."""
        return FrameworkManager.bootstrap(
            composer=composer,
            secure=secure,
            guild_only=guild_only,
            builtin_plugins=builtin_plugins,
            plugins=plugins,
        ).build()
