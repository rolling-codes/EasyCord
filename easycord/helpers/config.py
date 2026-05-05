"""ServerConfigStore helper shortcuts."""
from __future__ import annotations

from typing import Any

from easycord.server_config import ServerConfig, ServerConfigStore


class ConfigHelpers:
    """Shortcuts for ServerConfigStore operations."""

    @staticmethod
    async def load_or_default(guild_id: int, store_path: str, defaults: dict[str, Any]) -> dict[str, Any]:
        """Load config or return defaults if missing."""
        store = ServerConfigStore(store_path)
        cfg_obj = await store.load(guild_id)
        cfg = cfg_obj.get_other("config")
        if not cfg:
            cfg = defaults.copy()
            cfg_obj.set_other("config", cfg)
            await store.save(cfg_obj)
        return cfg

    @staticmethod
    async def update_atomic(guild_id: int, store_path: str, updates: dict[str, Any]) -> dict[str, Any]:
        """Atomically update config with dict of changes."""
        store = ServerConfigStore(store_path)
        cfg_obj = await store.load(guild_id)
        cfg = cfg_obj.get_other("config") or {}
        cfg.update(updates)
        cfg_obj.set_other("config", cfg)
        await store.save(cfg_obj)
        return cfg

    @staticmethod
    async def load_all_guilds(store_path: str) -> dict[int, dict[str, Any]]:
        """Load config for all guilds (requires listing directory)."""
        import os

        results = {}
        store = ServerConfigStore(store_path)

        # List all guild files in store path
        if os.path.exists(store_path):
            for filename in os.listdir(store_path):
                if filename.endswith(".json"):
                    try:
                        guild_id = int(filename.replace(".json", ""))
                        cfg_obj = await store.load(guild_id)
                        cfg = cfg_obj.get_other("config") or {}
                        results[guild_id] = cfg
                    except (ValueError, Exception):
                        pass

        return results

    @staticmethod
    async def get_or_create(
        guild_id: int, store_path: str, key: str, defaults: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Get config section or create with defaults."""
        store = ServerConfigStore(store_path)
        cfg_obj = await store.load(guild_id)
        section = cfg_obj.get_other(key)
        if not section:
            section = (defaults or {}).copy()
            cfg_obj.set_other(key, section)
            await store.save(cfg_obj)
        return section
