"""Tests for BotConfig and config-driven bot startup."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from easycord import Bot, BotConfig, MemoryDatabase, SQLiteDatabase


def test_from_env_reads_known_fields_and_extra(monkeypatch) -> None:
    monkeypatch.setenv("DISCORD_TOKEN", "env-token")
    monkeypatch.setenv("DISCORD_GUILD_ID", "123")
    monkeypatch.setenv("EASYCORD_DB_BACKEND", "sqlite")
    monkeypatch.setenv("EASYCORD_DB_PATH", "data/env.db")
    monkeypatch.setenv("EASYCORD_AUTO_SYNC", "false")
    monkeypatch.setenv("EASYCORD_LOG_LEVEL", "WARNING")

    cfg = BotConfig.from_env(custom="value", extra={"nested": True})

    assert cfg.token == "env-token"
    assert cfg.guild_id == 123
    assert cfg.db_backend == "sqlite"
    assert cfg.db_path == "data/env.db"
    assert cfg.auto_sync is False
    assert cfg.log_level == "WARNING"
    assert cfg.extra == {"custom": "value", "nested": True}


def test_from_env_respects_explicit_falsy_token_override(monkeypatch) -> None:
    monkeypatch.setenv("DISCORD_TOKEN", "env-token")

    with pytest.raises(ValueError, match="token is required"):
        BotConfig.from_env(token="")


def test_from_env_rejects_invalid_guild_id(monkeypatch) -> None:
    monkeypatch.setenv("DISCORD_TOKEN", "token")
    monkeypatch.setenv("DISCORD_GUILD_ID", "not-an-int")

    with pytest.raises(ValueError, match="DISCORD_GUILD_ID"):
        BotConfig.from_env()


def test_invalid_log_level_rejected() -> None:
    with pytest.raises(ValueError, match="log_level"):
        BotConfig(token="token", log_level="VERBOSE")


def test_from_file_uses_overrides_after_file_and_merges_extra(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DISCORD_TOKEN", "env-token")
    config_path = tmp_path / "config.json"
    config_path.write_text(
        """
        {
          "token": "file-token",
          "guild_id": 111,
          "db_backend": "sqlite",
          "extra": {"file_key": "file", "shared": "file"},
          "loose_key": "loose"
        }
        """,
        encoding="utf-8",
    )

    cfg = BotConfig.from_file(
        str(config_path),
        guild_id=222,
        extra={"override_key": "override", "shared": "override"},
    )

    assert cfg.token == "file-token"
    assert cfg.guild_id == 222
    assert cfg.db_backend == "sqlite"
    assert cfg.extra == {
        "file_key": "file",
        "loose_key": "loose",
        "override_key": "override",
        "shared": "override",
    }


async def test_build_bot_honors_memory_backend() -> None:
    bot = BotConfig(token="token", db_backend="memory").build_bot(auto_sync=False)
    try:
        assert isinstance(bot.db, MemoryDatabase)
        assert bot._sync_guild_id is None
    finally:
        await bot.close()


async def test_build_bot_honors_sqlite_backend(tmp_path) -> None:
    db_path = tmp_path / "bot.db"
    bot = BotConfig(
        token="token",
        db_backend="sqlite",
        db_path=str(db_path),
    ).build_bot(auto_sync=False)
    try:
        assert isinstance(bot.db, SQLiteDatabase)
        assert str(bot.db.path) == str(db_path)
    finally:
        await bot.close()


async def test_build_bot_passes_guild_sync_target() -> None:
    bot = BotConfig(token="token", guild_id=987).build_bot(auto_sync=False)
    try:
        assert bot._sync_guild_id == 987
    finally:
        await bot.close()


async def test_setup_hook_syncs_to_configured_guild() -> None:
    db = MagicMock()
    db.auto_sync_guilds = False
    db.ensure_schema = AsyncMock()
    db.close = AsyncMock()
    bot = Bot(database=db, sync_guild_id=555)
    bot.tree.sync = AsyncMock()
    bot.tree.copy_global_to = MagicMock()
    try:
        await bot.setup_hook()
        bot.tree.copy_global_to.assert_called_once()
        bot.tree.sync.assert_awaited_once()
        copied_guild = bot.tree.copy_global_to.call_args.kwargs["guild"]
        synced_guild = bot.tree.sync.await_args.kwargs["guild"]
        assert copied_guild is synced_guild
        assert synced_guild.id == 555
    finally:
        await bot.close()
