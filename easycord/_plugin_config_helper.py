"""Simplified config operations for plugins to eliminate repeated store/lock patterns.

Instead of:

    async with self._locks.lock(guild_id):
        cfg = await self._store.load(guild_id)
        data = cfg.get_other("section", {})
        data["key"] = value
        cfg.set_other("section", data)
        await self._store.save(cfg)

You can now write:

    await self.config_set(guild_id, "section", "key", value)
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from .server_config import ServerConfigStore
    from ._shared import GuildLockManager


class PluginConfigHelper:
    """Mixin for Plugin providing simplified config CRUD.
    
    Add this as a base class to any plugin that uses ServerConfigStore +
    GuildLockManager to eliminate the repeated load-mutate-save-lock ceremony.
    
    Example::
    
        class MyPlugin(Plugin, PluginConfigHelper):
            def __init__(self):
                super().__init__()
                self._store = ServerConfigStore(".easycord/my_plugin")
                self._locks = GuildLockManager()
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
    
    # Subclasses must set these
    _store: ServerConfigStore
    _locks: GuildLockManager
    _section_name: str = None  # Defaults to plugin.name if not set
    name: str  # From Plugin base
    
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
            Config section (defaults to plugin name).
        default: Any
            Default value if key is missing.
        
        Returns
        -------
        The config value, or *default* if missing.
        """
        section = section or (self._section_name or self.name)
        cfg = await self._store.load(guild_id)
        data = cfg.get_other(section, {})
        return data.get(key, default)
    
    async def config_set(
        self,
        guild_id: int,
        key: str,
        value: Any,
        section: str | None = None,
    ) -> None:
        """Set a config value atomically.
        
        Parameters
        ----------
        guild_id: int
            Guild to update.
        key: str
            Config key.
        value: Any
            New value.
        section: str
            Config section (defaults to plugin name).
        """
        section = section or (self._section_name or self.name)
        
        async def _apply(cfg: Any) -> None:
            data = cfg.get_other(section, {})
            data[key] = value
            cfg.set_other(section, data)
        
        async with self._locks.lock(guild_id):
            cfg = await self._store.load(guild_id)
            await _apply(cfg)
            await self._store.save(cfg)
    
    async def config_update(
        self,
        guild_id: int,
        updates: dict[str, Any],
        section: str | None = None,
    ) -> None:
        """Update multiple config keys at once.
        
        Parameters
        ----------
        guild_id: int
            Guild to update.
        updates: dict[str, Any]
            Map of key → value to merge.
        section: str
            Config section (defaults to plugin name).
        """
        section = section or (self._section_name or self.name)
        
        async def _apply(cfg: Any) -> None:
            data = cfg.get_other(section, {})
            data.update(updates)
            cfg.set_other(section, data)
        
        async with self._locks.lock(guild_id):
            cfg = await self._store.load(guild_id)
            await _apply(cfg)
            await self._store.save(cfg)
    
    async def config_delete(
        self,
        guild_id: int,
        key: str,
        section: str | None = None,
    ) -> Any:
        """Delete a config key and return its value (or None).
        
        Parameters
        ----------
        guild_id: int
            Guild to update.
        key: str
            Key to delete.
        section: str
            Config section (defaults to plugin name).
        
        Returns
        -------
        The deleted value, or None if not found.
        """
        section = section or (self._section_name or self.name)
        deleted = [None]
        
        async def _apply(cfg: Any) -> None:
            data = cfg.get_other(section, {})
            deleted[0] = data.pop(key, None)
            cfg.set_other(section, data)
        
        async with self._locks.lock(guild_id):
            cfg = await self._store.load(guild_id)
            await _apply(cfg)
            await self._store.save(cfg)
        
        return deleted[0]
    
    async def config_mutate(
        self,
        guild_id: int,
        fn: Callable[[dict[str, Any]], Any],
        section: str | None = None,
    ) -> Any:
        """Apply a custom mutation function to the config section.
        
        The function runs atomically under the per-guild lock. It receives
        the current config dict and can return a result.
        
        Parameters
        ----------
        guild_id: int
            Guild to update.
        fn: Callable[[dict], Any]
            Sync function that takes the config dict, mutates it, and optionally returns a value.
        section: str
            Config section (defaults to plugin name).
        
        Returns
        -------
        The return value of *fn*.
        
        Example::
        
            result = await plugin.config_mutate(
                guild_id,
                lambda cfg: cfg.get("members", []).append(user_id),
            )
        """
        section = section or (self._section_name or self.name)
        result = [None]
        
        async def _apply(cfg: Any) -> None:
            data = cfg.get_other(section, {})
            result[0] = fn(data)
            cfg.set_other(section, data)
        
        async with self._locks.lock(guild_id):
            cfg = await self._store.load(guild_id)
            await _apply(cfg)
            await self._store.save(cfg)
        
        return result[0]
    
    async def config_clear(
        self,
        guild_id: int,
        section: str | None = None,
    ) -> None:
        """Clear all keys in a config section.
        
        Parameters
        ----------
        guild_id: int
            Guild to update.
        section: str
            Config section (defaults to plugin name).
        """
        section = section or (self._section_name or self.name)
        
        async def _apply(cfg: Any) -> None:
            cfg.set_other(section, {})
        
        async with self._locks.lock(guild_id):
            cfg = await self._store.load(guild_id)
            await _apply(cfg)
            await self._store.save(cfg)
