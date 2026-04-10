"""
Server command plugins for EasyCord.

Import plugins from here (or from individual modules) and load them into your bot:

    from server_commands import FunPlugin, ModerationPlugin, InfoPlugin
    bot.add_plugin(FunPlugin())
"""

from .fun import FunPlugin
from .moderation import ModerationPlugin
from .info import InfoPlugin

__all__ = ["FunPlugin", "ModerationPlugin", "InfoPlugin"]
