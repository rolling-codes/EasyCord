"""Shared configuration management for plugins."""
from __future__ import annotations

from typing import Any, TYPE_CHECKING

from easycord.server_config import ServerConfigStore

if TYPE_CHECKING:
    pass


class PluginConfigManager:
    """Centralized config management for plugins using ServerConfigStore."""

    def __init__(self, store_path: str):
        """Initialize with store path (e.g., ".easycord/my-plugin")."""
        self.store = ServerConfigStore(store_path)

    async def get(self, guild_id: int, key: str, defaults: dict[str, Any] | None = None) -> dict[str, Any]:
        """Get config section or create with defaults."""
        cfg_obj = await self.store.load(guild_id)
        cfg = cfg_obj.get_other(key)
        if not cfg:
            cfg = (defaults or {}).copy()
            cfg_obj.set_other(key, cfg)
            await self.store.save(cfg_obj)
        return cfg

    async def update(self, guild_id: int, key: str, **updates) -> dict[str, Any]:
        """Update config section atomically."""
        cfg_obj = await self.store.load(guild_id)
        cfg = cfg_obj.get_other(key) or {}
        cfg.update(updates)
        cfg_obj.set_other(key, cfg)
        await self.store.save(cfg_obj)
        return cfg

    async def set_default(self, guild_id: int, key: str, defaults: dict[str, Any]) -> None:
        """Ensure config exists with defaults (idempotent)."""
        cfg_obj = await self.store.load(guild_id)
        if not cfg_obj.get_other(key):
            cfg_obj.set_other(key, defaults.copy())
            await self.store.save(cfg_obj)
