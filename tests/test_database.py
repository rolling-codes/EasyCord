import discord
import pytest
from unittest.mock import MagicMock, patch

from easycord import Bot, MemoryDatabase, SQLiteDatabase


async def test_memory_database_round_trip():
    db = MemoryDatabase()
    await db.ensure_guild(123)
    await db.set(123, "prefix", "!")
    await db.set(123, "config", {"enabled": True, "roles": [1, 2, 3]})

    assert await db.get(123, "prefix") == "!"
    assert await db.get(123, "config") == {"enabled": True, "roles": [1, 2, 3]}
    assert await db.get(123, "missing", "fallback") == "fallback"


async def test_sqlite_database_round_trip(tmp_path):
    db = SQLiteDatabase(path=str(tmp_path / "easycord.db"))
    await db.ensure_guild(321)
    await db.set(321, "prefix", "?")
    await db.set(321, "settings", {"locale": "en", "active": True})

    record = await db.get_guild(321)
    assert record is not None
    assert record.guild_id == 321
    assert record.data["prefix"] == "?"
    assert record.data["settings"] == {"locale": "en", "active": True}

    guilds = await db.list_guilds()
    assert [g.guild_id for g in guilds] == [321]

    await db.close()


async def test_sqlite_database_replace_guild(tmp_path):
    db = SQLiteDatabase(path=str(tmp_path / "replace.db"))
    await db.replace_guild(1, {"prefix": "!"})
    await db.replace_guild(1, {"prefix": "?", "flags": {"x": 1}})

    assert await db.get(1, "prefix") == "?"
    assert await db.get(1, "flags") == {"x": 1}

    await db.close()


def test_sqlite_decode_invalid_json_returns_empty_dict():
    assert SQLiteDatabase._decode_data("{not json}") == {}
    assert SQLiteDatabase._decode_data(b"{bad bytes}") == {}
    assert SQLiteDatabase._decode_data('"string"') == {}


def test_bot_uses_memory_database_when_requested():
    mock_tree = MagicMock()
    mock_tree.add_command = MagicMock()
    mock_tree.remove_command = MagicMock()
    mock_tree.sync = MagicMock()

    with patch("discord.Client.__init__", return_value=None), \
         patch("easycord.bot.app_commands.CommandTree", return_value=mock_tree):
        bot = Bot(intents=MagicMock(), auto_sync=False, db_backend="memory")

    assert isinstance(bot.db, MemoryDatabase)


async def test_guild_join_auto_syncs_database_row():
    mock_tree = MagicMock()
    mock_tree.add_command = MagicMock()
    mock_tree.remove_command = MagicMock()
    mock_tree.sync = MagicMock()

    with patch("discord.Client.__init__", return_value=None), \
         patch("easycord.bot.app_commands.CommandTree", return_value=mock_tree):
        bot = Bot(intents=MagicMock(), auto_sync=False, db_backend="memory")

    guild = MagicMock(spec=discord.Guild)
    guild.id = 999

    await bot.on_guild_join(guild)
    assert await bot.db.get_guild(999) is not None
