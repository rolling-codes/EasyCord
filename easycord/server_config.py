"""Per-guild configuration store backed by JSON files."""
from __future__ import annotations

import asyncio
import contextlib
import copy
import json
import os
from collections import defaultdict
from pathlib import Path
from typing import Any


class ServerConfig:  # pylint: disable=too-many-public-methods
    """Holds configuration for a single guild.

    Usage::

        cfg = await store.load(guild_id)
        cfg.set_role("moderator", 1234567890)
        cfg.set_channel("logs", 9876543210)
        cfg.set_other("prefix", "!")
        await store.save(cfg)
    """

    _SCHEMA: dict = {"roles": {}, "channels": {}, "other": {}}

    def __init__(self, guild_id: int, data: dict | None = None) -> None:
        self.guild_id = guild_id
        self._data: dict = self._normalize(data)

    @staticmethod
    def _normalize(data: object) -> dict:
        if not isinstance(data, dict):
            return copy.deepcopy(ServerConfig._SCHEMA)
        normalized = copy.deepcopy(ServerConfig._SCHEMA)
        for section in ("roles", "channels", "other"):
            raw_section = data.get(section)
            if raw_section is None:
                continue
            try:
                normalized[section] = copy.deepcopy(dict(raw_section))
            except (TypeError, ValueError):
                normalized[section] = {}
        return normalized

    def _s(self, section: str) -> dict:
        return self._data[section]

    # ── Roles ─────────────────────────────────────────────────

    def set_role(self, key: str, role_id: int) -> None:
        """Store a role ID under a named key."""
        self._s("roles")[key] = role_id

    def get_role(self, key: str) -> int | None:
        """Return the role ID for a key, or ``None``."""
        return self._s("roles").get(key)

    def has_role(self, key: str) -> bool:
        """Return ``True`` if the key exists."""
        return key in self._s("roles")

    def remove_role(self, key: str) -> None:
        """Delete a role entry (no-op if missing)."""
        self._s("roles").pop(key, None)

    def list_roles(self) -> dict[str, int]:
        """Return a copy of all role entries."""
        return dict(self._s("roles"))

    def clear_roles(self) -> None:
        """Remove all role entries."""
        self._s("roles").clear()

    # ── Channels ──────────────────────────────────────────────

    def set_channel(self, key: str, channel_id: int) -> None:
        """Store a channel ID under a named key."""
        self._s("channels")[key] = channel_id

    def get_channel(self, key: str) -> int | None:
        """Return the channel ID for a key, or ``None``."""
        return self._s("channels").get(key)

    def has_channel(self, key: str) -> bool:
        """Return ``True`` if the key exists."""
        return key in self._s("channels")

    def remove_channel(self, key: str) -> None:
        """Delete a channel entry (no-op if missing)."""
        self._s("channels").pop(key, None)

    def list_channels(self) -> dict[str, int]:
        """Return a copy of all channel entries."""
        return dict(self._s("channels"))

    def clear_channels(self) -> None:
        """Remove all channel entries."""
        self._s("channels").clear()

    # ── Other ─────────────────────────────────────────────────

    def set_other(self, key: str, value: Any) -> None:
        """Store an arbitrary setting under a named key."""
        self._s("other")[key] = value

    def get_other(self, key: str, default: Any = None) -> Any:
        """Return the setting for a key, or ``default``."""
        return self._s("other").get(key, default)

    def has_other(self, key: str) -> bool:
        """Return ``True`` if the key exists."""
        return key in self._s("other")

    def remove_other(self, key: str) -> None:
        """Delete an other setting (no-op if missing)."""
        self._s("other").pop(key, None)

    def list_other(self) -> dict[str, Any]:
        """Return a copy of all other settings."""
        return dict(self._s("other"))

    def clear_other(self) -> None:
        """Remove all other settings."""
        self._s("other").clear()

    # ── Bulk ──────────────────────────────────────────────────

    def reset(self) -> None:
        """Wipe all roles, channels, and other settings."""
        self._data = copy.deepcopy(self._SCHEMA)

    def merge(self, other: ServerConfig) -> None:
        """Merge another config into this one. Existing keys are overwritten."""
        for section, values in other.to_dict().items():
            self._s(section).update(values)

    def to_dict(self) -> dict:
        """Return a deep copy of the config data."""
        return copy.deepcopy(self._data)


class ServerConfigStore:
    """Loads and saves per-guild config as JSON files.

    Files are written under ``base_dir/<guild_id>.json``.
    Saves are atomic (write-to-temp + rename) and protected by per-guild locks.
    """

    def __init__(self, base_dir: str = ".easycord/server-config") -> None:
        self._base = Path(base_dir)
        self._base.mkdir(parents=True, exist_ok=True)
        self._locks: dict[int, asyncio.Lock] = defaultdict(asyncio.Lock)
        # In-memory cache of parsed config keyed by guild_id. ``None`` marks a
        # guild that is known to have no config file (so repeated hot-path
        # reads for disabled features never touch disk). The bot is the sole
        # writer; ``save``/``delete`` keep this coherent with disk.
        self._cache: dict[int, dict | None] = {}

    def _path(self, guild_id: int) -> Path:
        return self._base / f"{guild_id}.json"

    async def load(self, guild_id: int) -> ServerConfig:
        """Load config for a guild; returns an empty config if none exists.

        Parsed data is cached in memory after the first read. ``ServerConfig``
        deep-copies its data on construction, so each call still returns an
        independent, freely-mutable object.
        """
        async with self._locks[guild_id]:
            if guild_id in self._cache:
                return ServerConfig(guild_id, self._cache[guild_id])
            path = self._path(guild_id)
            if not path.exists():
                self._cache[guild_id] = None
                return ServerConfig(guild_id)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except (json.JSONDecodeError, OSError) as exc:
                raise RuntimeError(
                    f"Failed to load config for guild {guild_id}: {exc}"
                ) from exc
            self._cache[guild_id] = data
            return ServerConfig(guild_id, data)

    async def save(self, config: ServerConfig) -> None:
        """Persist a guild's config to disk atomically."""
        async with self._locks[config.guild_id]:
            path = self._path(config.guild_id)
            tmp = path.with_suffix(".tmp")
            data = config.to_dict()
            try:
                with open(tmp, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)
                os.replace(tmp, path)
            except (OSError, TypeError, ValueError) as exc:
                with contextlib.suppress(OSError):
                    if tmp.exists():
                        tmp.unlink()
                raise RuntimeError(
                    f"Failed to save config for guild {config.guild_id}: {exc}"
                ) from exc
            self._cache[config.guild_id] = data

    async def delete(self, guild_id: int) -> None:
        """Remove a guild's config file."""
        async with self._locks[guild_id]:
            path = self._path(guild_id)
            if path.exists():
                os.remove(path)
            self._cache[guild_id] = None

    async def exists(self, guild_id: int) -> bool:
        """Return ``True`` if a config file exists for this guild."""
        async with self._locks[guild_id]:
            return self._path(guild_id).exists()
