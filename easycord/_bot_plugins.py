"""Plugin lifecycle, task management, and shared method-scanner."""
from __future__ import annotations

import asyncio
import inspect
import logging
from typing import Callable

import discord

from .plugin import Plugin
from .tool_limits import RateLimit
from .tools import ToolSafety

logger = logging.getLogger("easycord")


class _PluginsMixin:
    """Mixin: plugin add/remove, background tasks, and method scanning."""

    # ── Shared scanner ────────────────────────────────────────

    def _scan_methods(self, plugin: Plugin, *, parent=None) -> None:
        """Register all @slash and @on methods on *plugin*.

        parent: an ``app_commands.Group`` — when supplied, slash commands are
        added to the group instead of the command tree (used by add_group).
        """
        plugin_name = getattr(plugin, "_instance_id", str(id(plugin)))
        standalone_autocomplete: dict[str, dict[str, Callable]] = {}
        for _, method in inspect.getmembers(plugin, predicate=inspect.ismethod):
            if getattr(method, "_is_autocomplete", False):
                standalone_autocomplete.setdefault(
                    method._autocomplete_command,
                    {},
                )[method._autocomplete_option] = method

        for _, method in inspect.getmembers(plugin, predicate=inspect.ismethod):
            if getattr(method, "_is_slash", False):
                autocomplete_handlers = {
                    **getattr(method, "_slash_autocomplete", {}),
                    **standalone_autocomplete.get(method._slash_name, {}),
                }
                self._register_slash(
                    method,
                    name=method._slash_name,
                    description=method._slash_desc,
                    guild_id=method._slash_guild,
                    guild_only=getattr(method, "_slash_guild_only", False),
                    require_admin=getattr(method, "_slash_require_admin", False),
                    ephemeral=getattr(method, "_slash_ephemeral", False),
                    permissions=getattr(method, "_slash_permissions", None),
                    cooldown=getattr(method, "_slash_cooldown", None),
                    cooldown_rate=getattr(method, "_slash_cooldown_rate", 1),
                    cooldown_bucket=getattr(method, "_slash_cooldown_bucket", "user"),
                    premium_required=getattr(method, "_slash_premium_required", False),
                    autocomplete=autocomplete_handlers,
                    choices=getattr(method, "_slash_choices", None),
                    nsfw=getattr(method, "_slash_nsfw", False),
                    allowed_contexts=getattr(method, "_slash_allowed_contexts", None),
                    allowed_installs=getattr(method, "_slash_allowed_installs", None),
                    parent=parent,
                    source_plugin=plugin_name,
                )
                for alias in getattr(method, "_slash_aliases", []):
                    self._register_slash(
                        method,
                        name=alias,
                        description=method._slash_desc,
                        guild_id=method._slash_guild,
                        guild_only=getattr(method, "_slash_guild_only", False),
                        require_admin=getattr(method, "_slash_require_admin", False),
                        ephemeral=getattr(method, "_slash_ephemeral", False),
                        permissions=getattr(method, "_slash_permissions", None),
                        cooldown=getattr(method, "_slash_cooldown", None),
                        cooldown_rate=getattr(method, "_slash_cooldown_rate", 1),
                        cooldown_bucket=getattr(method, "_slash_cooldown_bucket", "user"),
                        premium_required=getattr(method, "_slash_premium_required", False),
                        autocomplete=autocomplete_handlers,
                        choices=getattr(method, "_slash_choices", None),
                        nsfw=getattr(method, "_slash_nsfw", False),
                        allowed_contexts=getattr(method, "_slash_allowed_contexts", None),
                        allowed_installs=getattr(method, "_slash_allowed_installs", None),
                        parent=parent,
                        source_plugin=plugin_name,
                    )
            if getattr(method, "_is_command_error", False):
                self._command_error_handlers[method._command_error_for] = method
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
                    nsfw=getattr(method, "_context_menu_nsfw", False),
                    allowed_contexts=getattr(method, "_context_menu_allowed_contexts", None),
                    allowed_installs=getattr(method, "_context_menu_allowed_installs", None),
                    source_plugin=plugin_name,
                )
            if getattr(method, "_is_message_command", False):
                self._register_context_menu(
                    method,
                    name=method._context_menu_name,
                    menu_type=discord.AppCommandType.message,
                    guild_id=method._context_menu_guild,
                    nsfw=getattr(method, "_context_menu_nsfw", False),
                    allowed_contexts=getattr(method, "_context_menu_allowed_contexts", None),
                    allowed_installs=getattr(method, "_context_menu_allowed_installs", None),
                    source_plugin=plugin_name,
                )
            if getattr(method, "_is_component", False):
                custom_id = method._component_id
                if getattr(method, "_component_scoped", True):
                    custom_id = plugin.id(custom_id)
                self._register_component_handler(
                    custom_id,
                    method,
                    source_plugin=plugin_name,
                    ttl=getattr(method, "_component_ttl", None),
                )
            if getattr(method, "_is_modal", False):
                custom_id = method._modal_id
                if getattr(method, "_modal_scoped", True):
                    custom_id = plugin.id(custom_id)
                self._register_modal_handler(custom_id, method, source_plugin=plugin_name)
            if getattr(method, "_is_ai_tool", False):
                tool_name = method._ai_tool_name
                rate_limit = getattr(method, "_ai_tool_rate_limit", None)
                rate_limit_obj = (
                    RateLimit(max_calls=rate_limit[0], window_minutes=rate_limit[1])
                    if rate_limit
                    else None
                )
                safety = getattr(method, "_ai_tool_safety", ToolSafety.SAFE)
                self.ai_tools[tool_name] = {
                    "name": tool_name,
                    "description": method._ai_tool_description,
                    "func": method,
                    "parameters": method._ai_tool_parameters,
                    "safety": safety,
                    "require_guild": getattr(method, "_ai_tool_require_guild", True),
                    "require_admin": getattr(method, "_ai_tool_require_admin", False),
                    "allowed_roles": getattr(method, "_ai_tool_allowed_roles", []),
                    "allowed_users": getattr(method, "_ai_tool_allowed_users", []),
                    "timeout_ms": getattr(method, "_ai_tool_timeout_ms", 5000),
                    "rate_limit": rate_limit_obj,
                }
                if tool_name not in self.tool_registry._tools:
                    self.tool_registry.register(
                        name=tool_name,
                        func=method,
                        description=method._ai_tool_description,
                        safety=safety,
                        parameters=method._ai_tool_parameters,
                        require_guild=getattr(method, "_ai_tool_require_guild", True),
                        require_admin=getattr(method, "_ai_tool_require_admin", False),
                        allowed_roles=getattr(method, "_ai_tool_allowed_roles", []),
                        allowed_users=getattr(method, "_ai_tool_allowed_users", []),
                        permissions=getattr(method, "_ai_tool_permissions", []),
                        timeout_ms=getattr(method, "_ai_tool_timeout_ms", 5000),
                        rate_limit=rate_limit_obj,
                    )
                if safety is ToolSafety.RESTRICTED:
                    self.tool_registry.disable(tool_name)

    # ── Plugins ───────────────────────────────────────────────

    def add_plugin(self, plugin: Plugin):
        """Add a plugin, registering all of its slash commands and event handlers.

        Returns self for method chaining multiple plugins.

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
            # Schedule on_load and task startup as a single sequential coroutine
            # so that background tasks never fire before on_load() finishes.
            async def _load_then_start(p: Plugin) -> None:
                await p.on_load()
                self._start_plugin_tasks(p)

            task = asyncio.create_task(_load_then_start(plugin))
            background_tasks = getattr(self, "_background_tasks", None)
            if background_tasks is not None:
                background_tasks.add(task)
                task.add_done_callback(background_tasks.discard)
            task.add_done_callback(self._log_task_exception)
        return self

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
        self.registry.unregister_plugin(getattr(plugin, "_instance_id", str(id(plugin))))
        for handle in self._task_handles.pop(id(plugin), []):
            handle.cancel()
            try:
                await handle
            except asyncio.CancelledError:
                pass
        for key, status in getattr(self, "_task_statuses", {}).items():
            if key.startswith(f"{getattr(plugin, '_instance_id', str(id(plugin)))}."):
                status["state"] = "stopped"
        await plugin.on_unload()

    async def reload_plugin(self, name: str) -> None:
        """Reload a plugin by class name — calls ``on_unload`` then ``on_load`` in-place.

        The same instance is kept, so constructor arguments and in-memory state
        are preserved. Raises ``ValueError`` if no loaded plugin has that class name.
        """
        for plugin in self._plugins:
            if getattr(plugin, "_instance_id", type(plugin).__name__) == name or type(plugin).__name__ == name:
                await plugin.on_unload()
                await plugin.on_load()
                return
        raise ValueError(f"No plugin named {name!r} is loaded")

    # ── Background tasks ──────────────────────────────────────

    def _start_plugin_tasks(self, plugin: Plugin) -> None:
        """Start all @task-decorated methods for a plugin."""
        existing = self._task_handles.get(id(plugin), [])
        active = [handle for handle in existing if not handle.done()]
        if active:
            self._task_handles[id(plugin)] = active
            return

        handles = []
        for _, method in inspect.getmembers(plugin, predicate=inspect.ismethod):
            if getattr(method, "_is_task", False):
                plugin_id = getattr(plugin, "_instance_id", str(id(plugin)))
                key = f"{plugin_id}.{method.__name__}"
                self._task_statuses.setdefault(
                    key,
                    {
                        "state": "stopped",
                        "restart_count": 0,
                        "last_error": None,
                        "plugin": plugin_id,
                        "task": method.__name__,
                    },
                )
                handle = asyncio.create_task(
                    self._run_task(
                        method,
                        method._task_interval,
                        key=key,
                        restart=getattr(method, "_task_restart", False),
                        backoff=getattr(method, "_task_backoff", 1.0),
                    )
                )
                handles.append(handle)
        if handles:
            self._task_handles[id(plugin)] = handles

    async def _run_task(
        self,
        method: Callable,
        interval: float,
        *,
        key: str,
        restart: bool,
        backoff: float,
    ) -> None:
        """Run a plugin task method in a loop, sleeping between calls."""
        status = self._task_statuses[key]
        status["state"] = "running"
        while True:
            try:
                await method()
            except asyncio.CancelledError:
                status["state"] = "stopped"
                raise
            except Exception as exc:
                status["state"] = "failed"
                status["last_error"] = repr(exc)
                plugin_name = status.get("plugin")
                if isinstance(plugin_name, str):
                    await self._dispatch_framework_error(exc, ctx=None, plugin_name=plugin_name)
                else:
                    await self._dispatch_framework_error(exc, ctx=None, plugin_instance=getattr(method, "__self__", None))
                if not restart:
                    return
                status["restart_count"] += 1
                await asyncio.sleep(backoff)
                status["state"] = "running"
            await asyncio.sleep(interval)

    def task_statuses(self) -> dict[str, dict[str, object]]:
        """Return status snapshots for plugin background tasks."""
        return {
            key: dict(value)
            for key, value in getattr(self, "_task_statuses", {}).items()
        }
