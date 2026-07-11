"""Plugin lifecycle, task management, and shared method-scanner."""
from __future__ import annotations

import asyncio
import inspect
import logging
from typing import TYPE_CHECKING, Any, Callable

import discord

from ._plugin_scanner import scan_plugin_methods

if TYPE_CHECKING:
    from ._bot_base import _BotBase
    from .plugin import Plugin  # cyclic at type-check time only; never imported at runtime, and
    # `from __future__ import annotations` keeps every reference to it a deferred string

    _MixinBase = _BotBase
else:
    _MixinBase = object

logger = logging.getLogger("easycord")


class PluginDependencyError(RuntimeError):
    """Raised when a plugin's declared dependencies are not yet loaded.

    Check the ``missing`` attribute for the list of missing plugin names.

    Example::

        try:
            bot.add_plugin(InventoryPlugin())
        except PluginDependencyError as e:
            print(f"Load {e.missing} first")
    """

    def __init__(self, plugin_class: str, missing: list[str]) -> None:
        self.plugin_class = plugin_class
        self.missing = missing
        super().__init__(
            f"{plugin_class} requires plugins {missing!r} to be loaded first. "
            "Call add_plugin() in dependency order."
        )


def _iter_methods(plugin: object) -> list[tuple[str, Any]]:
    """Return ``(name, method)`` pairs for *plugin*'s bound methods.

    ``inspect.ismethod`` is typed as a ``TypeGuard[MethodType]``, so static
    checkers forget the decorator-added attributes (``_slash_name`` etc.) that
    the scanner reads.  Returning the pairs as ``Any`` keeps those dynamic
    attribute accesses clean without a ``getattr`` call on every line.
    """
    return inspect.getmembers(plugin, predicate=inspect.ismethod)


class _PluginsMixin(_MixinBase):
    """Mixin: plugin add/remove, background tasks, and method scanning."""

    # ── Shared scanner ────────────────────────────────────────

    def _scan_methods(self, plugin: Plugin, *, parent=None) -> None:
        """Register all @slash and @on methods on *plugin*.

        parent: an ``app_commands.Group`` — when supplied, slash commands are
        added to the group instead of the command tree (used by add_group).
        """
        scan_plugin_methods(self, plugin, iter_methods=_iter_methods, parent=parent)

    # ── Plugins ───────────────────────────────────────────────

    def add_plugin(self, plugin: Plugin):
        """Add a plugin, registering all of its slash commands and event handlers.

        Returns self for method chaining multiple plugins.

        Raises ``TypeError`` if ``plugin`` is not a :class:`Plugin` instance.
        Raises ``ValueError`` if the same plugin instance has already been added.
        """
        from .plugin import Plugin  # local import keeps the module-level graph acyclic

        if not isinstance(plugin, Plugin):
            raise TypeError(
                f"expected a Plugin instance, got {type(plugin).__name__!r}"
            )
        if plugin in self._plugins:
            raise ValueError(
                f"{type(plugin).__name__} is already added to this bot. "
                "Create a new instance if you need a second copy."
            )
        required: tuple[str, ...] = getattr(type(plugin), "requires", ())
        if required:
            loaded_names = {p.name for p in self._plugins}
            missing = [n for n in required if n not in loaded_names]
            if missing:
                raise PluginDependencyError(type(plugin).__name__, missing)
        plugin._bot = self  # type: ignore[assignment]  # ``self`` is the composed Bot at runtime
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
        for _, method in _iter_methods(plugin):
            if getattr(method, "_is_slash", False):
                guild = (
                    discord.Object(id=method._slash_guild)
                    if method._slash_guild
                    else None
                )
                for cmd_name in [method._slash_name] + list(getattr(method, "_slash_aliases", [])):
                    _existing_cmd = self.tree.get_command(cmd_name, guild=guild)
                    if _existing_cmd is not None:
                        _entry = getattr(
                            getattr(_existing_cmd, "callback", None),
                            "_cooldown_registry_entry",
                            None,
                        )
                        if _entry is not None:
                            _registries = getattr(self, "_cooldown_registries", None)
                            if _registries is not None:
                                try:
                                    _registries.remove(_entry)
                                except ValueError:
                                    pass
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
                    pass  # Handler not registered or already removed
            if getattr(method, "_is_user_command", False):
                guild = discord.Object(id=method._context_menu_guild) if method._context_menu_guild else None
                try:
                    self.tree.remove_command(method._context_menu_name, type=discord.AppCommandType.user, guild=guild)
                except Exception:  # noqa: BLE001
                    logger.debug(
                        "Could not remove user command %r during unload",
                        method._context_menu_name,
                    )
            if getattr(method, "_is_message_command", False):
                guild = discord.Object(id=method._context_menu_guild) if method._context_menu_guild else None
                try:
                    self.tree.remove_command(method._context_menu_name, type=discord.AppCommandType.message, guild=guild)
                except Exception:  # noqa: BLE001
                    logger.debug(
                        "Could not remove message command %r during unload",
                        method._context_menu_name,
                    )
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
            if getattr(method, "_is_subscription", False):
                event_bus = getattr(self, "event_bus", None)
                if event_bus is not None:
                    event_bus.unsubscribe(method._subscription_event, method)
        self.registry.unregister_plugin(getattr(plugin, "_instance_id", str(id(plugin))))
        for handle in self._task_handles.pop(id(plugin), []):
            handle.cancel()
            try:
                await handle
            except asyncio.CancelledError:
                pass  # Task was cancelled as expected
            except Exception as e:
                logger.warning("Task raised during plugin unload: %r", e)
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

    def _get_reload_lock(self) -> asyncio.Lock:
        """Return the bot-wide hot-reload lock, creating it on first use.

        The lock serializes a plugin swap (``remove_plugin`` → ``add_plugin`` →
        ``on_reload``) against command dispatch so an interaction can never land
        in the window where the old plugin's commands are unregistered but the
        new ones are not yet installed. ``asyncio.Lock`` does not bind to a loop
        at construction (3.10+), so lazy creation here is safe.
        """
        lock = getattr(self, "_reload_lock", None)
        if lock is None:
            lock = asyncio.Lock()
            self._reload_lock = lock
        return lock

    async def _hot_reload_plugin(self, plugin: Plugin) -> None:
        """Reload a plugin's module code and reinstall it, replacing the running instance.

        Plugins with ``__init__`` arguments cannot be re-instantiated automatically;
        an error is logged and the original instance is kept intact.
        """
        import importlib

        logger.debug("Hot-reload triggered for plugin: %s", plugin.name)
        module = inspect.getmodule(type(plugin))
        if module is None:
            logger.error(
                "Hot-reload failed for %s: cannot determine module", plugin.name
            )
            return
        cls_name = type(plugin).__name__
        try:
            new_module = importlib.reload(module)
            NewClass = getattr(new_module, cls_name)
            init_sig = inspect.signature(NewClass.__init__)
            required_params = [
                name
                for name, p in init_sig.parameters.items()
                if name != "self"
                and p.default is inspect.Parameter.empty
                and p.kind not in (
                    inspect.Parameter.VAR_POSITIONAL,
                    inspect.Parameter.VAR_KEYWORD,
                )
            ]
            if required_params:
                logger.error(
                    "Hot-reload skipped for %s: __init__ requires args %s — "
                    "reload manually or use Plugin.on_reload() for state migration",
                    plugin.name,
                    required_params,
                )
                return
            new_instance = NewClass()
        except Exception as exc:
            logger.error(
                "Hot-reload failed for %s: %s: %s",
                plugin.name, type(exc).__name__, exc,
            )
            return
        # Serialize the swap against command dispatch: while this lock is held,
        # callbacks gated on it (see build_slash_callback) wait, so no
        # interaction runs against the half-removed registry.
        async with self._get_reload_lock():
            await self.remove_plugin(plugin)
            self.add_plugin(new_instance)
            logger.info("Plugin reloaded: %s", plugin.name)
            await new_instance.on_reload()

    async def _hot_reload_loop(self) -> None:
        """Poll plugin files every second and hot-reload any whose mtime changed."""
        import os

        # Mark hot-reload as active so command dispatch acquires the reload lock
        # (cheap, uncontended). When the loop never runs — i.e. production — the
        # flag stays falsy and dispatch keeps its lock-free fast path.
        self._hot_reload_active = True
        self._get_reload_lock()  # ensure the lock exists before any dispatch
        mtimes: dict[str, float] = {}
        while True:
            await asyncio.sleep(3)
            for plugin in list(self._plugins):
                try:
                    path = inspect.getfile(type(plugin))
                    mtime = os.path.getmtime(path)
                    if path not in mtimes:
                        mtimes[path] = mtime  # seed on first pass — no reload
                    elif mtimes[path] != mtime:
                        mtimes[path] = mtime
                        await self._hot_reload_plugin(plugin)
                except Exception as exc:
                    logger.warning("Hot-reload watcher error: %s", exc)

    # ── Background tasks ──────────────────────────────────────

    def _start_plugin_tasks(self, plugin: Plugin) -> None:
        """Start all @task-decorated methods for a plugin."""
        existing = self._task_handles.get(id(plugin), [])
        active = [handle for handle in existing if not handle.done()]
        if active:
            self._task_handles[id(plugin)] = active
            return

        handles = []
        for _, method in _iter_methods(plugin):
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

    # ── Per-guild plugin feature flags ───────────────────────────

    def disable_plugin(self, name: str, guild_id: int) -> None:
        """Disable a named plugin for a specific guild.

        Any slash command whose ``source`` plugin matches *name* will return an
        ephemeral "disabled in this server" response when invoked from *guild_id*.
        In-memory only — does not persist across restarts.

        Example::

            bot.disable_plugin("economy", guild_id=123456)
        """
        disabled: dict[int, set[str]] = getattr(self, "_guild_disabled_plugins", {})
        disabled.setdefault(guild_id, set()).add(name)
        self._guild_disabled_plugins = disabled  # type: ignore[attr-defined]

    def enable_plugin(self, name: str, guild_id: int) -> None:
        """Re-enable a plugin that was disabled for a specific guild.

        No-op if the plugin was not disabled for that guild.
        """
        disabled: dict[int, set[str]] = getattr(self, "_guild_disabled_plugins", {})
        if guild_id in disabled:
            disabled[guild_id].discard(name)

    def is_plugin_enabled(self, name: str, guild_id: int) -> bool:
        """Return ``True`` if the named plugin is enabled for *guild_id*.

        Defaults to ``True`` — plugins are enabled unless explicitly disabled.
        """
        disabled: dict[int, set[str]] = getattr(self, "_guild_disabled_plugins", {})
        return name not in disabled.get(guild_id, set())

    def _validate_plugin_permissions(self, plugin: Plugin) -> None:
        """Warn if the bot lacks Discord permissions required by the plugin's commands.

        Iterates over every ``@slash``-decorated method on *plugin* and checks
        whether the bot's member permissions in each relevant guild satisfy the
        ``permissions=`` list declared on the command.  Called from ``on_ready``
        once the guild list is populated.

        Only runs when the bot is in at least one guild; skips silently otherwise.
        """
        guilds = list(getattr(self, "guilds", []))
        if not guilds:
            return

        plugin_name = getattr(plugin, "name", type(plugin).__name__)

        for _, method in _iter_methods(plugin):
            if not getattr(method, "_is_slash", False):
                continue

            required_perms: list[str] | None = getattr(method, "_slash_permissions", None)
            require_admin: bool = getattr(method, "_slash_require_admin", False)
            bot_required: list[str] | None = getattr(method, "_slash_bot_permissions", None)

            # Build effective permission list — the perms the bot must hold for the
            # command to work. Includes user-declared perms (legacy behavior) plus
            # any explicit bot_permissions=, so this startup warning stays aligned
            # with the dispatch-time block in build_slash_callback.
            effective: list[str] = []
            if require_admin:
                effective.append("administrator")
            if required_perms:
                effective.extend(required_perms)
            if bot_required:
                effective.extend(p for p in bot_required if p not in effective)
            if not effective:
                continue

            command_name = getattr(method, "_slash_name", method.__name__)
            guild_id: int | None = getattr(method, "_slash_guild", None)

            # Determine which guilds to check
            if guild_id is not None:
                target_guilds = [g for g in guilds if g.id == guild_id]
            else:
                target_guilds = guilds

            for guild in target_guilds:
                # Retrieve the bot's Member object in this guild
                me = guild.me
                if me is None:
                    continue
                bot_perms: discord.Permissions = me.guild_permissions
                for perm in effective:
                    if not getattr(bot_perms, perm, False):
                        logger.warning(
                            "Plugin %r requires %r permission but bot lacks it "
                            "in guild %r (ID: %s) — command /%s may not work as expected",
                            plugin_name,
                            perm,
                            guild.name,
                            guild.id,
                            command_name,
                        )
