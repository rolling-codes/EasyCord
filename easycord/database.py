"""Framework-owned database helpers with automatic configuration."""
from __future__ import annotations

import asyncio
import json
import os
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal


DatabaseBackend = Literal["sqlite", "memory"]


@dataclass(slots=True)
class DatabaseConfig:
    """Configuration for the built-in database service."""

    backend: DatabaseBackend = "sqlite"
    path: str = ".easycord/library.db"
    auto_sync_guilds: bool = True

    @classmethod
    def from_env(cls) -> "DatabaseConfig":
        """Build a config from environment variables and framework defaults."""
        backend = os.getenv("EASYCORD_DB_BACKEND", cls.backend)
        path = os.getenv("EASYCORD_DB_PATH", cls.path)
        auto_sync = os.getenv("EASYCORD_DB_AUTO_SYNC_GUILDS", "1").strip().lower()
        return cls(
            backend=backend if backend in {"sqlite", "memory"} else "sqlite",
            path=path,
            auto_sync_guilds=auto_sync not in {"0", "false", "no", "off"},
        )


@dataclass(slots=True)
class GuildRecord:
    """Stored guild payload."""

    guild_id: int
    data: dict[str, Any] = field(default_factory=dict)


class EasyCordDatabase:
    """Base class for the framework's database backends."""

    backend_name = "base"

    def __init__(self, *, auto_sync_guilds: bool = True) -> None:
        self.auto_sync_guilds = auto_sync_guilds

    async def ensure_schema(self) -> None:
        """Create any backend tables or in-memory structures."""
        raise NotImplementedError

    async def close(self) -> None:
        """Release backend resources."""
        raise NotImplementedError

    async def ensure_guild(self, guild_id: int) -> None:
        """Create an empty row for a guild if it does not already exist."""
        raise NotImplementedError

    async def sync_guilds(self, guild_ids: list[int] | tuple[int, ...] | set[int]) -> None:
        """Ensure a batch of guild rows exists."""
        for guild_id in guild_ids:
            await self.ensure_guild(guild_id)

    async def get_guild(self, guild_id: int) -> GuildRecord | None:
        """Return a guild record or ``None`` if it does not exist."""
        raise NotImplementedError

    async def list_guilds(self) -> list[GuildRecord]:
        """Return all known guild records."""
        raise NotImplementedError

    async def get(self, guild_id: int, key: str, default: Any = None) -> Any:
        """Return a single guild-scoped value."""
        raise NotImplementedError

    async def set(self, guild_id: int, key: str, value: Any) -> None:
        """Store a single guild-scoped value."""
        raise NotImplementedError

    async def delete(self, guild_id: int, key: str) -> None:
        """Remove a single guild-scoped value."""
        raise NotImplementedError

    async def replace_guild(self, guild_id: int, data: dict[str, Any]) -> None:
        """Replace the full guild payload."""
        raise NotImplementedError


class SQLiteDatabase(EasyCordDatabase):
    """SQLite backend that stores guild records as JSON blobs."""

    backend_name = "sqlite"

    def __init__(self, path: str = ".easycord/library.db", *, auto_sync_guilds: bool = True) -> None:
        super().__init__(auto_sync_guilds=auto_sync_guilds)
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = asyncio.Lock()
        self._initialize()

    def _initialize(self) -> None:
        with self._conn:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS guilds (
                    guild_id INTEGER PRIMARY KEY,
                    data TEXT NOT NULL
                )
                """
            )

    @staticmethod
    def _encode_data(data: dict[str, Any]) -> str:
        return json.dumps(data, ensure_ascii=False)

    @staticmethod
    def _decode_data(payload: str | bytes | None) -> dict[str, Any]:
        if not payload:
            return {}
        try:
            parsed = json.loads(payload)
        except (TypeError, json.JSONDecodeError):
            return {}
        return parsed if isinstance(parsed, dict) else {}

    async def close(self) -> None:
        async with self._lock:
            await asyncio.to_thread(self._conn.close)

    async def ensure_schema(self) -> None:
        async with self._lock:
            await asyncio.to_thread(self._initialize)

    async def ensure_guild(self, guild_id: int) -> None:
        async with self._lock:
            await asyncio.to_thread(self._ensure_guild_sync, guild_id)

    def _ensure_guild_sync(self, guild_id: int) -> None:
        with self._conn:
            self._conn.execute(
                "INSERT OR IGNORE INTO guilds (guild_id, data) VALUES (?, ?)",
                (guild_id, self._encode_data({})),
            )

    async def get_guild(self, guild_id: int) -> GuildRecord | None:
        async with self._lock:
            row = await asyncio.to_thread(self._fetch_guild_sync, guild_id)
        if row is None:
            return None
        return GuildRecord(guild_id=guild_id, data=row)

    def _fetch_guild_sync(self, guild_id: int) -> dict[str, Any] | None:
        cur = self._conn.execute(
            "SELECT data FROM guilds WHERE guild_id = ?",
            (guild_id,),
        )
        row = cur.fetchone()
        if row is None:
            return None
        return self._decode_data(row["data"])

    async def list_guilds(self) -> list[GuildRecord]:
        async with self._lock:
            rows = await asyncio.to_thread(self._list_guilds_sync)
        return [GuildRecord(guild_id=guild_id, data=data) for guild_id, data in rows]

    def _list_guilds_sync(self) -> list[tuple[int, dict[str, Any]]]:
        cur = self._conn.execute("SELECT guild_id, data FROM guilds ORDER BY guild_id")
        return [(row["guild_id"], self._decode_data(row["data"])) for row in cur.fetchall()]

    async def get(self, guild_id: int, key: str, default: Any = None) -> Any:
        record = await self.get_guild(guild_id)
        if record is None:
            return default
        return record.data.get(key, default)

    async def set(self, guild_id: int, key: str, value: Any) -> None:
        async with self._lock:
            await asyncio.to_thread(self._set_sync, guild_id, key, value)

    def _set_sync(self, guild_id: int, key: str, value: Any) -> None:
        data = self._fetch_guild_sync(guild_id) or {}
        data[key] = value
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO guilds (guild_id, data) VALUES (?, ?)
                ON CONFLICT(guild_id) DO UPDATE SET data = excluded.data
                """,
                (guild_id, self._encode_data(data)),
            )

    async def delete(self, guild_id: int, key: str) -> None:
        async with self._lock:
            await asyncio.to_thread(self._delete_sync, guild_id, key)

    def _delete_sync(self, guild_id: int, key: str) -> None:
        data = self._fetch_guild_sync(guild_id) or {}
        if key not in data:
            return
        data.pop(key, None)
        with self._conn:
            self._conn.execute(
                "UPDATE guilds SET data = ? WHERE guild_id = ?",
                (self._encode_data(data), guild_id),
            )

    async def replace_guild(self, guild_id: int, data: dict[str, Any]) -> None:
        async with self._lock:
            await asyncio.to_thread(self._replace_sync, guild_id, data)

    def _replace_sync(self, guild_id: int, data: dict[str, Any]) -> None:
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO guilds (guild_id, data) VALUES (?, ?)
                ON CONFLICT(guild_id) DO UPDATE SET data = excluded.data
                """,
                (guild_id, self._encode_data(dict(data))),
            )


class MemoryDatabase(EasyCordDatabase):
    """In-memory backend used for tests and ephemeral bots."""

    backend_name = "memory"

    def __init__(self, *, auto_sync_guilds: bool = True) -> None:
        super().__init__(auto_sync_guilds=auto_sync_guilds)
        self._guilds: dict[int, dict[str, Any]] = {}
        self._lock = asyncio.Lock()

    async def ensure_schema(self) -> None:
        return None

    async def close(self) -> None:
        return None

    async def ensure_guild(self, guild_id: int) -> None:
        async with self._lock:
            self._guilds.setdefault(guild_id, {})

    async def get_guild(self, guild_id: int) -> GuildRecord | None:
        async with self._lock:
            data = self._guilds.get(guild_id)
            if data is None:
                return None
            return GuildRecord(guild_id=guild_id, data=dict(data))

    async def list_guilds(self) -> list[GuildRecord]:
        async with self._lock:
            return [GuildRecord(guild_id=guild_id, data=dict(data)) for guild_id, data in self._guilds.items()]

    async def get(self, guild_id: int, key: str, default: Any = None) -> Any:
        async with self._lock:
            return self._guilds.get(guild_id, {}).get(key, default)

    async def set(self, guild_id: int, key: str, value: Any) -> None:
        async with self._lock:
            self._guilds.setdefault(guild_id, {})[key] = value

    async def delete(self, guild_id: int, key: str) -> None:
        async with self._lock:
            self._guilds.get(guild_id, {}).pop(key, None)

    async def replace_guild(self, guild_id: int, data: dict[str, Any]) -> None:
        async with self._lock:
            self._guilds[guild_id] = dict(data)
