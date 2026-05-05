"""Tests for SQLiteDatabase and MemoryDatabase."""
from __future__ import annotations

import os
import tempfile

import pytest

from easycord.database import DatabaseConfig, GuildRecord, MemoryDatabase, SQLiteDatabase


# ---------------------------------------------------------------------------
# DatabaseConfig
# ---------------------------------------------------------------------------

class TestDatabaseConfig:
    def test_defaults(self) -> None:
        cfg = DatabaseConfig()
        assert cfg.backend == "sqlite"
        assert cfg.auto_sync_guilds is True

    def test_from_env_defaults(self, monkeypatch) -> None:
        monkeypatch.delenv("EASYCORD_DB_BACKEND", raising=False)
        monkeypatch.delenv("EASYCORD_DB_PATH", raising=False)
        monkeypatch.delenv("EASYCORD_DB_AUTO_SYNC_GUILDS", raising=False)
        cfg = DatabaseConfig.from_env()
        assert cfg.backend == "sqlite"
        assert cfg.auto_sync_guilds is True

    def test_from_env_memory_backend(self, monkeypatch) -> None:
        monkeypatch.setenv("EASYCORD_DB_BACKEND", "memory")
        cfg = DatabaseConfig.from_env()
        assert cfg.backend == "memory"

    def test_from_env_invalid_backend_defaults_to_sqlite(self, monkeypatch) -> None:
        monkeypatch.setenv("EASYCORD_DB_BACKEND", "redis")
        cfg = DatabaseConfig.from_env()
        assert cfg.backend == "sqlite"

    def test_from_env_auto_sync_false(self, monkeypatch) -> None:
        monkeypatch.setenv("EASYCORD_DB_AUTO_SYNC_GUILDS", "0")
        cfg = DatabaseConfig.from_env()
        assert cfg.auto_sync_guilds is False

    def test_from_env_auto_sync_false_variants(self, monkeypatch) -> None:
        for val in ("false", "no", "off"):
            monkeypatch.setenv("EASYCORD_DB_AUTO_SYNC_GUILDS", val)
            cfg = DatabaseConfig.from_env()
            assert cfg.auto_sync_guilds is False


# ---------------------------------------------------------------------------
# MemoryDatabase
# ---------------------------------------------------------------------------

class TestMemoryDatabase:
    @pytest.mark.asyncio
    async def test_ensure_schema_is_noop(self) -> None:
        db = MemoryDatabase()
        await db.ensure_schema()  # should not raise

    @pytest.mark.asyncio
    async def test_close_is_noop(self) -> None:
        db = MemoryDatabase()
        await db.close()  # should not raise

    @pytest.mark.asyncio
    async def test_ensure_guild_creates_entry(self) -> None:
        db = MemoryDatabase()
        await db.ensure_guild(1)
        record = await db.get_guild(1)
        assert record is not None
        assert record.guild_id == 1

    @pytest.mark.asyncio
    async def test_ensure_guild_idempotent(self) -> None:
        db = MemoryDatabase()
        await db.ensure_guild(1)
        await db.set(1, "key", "val")
        await db.ensure_guild(1)  # should not wipe existing data
        assert await db.get(1, "key") == "val"

    @pytest.mark.asyncio
    async def test_get_guild_missing_returns_none(self) -> None:
        db = MemoryDatabase()
        assert await db.get_guild(999) is None

    @pytest.mark.asyncio
    async def test_set_and_get(self) -> None:
        db = MemoryDatabase()
        await db.set(1, "score", 42)
        assert await db.get(1, "score") == 42

    @pytest.mark.asyncio
    async def test_get_missing_key_returns_default(self) -> None:
        db = MemoryDatabase()
        await db.ensure_guild(1)
        assert await db.get(1, "missing") is None
        assert await db.get(1, "missing", "fallback") == "fallback"

    @pytest.mark.asyncio
    async def test_get_missing_guild_returns_default(self) -> None:
        db = MemoryDatabase()
        assert await db.get(999, "key", "default") == "default"

    @pytest.mark.asyncio
    async def test_delete(self) -> None:
        db = MemoryDatabase()
        await db.set(1, "key", "value")
        await db.delete(1, "key")
        assert await db.get(1, "key") is None

    @pytest.mark.asyncio
    async def test_delete_missing_key_is_noop(self) -> None:
        db = MemoryDatabase()
        await db.ensure_guild(1)
        await db.delete(1, "nonexistent")  # should not raise

    @pytest.mark.asyncio
    async def test_replace_guild(self) -> None:
        db = MemoryDatabase()
        await db.set(1, "old", "data")
        await db.replace_guild(1, {"new": "data"})
        assert await db.get(1, "new") == "data"
        assert await db.get(1, "old") is None

    @pytest.mark.asyncio
    async def test_list_guilds(self) -> None:
        db = MemoryDatabase()
        await db.ensure_guild(10)
        await db.ensure_guild(20)
        guilds = await db.list_guilds()
        guild_ids = {g.guild_id for g in guilds}
        assert {10, 20} == guild_ids

    @pytest.mark.asyncio
    async def test_sync_guilds_batch(self) -> None:
        db = MemoryDatabase()
        await db.sync_guilds([1, 2, 3])
        guilds = await db.list_guilds()
        assert len(guilds) == 3

    @pytest.mark.asyncio
    async def test_get_returns_deep_copy(self) -> None:
        db = MemoryDatabase()
        await db.set(1, "data", {"list": [1, 2, 3]})
        val = await db.get(1, "data")
        val["list"].append(99)
        stored = await db.get(1, "data")
        assert stored == {"list": [1, 2, 3]}

    @pytest.mark.asyncio
    async def test_set_stores_deep_copy(self) -> None:
        db = MemoryDatabase()
        original = {"nested": [1, 2]}
        await db.set(1, "data", original)
        original["nested"].append(99)
        stored = await db.get(1, "data")
        assert stored == {"nested": [1, 2]}

    @pytest.mark.asyncio
    async def test_get_guild_returns_deep_copy(self) -> None:
        db = MemoryDatabase()
        await db.set(1, "x", [1, 2])
        record = await db.get_guild(1)
        record.data["x"].append(99)
        record2 = await db.get_guild(1)
        assert record2.data["x"] == [1, 2]


# ---------------------------------------------------------------------------
# SQLiteDatabase
# ---------------------------------------------------------------------------

class TestSQLiteDatabase:
    @pytest.fixture
    def db(self, tmp_path):
        path = tmp_path / "test.db"
        d = SQLiteDatabase(str(path))
        yield d

    @pytest.mark.asyncio
    async def test_ensure_guild_and_get_guild(self, db) -> None:
        await db.ensure_guild(42)
        record = await db.get_guild(42)
        assert record is not None
        assert record.guild_id == 42

    @pytest.mark.asyncio
    async def test_get_guild_missing_returns_none(self, db) -> None:
        assert await db.get_guild(999) is None

    @pytest.mark.asyncio
    async def test_set_and_get(self, db) -> None:
        await db.set(1, "points", 100)
        assert await db.get(1, "points") == 100

    @pytest.mark.asyncio
    async def test_get_missing_key_returns_default(self, db) -> None:
        await db.ensure_guild(1)
        assert await db.get(1, "missing", 99) == 99

    @pytest.mark.asyncio
    async def test_get_missing_guild_returns_default(self, db) -> None:
        assert await db.get(999, "key", "fallback") == "fallback"

    @pytest.mark.asyncio
    async def test_delete(self, db) -> None:
        await db.set(1, "key", "val")
        await db.delete(1, "key")
        assert await db.get(1, "key") is None

    @pytest.mark.asyncio
    async def test_delete_missing_key_noop(self, db) -> None:
        await db.ensure_guild(1)
        await db.delete(1, "nonexistent")

    @pytest.mark.asyncio
    async def test_replace_guild(self, db) -> None:
        await db.set(1, "old", "data")
        await db.replace_guild(1, {"new": "data"})
        assert await db.get(1, "new") == "data"
        assert await db.get(1, "old") is None

    @pytest.mark.asyncio
    async def test_list_guilds(self, db) -> None:
        await db.ensure_guild(10)
        await db.ensure_guild(20)
        guilds = await db.list_guilds()
        guild_ids = {g.guild_id for g in guilds}
        assert {10, 20} == guild_ids

    @pytest.mark.asyncio
    async def test_ensure_guild_idempotent(self, db) -> None:
        await db.ensure_guild(1)
        await db.set(1, "k", "v")
        await db.ensure_guild(1)
        assert await db.get(1, "k") == "v"

    @pytest.mark.asyncio
    async def test_ensure_schema_runs_without_error(self, db) -> None:
        await db.ensure_schema()

    @pytest.mark.asyncio
    async def test_close(self, db) -> None:
        await db.close()
