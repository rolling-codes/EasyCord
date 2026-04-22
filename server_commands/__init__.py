"""
Server command plugins for EasyCord.

Import plugins from here (or from individual modules) and load them into your bot:

    from server_commands import FunPlugin, ModerationPlugin, InfoPlugin
    load_default_plugins(bot)
"""

from easycord import Bot, Plugin

from .fun import FunPlugin
from .moderation import ModerationPlugin
from .info import InfoPlugin

DEFAULT_PLUGINS: tuple[type[Plugin], ...] = (
    FunPlugin,
    ModerationPlugin,
    InfoPlugin,
)


def build_default_plugins() -> tuple[Plugin, ...]:
    """Create the built-in example plugins in one place."""
    return tuple(plugin_class() for plugin_class in DEFAULT_PLUGINS)


def load_default_plugins(bot: Bot) -> None:
    """Register the standard example plugins on a bot."""
    plugins = build_default_plugins()
    if hasattr(bot, "add_plugins"):
        bot.add_plugins(*plugins)
        return
    for plugin in plugins:
        bot.add_plugin(plugin)


__all__ = [
    "FunPlugin",
    "ModerationPlugin",
    "InfoPlugin",
    "DEFAULT_PLUGINS",
    "build_default_plugins",
    "load_default_plugins",
]
