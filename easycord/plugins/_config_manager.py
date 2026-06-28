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
        """Get config section, creating it with defaults if absent.

        The common case (section already present) is a pure read with no write,
        so hot callers that ``get`` on every event don't trigger a disk write.
        Default creation is funneled through an atomic :meth:`ServerConfigStore.mutate`
        so two concurrent first-time callers can't lose each other's section.
        """
        cfg_obj = await self.store.load(guild_id)
        existing = cfg_obj.get_other(key)
        if existing:
            return existing

        def _create(cfg) -> dict[str, Any]:
            current = cfg.get_other(key)
            if current:
                return current
            created = (defaults or {}).copy()
            cfg.set_other(key, created)
            return created

        return await self.store.mutate(guild_id, _create)

    async def update(self, guild_id: int, key: str, **updates) -> dict[str, Any]:
        """Update config section atomically (load-modify-save under the guild lock)."""
        def _apply(cfg) -> dict[str, Any]:
            section = cfg.get_other(key) or {}
            section.update(updates)
            cfg.set_other(key, section)
            return section

        return await self.store.mutate(guild_id, _apply)

    async def set_default(self, guild_id: int, key: str, defaults: dict[str, Any]) -> None:
        """Ensure config exists with defaults (idempotent, atomic)."""
        def _apply(cfg) -> None:
            if not cfg.get_other(key):
                cfg.set_other(key, defaults.copy())

        await self.store.mutate(guild_id, _apply)
