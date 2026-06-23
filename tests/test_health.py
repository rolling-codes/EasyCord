"""Tests for the /health command database status field."""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from easycord import Bot
from easycord.database import MemoryDatabase, SQLiteDatabase
from easycord.testing import FakeContext


def _get_health_embed(ctx: FakeContext):
    assert ctx.responses, "health command produced no response"
    embed = ctx.responses[-1].embed
    assert embed is not None
    return embed


def _db_field(embed) -> str:
    field = next((f for f in embed.fields if f.name == "Database"), None)
    assert field is not None, "Database field missing from health embed"
    assert field.value is not None
    return field.value


async def _invoke_health(bot: Bot) -> FakeContext:
    from discord import app_commands
    bot._start_time = 0
    health_cmd = next(c for c in bot.tree.get_commands() if c.name == "health")
    assert isinstance(health_cmd, app_commands.Command)
    ctx = FakeContext.make(client=bot)
    await health_cmd.callback(ctx.interaction)  # type: ignore[call-arg]
    return ctx


# ---------------------------------------------------------------------------
# MemoryDatabase ping
# ---------------------------------------------------------------------------

class TestMemoryDatabasePing:
    @pytest.mark.asyncio
    async def test_ping_returns_float(self) -> None:
        db = MemoryDatabase()
        latency = await db.ping()
        assert isinstance(latency, float)
        assert latency >= 0.0

    @pytest.mark.asyncio
    async def test_ping_reflects_populated_store(self) -> None:
        db = MemoryDatabase()
        await db.ensure_guild(1)
        await db.ensure_guild(2)
        assert db.record_count == 2
        latency = await db.ping()
        assert latency >= 0.0

    @pytest.mark.asyncio
    async def test_record_count_starts_at_zero(self) -> None:
        db = MemoryDatabase()
        assert db.record_count == 0


# ---------------------------------------------------------------------------
# SQLiteDatabase ping
# ---------------------------------------------------------------------------

class TestSQLiteDatabasePing:
    @pytest.mark.asyncio
    async def test_ping_returns_float(self, tmp_path) -> None:
        db = SQLiteDatabase(str(tmp_path / "test.db"))
        try:
            latency = await db.ping()
            assert isinstance(latency, float)
            assert latency >= 0.0
        finally:
            await db.close()

    @pytest.mark.asyncio
    async def test_path_attribute_is_set(self, tmp_path) -> None:
        db_path = tmp_path / "mybot.db"
        db = SQLiteDatabase(str(db_path))
        try:
            assert db.path == db_path
        finally:
            await db.close()


# ---------------------------------------------------------------------------
# /health embed — MemoryDatabase
# ---------------------------------------------------------------------------

class TestHealthEmbedMemoryDatabase:
    @pytest.mark.asyncio
    async def test_database_field_contains_backend_name(self) -> None:
        bot = Bot(enable_health_command=True, db_backend="memory")
        try:
            ctx = await _invoke_health(bot)
            field = _db_field(_get_health_embed(ctx))
            assert "MemoryDatabase" in field
        finally:
            await bot.close()

    @pytest.mark.asyncio
    async def test_database_field_contains_latency(self) -> None:
        bot = Bot(enable_health_command=True, db_backend="memory")
        try:
            ctx = await _invoke_health(bot)
            field = _db_field(_get_health_embed(ctx))
            assert "Latency:" in field
            assert "ms" in field
        finally:
            await bot.close()

    @pytest.mark.asyncio
    async def test_database_field_contains_record_count(self) -> None:
        bot = Bot(enable_health_command=True, db_backend="memory")
        try:
            ctx = await _invoke_health(bot)
            field = _db_field(_get_health_embed(ctx))
            assert "Records:" in field
        finally:
            await bot.close()

    @pytest.mark.asyncio
    async def test_database_field_shows_error_on_ping_failure(self) -> None:
        bot = Bot(enable_health_command=True, db_backend="memory")
        try:
            bot.db.ping = AsyncMock(side_effect=RuntimeError("connection lost"))  # type: ignore[method-assign]
            ctx = await _invoke_health(bot)
            field = _db_field(_get_health_embed(ctx))
            assert "Error:" in field
            assert "connection lost" in field
        finally:
            await bot.close()

    @pytest.mark.asyncio
    async def test_database_field_no_path_for_memory_backend(self) -> None:
        bot = Bot(enable_health_command=True, db_backend="memory")
        try:
            ctx = await _invoke_health(bot)
            field = _db_field(_get_health_embed(ctx))
            assert "Path:" not in field
        finally:
            await bot.close()


# ---------------------------------------------------------------------------
# /health embed — SQLiteDatabase
# ---------------------------------------------------------------------------

class TestHealthEmbedSQLiteDatabase:
    @pytest.mark.asyncio
    async def test_database_field_contains_backend_name(self, tmp_path) -> None:
        bot = Bot(enable_health_command=True, db_backend="sqlite",
                  db_path=str(tmp_path / "h.db"))
        try:
            ctx = await _invoke_health(bot)
            field = _db_field(_get_health_embed(ctx))
            assert "SQLiteDatabase" in field
        finally:
            await bot.close()

    @pytest.mark.asyncio
    async def test_database_field_contains_latency(self, tmp_path) -> None:
        bot = Bot(enable_health_command=True, db_backend="sqlite",
                  db_path=str(tmp_path / "h.db"))
        try:
            ctx = await _invoke_health(bot)
            field = _db_field(_get_health_embed(ctx))
            assert "Latency:" in field
        finally:
            await bot.close()

    @pytest.mark.asyncio
    async def test_database_field_contains_path(self, tmp_path) -> None:
        db_path = tmp_path / "h.db"
        bot = Bot(enable_health_command=True, db_backend="sqlite",
                  db_path=str(db_path))
        try:
            ctx = await _invoke_health(bot)
            field = _db_field(_get_health_embed(ctx))
            assert "Path:" in field
        finally:
            await bot.close()
