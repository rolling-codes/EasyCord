"""Plugin lifecycle, task management, and shared method-scanner."""
from __future__ import annotations

import asyncio
import inspect
import logging
from typing import Callable

import discord

from .plugin import Plugin

logger = logging.getLogger("easycord")


class _PluginsMixin:
    """Mixin: plugin add/remove, background tasks, and method scanning."""

    # ── Shared scanner ────────────────────────────────────────

    def _scan_methods(self, plugin: Plugin, *, parent=None) -> None:
        """Register all @slash and @on methods on *plugin*.

        parent: an ``app_commands.Group`` — when supplied, slash commands are
        added to the group instead of the command tree (used by add_group).
        """
        for _, method in inspect.getmembers(plugin, predicate=inspect.ismethod):
            if getattr(method, "_is_slash", False):
                self._register_slash(
                    method,
                    name=method._slash_name,
                    description=method._slash_desc,
                    guild_id=method._slash_guild,
                    guild_only=getattr(method, "_slash_guild_only", False),
                    ephemeral=getattr(method, "_slash_ephemeral", False),
                    permissions=getattr(method, "_slash_permissions", None),
                    cooldown=getattr(method, "_slash_cooldown", None),
                    autocomplete=getattr(method, "_slash_autocomplete", None),
                    choices=getattr(method, "_slash_choices", None),
                    parent=parent,
                )
                for alias in getattr(method, "_slash_aliases", []):
                    self._register_slash(
                        method,
                        name=alias,
                        description=method._slash_desc,
                        guild_id=method._slash_guild,
                        guild_only=getattr(method, "_slash_guild_only", False),
                        ephemeral=getattr(method, "_slash_ephemeral", False),
                        permissions=getattr(method, "_slash_permissions", None),
                        cooldown=getattr(method, "_slash_cooldown", None),
                        autocomplete=getattr(method, "_slash_autocomplete", None),
                        choices=getattr(method, "_slash_choices", None),
                        parent=parent,
                    )
            if getattr(method, "_is_event", False):
                self._event_handlers.setdefault(
                    method._event_name, []
                ).append(method)
            if getattr(method, "_is_user_command", False):
                self._register_context_menu(
                    method,
                    name=method._context_menu_name,
                    menu_type=discord.AppCommandType.user,
                    guild_id=method._context_menu_guild,
                )
            if getattr(method, "_is_message_command", False):
                self._register_context_menu(
                    method,
                    name=method._context_menu_name,
                    menu_type=discord.AppCommandType.message,
                    guild_id=method._context_menu_guild,
                )
            if getattr(method, "_is_component", False):
                custom_id = method._component_id
                if getattr(method, "_component_scoped", True):
                    custom_id = plugin.id(custom_id)
                self._register_component_handler(custom_id, method, source_plugin=type(plugin).__name__)
            if getattr(method, "_is_modal", False):
                custom_id = method._modal_id
                if getattr(method, "_modal_scoped", True):
                    custom_id = plugin.id(custom_id)
                self._register_modal_handler(custom_id, method, source_plugin=type(plugin).__name__)
            if getattr(method, "_is_ai_tool", False):
                tool_name = method._ai_tool_name
                self.ai_tools[tool_name] = {
                    "name": tool_name,
                    "description": method._ai_tool_description,
                    "func": method,
                    "parameters": method._ai_tool_parameters,
                }

    # ── Plugins ───────────────────────────────────────────────

    def add_plugin(self, plugin: Plugin) -> Plugin:
        """Add a plugin, registering all of its slash commands and event handlers.

        Returns the plugin instance for method chaining.

        Raises ``TypeError`` if ``plugin`` is not a :class:`Plugin` instance.
        Raises ``ValueError`` if the same plugin instance has already been added.
        """
        if not isinstance(plugin, Plugin):
            raise TypeError(
                f"expected a Plugin instance, got {type(plugin).__name__!r}"
            )
        if plugin in self._plugins:
            raise ValueError(
                f"{type(plugin).__name__} is already added to this bot. "
                "Create a new instance if you need a second copy."
            )
        plugin._bot = self
        self._plugins.append(plugin)
        self._scan_methods(plugin)
        if self.is_ready():
            asyncio.create_task(plugin.on_load())
            self._start_plugin_tasks(plugin)
        return plugin

    def add_plugins(self, *plugins: Plugin) -> None:
        """Add several plugins in one call."""
        for plugin in plugins:
            self.add_plugin(plugin)

    async def remove_plugin(self, plugin: Plugin) -> None:
        """Remove a plugin, deregistering its commands and event handlers.

        Raises ``ValueError`` if the plugin was never added.
        """
        if plugin not in self._plugins:
            raise ValueError(
                f"{type(plugin).__name__} has not been added to this bot. "
                "Call bot.add_plugin() before trying to remove it."
            )
        self._plugins.remove(plugin)
        for _, method in inspect.getmembers(plugin, predicate=inspect.ismethod):
            if getattr(method, "_is_slash", False):
                guild = (
                    discord.Object(id=method._slash_guild)
                    if method._slash_guild
                    else None
                )
                for cmd_name in [method._slash_name] + list(getattr(method, "_slash_aliases", [])):
                    try:
                        self.tree.remove_command(cmd_name, guild=guild)
                    except Exception:  # noqa: BLE001
                        logger.debug(
                            "Could not remove command %r during unload",
                            cmd_name,
                        )
            if getattr(method, "_is_event", False):
                try:
                    self._event_handlers[method._event_name].remove(method)
                except (KeyError, ValueError):
                    pass
            if getattr(method, "_is_user_command", False):
                guild = discord.Object(id=method._context_menu_guild) if method._context_menu_guild else None
                try:
                    self.tree.remove_command(method._context_menu_name, type=discord.AppCommandType.user, guild=guild)
                except Exception:
                    pass
            if getattr(method, "_is_message_command", False):
                guild = discord.Object(id=method._context_menu_guild) if method._context_menu_guild else None
                try:
                    self.tree.remove_command(method._context_menu_name, type=discord.AppCommandType.message, guild=guild)
                except Exception:
                    pass
            if getattr(method, "_is_component", False):
                custom_id = method._component_id
                if getattr(method, "_component_scoped", True):
                    custom_id = plugin.id(custom_id)
                self.registry.components.pop(custom_id, None)
            if getattr(method, "_is_modal", False):
                custom_id = method._modal_id
                if getattr(method, "_modal_scoped", True):
                    custom_id = plugin.id(custom_id)
                self.registry.modals.pop(custom_id, None)
        for handle in self._task_handles.pop(id(plugin), []):
            handle.cancel()
            try:
                await handle
            except asyncio.CancelledError:
                pass
        await plugin.on_unload()

    async def reload_plugin(self, name: str) -> None:
        """Reload a plugin by class name — calls ``on_unload`` then ``on_load`` in-place.

        The same instance is kept, so constructor arguments and in-memory state
        are preserved. Raises ``ValueError`` if no loaded plugin has that class name.
        """
        for plugin in self._plugins:
            if type(plugin).__name__ == name:
                await plugin.on_unload()
                await plugin.on_load()
                return
        raise ValueError(f"No plugin named {name!r} is loaded")

    # ── Background tasks ──────────────────────────────────────

    def _start_plugin_tasks(self, plugin: Plugin) -> None:
        """Start all @task-decorated methods for a plugin."""
        handles = []
        for _, method in inspect.getmembers(plugin, predicate=inspect.ismethod):
            if getattr(method, "_is_task", False):
                handle = asyncio.create_task(
                    self._run_task(method, method._task_interval)
                )
                handles.append(handle)
        if handles:
            self._task_handles[id(plugin)] = handles

    @staticmethod
    async def _run_task(method: Callable, interval: float) -> None:
        """Run a plugin task method in a loop, sleeping between calls."""
        while True:
            try:
                await method()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception(
                    "Error in task %r", getattr(method, "__name__", method)
                )
            await asyncio.sleep(interval)
