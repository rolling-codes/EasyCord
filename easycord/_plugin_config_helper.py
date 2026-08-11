"""Simplified config operations for plugins to eliminate repeated store/lock patterns.

Instead of:

    async with self._locks.lock(guild_id):
        cfg = await self._store.load(guild_id)
        data = cfg.get_other("section", {})
        data["key"] = value
        cfg.set_other("section", data)
        await self._store.save(cfg)

you can write:

    await self.config_set(guild_id, "key", value, section="section")

Every write routes through :meth:`ServerConfigStore.mutate`, so the whole
load-modify-save runs under the store's per-guild lock — the same single lock
domain every other ``mutate`` caller uses, with no lost updates. Because the
store owns the lock, the mixin needs only a ``_store``; it does not manage its
own locks.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from .server_config import ServerConfig, ServerConfigStore


class PluginConfigHelper:
    """Mixin for Plugin providing simplified, atomic config CRUD.

    Add this as a base class to any plugin backed by a ``ServerConfigStore`` to
    eliminate the repeated load-modify-save ceremony. Every write goes through
    :meth:`ServerConfigStore.mutate`, so it is atomic under the store's own
    per-guild lock — you do not create or manage a separate lock.

    Example::

        class MyPlugin(Plugin, PluginConfigHelper):
            def __init__(self):
                super().__init__()
                self._store = ServerConfigStore(".easycord/my_plugin")
                self._section_name = "my_plugin"  # optional: defaults to plugin.name

            @slash(description="Set a value")
            async def set_config(self, ctx, key: str, value: str):
                await self.config_set(ctx.guild.id, key, value)
                await ctx.respond(f"Set {key} = {value}")

            @slash(description="Get a value")
            async def get_config(self, ctx, key: str):
                value = await self.config_get(ctx.guild.id, key)
                await ctx.respond(f"{key} = {value}")
    """

    # Subclasses must set _store. _section_name defaults to the plugin name.
    _store: ServerConfigStore
    _section_name: str | None = None
    name: str  # From Plugin base

    def _resolve_section(self, section: str | None) -> str:
        return section or (self._section_name or self.name)

    def _require_store(self) -> ServerConfigStore:
        store = getattr(self, "_store", None)
        if store is None:
            raise RuntimeError(
                f"{type(self).__name__} uses PluginConfigHelper but never set "
                "self._store; assign a ServerConfigStore in __init__()."
            )
        return store

    async def config_get(
        self,
        guild_id: int,
        key: str,
        section: str | None = None,
        default: Any = None,
    ) -> Any:
        """Fetch a config value.

        Parameters
        ----------
        guild_id: int
            Guild to load config from.
        key: str
            Config key.
        section: str
            Config section (defaults to the plugin name).
        default: Any
            Value returned if the key is missing.

        Returns
        -------
        The config value, or *default* if missing.
        """
        store = self._require_store()
        section = self._resolve_section(section)
        cfg = await store.load(guild_id)
        return cfg.get_other(section, {}).get(key, default)

    async def config_set(
        self,
        guild_id: int,
        key: str,
        value: Any,
        section: str | None = None,
    ) -> None:
        """Set a single config value atomically.

        Parameters
        ----------
        guild_id: int
            Guild to update.
        key: str
            Config key.
        value: Any
            New value.
        section: str
            Config section (defaults to the plugin name).
        """
        store = self._require_store()
        section = self._resolve_section(section)

        def _apply(cfg: ServerConfig) -> None:
            data = cfg.get_other(section, {})
            data[key] = value
            cfg.set_other(section, data)

        await store.mutate(guild_id, _apply)

    async def config_update(
        self,
        guild_id: int,
        updates: dict[str, Any],
        section: str | None = None,
    ) -> None:
        """Merge multiple config keys at once, atomically.

        Parameters
        ----------
        guild_id: int
            Guild to update.
        updates: dict[str, Any]
            Map of key → value to merge into the section.
        section: str
            Config section (defaults to the plugin name).
        """
        store = self._require_store()
        section = self._resolve_section(section)

        def _apply(cfg: ServerConfig) -> None:
            data = cfg.get_other(section, {})
            data.update(updates)
            cfg.set_other(section, data)

        await store.mutate(guild_id, _apply)

    async def config_delete(
        self,
        guild_id: int,
        key: str,
        section: str | None = None,
    ) -> Any:
        """Delete a config key and return its previous value (or ``None``).

        Parameters
        ----------
        guild_id: int
            Guild to update.
        key: str
            Key to delete.
        section: str
            Config section (defaults to the plugin name).

        Returns
        -------
        The deleted value, or ``None`` if it was not present.
        """
        store = self._require_store()
        section = self._resolve_section(section)

        def _apply(cfg: ServerConfig) -> Any:
            data = cfg.get_other(section, {})
            deleted = data.pop(key, None)
            cfg.set_other(section, data)
            return deleted

        return await store.mutate(guild_id, _apply)

    async def config_mutate(
        self,
        guild_id: int,
        fn: Callable[[dict[str, Any]], Any],
        section: str | None = None,
    ) -> Any:
        """Apply a custom mutation to the config section, atomically.

        *fn* runs under the store's per-guild lock. It receives the current
        section dict, mutates it in place, and may return a value.

        Parameters
        ----------
        guild_id: int
            Guild to update.
        fn: Callable[[dict], Any]
            Fast, synchronous function that takes the section dict and mutates
            it. Do not perform network I/O inside *fn* — it runs under the lock.
        section: str
            Config section (defaults to the plugin name).

        Returns
        -------
        The return value of *fn*.

        Example::

            def add_member(data: dict) -> int:
                members = data.setdefault("members", [])
                members.append(user_id)
                return len(members)  # config_mutate returns this

            count = await plugin.config_mutate(guild_id, add_member)
        """
        store = self._require_store()
        section = self._resolve_section(section)

        def _apply(cfg: ServerConfig) -> Any:
            data = cfg.get_other(section, {})
            result = fn(data)
            cfg.set_other(section, data)
            return result

        return await store.mutate(guild_id, _apply)

    async def config_clear(
        self,
        guild_id: int,
        section: str | None = None,
    ) -> None:
        """Clear all keys in a config section, atomically.

        Parameters
        ----------
        guild_id: int
            Guild to update.
        section: str
            Config section (defaults to the plugin name).
        """
        store = self._require_store()
        section = self._resolve_section(section)

        def _apply(cfg: ServerConfig) -> None:
            cfg.set_other(section, {})

        await store.mutate(guild_id, _apply)
