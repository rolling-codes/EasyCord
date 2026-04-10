"""
easycord/server_config.py
~~~~~~~~~~~~~~~~~~~~~~~~~
Per-guild configuration store backed by JSON files.

Usage::

    from easycord import ServerConfigStore

    store = ServerConfigStore()

    cfg = await store.load(guild_id)
    cfg.set_role("moderator", 1234567890)
    cfg.set_channel("logs", 9876543210)
    cfg.set_other("prefix", "!")
    await store.save(cfg)
"""

from __future__ import annotations

import asyncio
import copy
import json
import os
from collections import defaultdict
from pathlib import Path
from typing import Any


class ServerConfig:
    """Holds configuration for a single guild."""

    _SCHEMA: dict = {"roles": {}, "channels": {}, "other": {}}

    @staticmethod
    def _normalize(data: object) -> dict:
        """Return a valid config dict, filling in any missing top-level keys."""
        if not isinstance(data, dict):
            return copy.deepcopy(ServerConfig._SCHEMA)
        return {
            "roles": dict(data.get("roles") or {}),
            "channels": dict(data.get("channels") or {}),
            "other": dict(data.get("other") or {}),
        }

    def __init__(self, guild_id: int, data: dict | None = None) -> None:
        self.guild_id = guild_id
        self._data: dict = self._normalize(data)

    # ── Roles ────────────────────────────────────────────────

    def set_role(self, key: str, role_id: int) -> None:
        self._data["roles"][key] = role_id

    def get_role(self, key: str) -> int | None:
        return self._data["roles"].get(key)

    def has_role(self, key: str) -> bool:
        return key in self._data["roles"]

    def remove_role(self, key: str) -> None:
        self._data["roles"].pop(key, None)

    def list_roles(self) -> dict[str, int]:
        return dict(self._data["roles"])

    def clear_roles(self) -> None:
        self._data["roles"].clear()

    # ── Channels ─────────────────────────────────────────────

    def set_channel(self, key: str, channel_id: int) -> None:
        self._data["channels"][key] = channel_id

    def get_channel(self, key: str) -> int | None:
        return self._data["channels"].get(key)

    def has_channel(self, key: str) -> bool:
        return key in self._data["channels"]

    def remove_channel(self, key: str) -> None:
        self._data["channels"].pop(key, None)

    def list_channels(self) -> dict[str, int]:
        return dict(self._data["channels"])

    def clear_channels(self) -> None:
        self._data["channels"].clear()

    # ── Other / feature flags ────────────────────────────────

    def set_other(self, key: str, value: Any) -> None:
        self._data["other"][key] = value

    def get_other(self, key: str, default: Any = None) -> Any:
        return self._data["other"].get(key, default)

    def has_other(self, key: str) -> bool:
        return key in self._data["other"]

    def remove_other(self, key: str) -> None:
        self._data["other"].pop(key, None)

    def list_other(self) -> dict[str, Any]:
        return dict(self._data["other"])

    def clear_other(self) -> None:
        self._data["other"].clear()

    # ── Bulk helpers ─────────────────────────────────────────

    def reset(self) -> None:
        """Wipe all roles, channels, and other settings."""
        self._data = copy.deepcopy(self._SCHEMA)

    def merge(self, other: ServerConfig) -> None:
        """Merge another config into this one. Existing keys are overwritten."""
        self._data["roles"].update(other._data["roles"])
        self._data["channels"].update(other._data["channels"])
        self._data["other"].update(other._data["other"])

    def to_dict(self) -> dict:
        """Return a deep copy of the config data."""
        return copy.deepcopy(self._data)


class ServerConfigStore:
    """
    Loads and saves per-guild config as JSON files.

    Files are written under ``base_dir/<guild_id>.json``.
    Saves are atomic (write-to-temp + rename) and protected by
    per-guild async locks.
    """

    def __init__(self, base_dir: str = ".easycord/server-config") -> None:
        self._base = Path(base_dir)
        self._base.mkdir(parents=True, exist_ok=True)
        self._locks: dict[int, asyncio.Lock] = defaultdict(asyncio.Lock)

    def _path(self, guild_id: int) -> Path:
        return self._base / f"{guild_id}.json"

    async def load(self, guild_id: int) -> ServerConfig:
        """Load config for a guild; returns an empty config if none exists."""
        async with self._locks[guild_id]:
            path = self._path(guild_id)
            if not path.exists():
                return ServerConfig(guild_id)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return ServerConfig(guild_id, data)
            except (json.JSONDecodeError, OSError) as exc:
                raise RuntimeError(
                    f"Failed to load config for guild {guild_id}: {exc}"
                ) from exc

    async def save(self, config: ServerConfig) -> None:
        """Persist a guild's config to disk atomically."""
        async with self._locks[config.guild_id]:
            path = self._path(config.guild_id)
            tmp = path.with_suffix(".tmp")
            try:
                with open(tmp, "w", encoding="utf-8") as f:
                    json.dump(config.to_dict(), f, indent=2)
                os.replace(tmp, path)
            except OSError as exc:
                raise RuntimeError(
                    f"Failed to save config for guild {config.guild_id}: {exc}"
                ) from exc

    async def delete(self, guild_id: int) -> None:
        """Remove a guild's config file entirely."""
        async with self._locks[guild_id]:
            path = self._path(guild_id)
            if path.exists():
                os.remove(path)

    async def exists(self, guild_id: int) -> bool:
        """Return ``True`` if a config file exists for this guild."""
        async with self._locks[guild_id]:
            return self._path(guild_id).exists()
