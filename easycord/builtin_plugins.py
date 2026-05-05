"""Helpers for loading the framework's bundled plugins."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .plugin import Plugin


def builtin_plugin_classes() -> tuple[type["Plugin"], ...]:
    """Return the built-in plugin classes shipped with EasyCord."""
    from .plugins import LevelsPlugin, PollsPlugin, TagsPlugin, WelcomePlugin

    return (WelcomePlugin, TagsPlugin, PollsPlugin, LevelsPlugin)


def build_builtin_plugins() -> tuple["Plugin", ...]:
    """Instantiate the built-in plugins."""
    return tuple(plugin_cls() for plugin_cls in builtin_plugin_classes())
