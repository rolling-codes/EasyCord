"""Scenario checks for starter configuration, storage, and offline isolation."""
from __future__ import annotations

import pytest
from starter_helpers import run_python

from easycord.cli import _write_new_project


@pytest.mark.parametrize("guild_id", ["0", "-1", "18446744073709551616"])
def test_starter_rejects_invalid_server_id_before_storage_or_login(tmp_path, guild_id):
    """Integer syntax alone does not establish a usable Discord server ID."""
    _write_new_project(tmp_path, "starter", template="minimal")
    result = run_python(
        tmp_path,
        '''
from easycord import Bot
import bot
def unexpected_login(*args, **kwargs):
    raise AssertionError("invalid server ID reached login")
Bot.run = unexpected_login
bot.main()
''',
        check=False, DISCORD_TOKEN="offline-test-token", DISCORD_GUILD_ID=guild_id,
    )
    assert result.returncode != 0
    assert "DISCORD_GUILD_ID" in result.stderr
    assert "Traceback" not in result.stderr
    assert not (tmp_path / "data").exists()


def test_offline_database_command_ignores_broken_live_configuration(tmp_path):
    """A copied production shell must not make offline development need credentials."""
    _write_new_project(tmp_path, "starter", template="database")
    result = run_python(
        tmp_path,
        '''
from easycord.cli import main
raise SystemExit(main(["try", "bot:bot", "get_note"]))
''',
        DISCORD_GUILD_ID="not-a-number", DISCORD_TOKEN="",
        EASYCORD_DB_BACKEND="unsupported-production-backend",
        EASYCORD_DB_PATH=str(tmp_path / "must-not-create" / "production.db"),
        EASYCORD_AUTO_SYNC="true", EASYCORD_LOG_LEVEL="not-a-level",
        EASYCORD_GUILD_SYNC_TIMEOUT="not-a-number",
    )
    assert "No note saved." in result.stdout
    assert not (tmp_path / "must-not-create").exists()


def test_database_starter_preserves_notes_across_restart_and_isolates_servers(tmp_path):
    """Exercise real SQLite I/O and handler behavior, rather than inspecting db type."""
    _write_new_project(tmp_path, "starter", template="database")
    run_python(
        tmp_path,
        '''
import asyncio
from bot import create_bot
from easycord.testing import invoke

async def scenario():
    first = create_bot(db_backend="sqlite", db_path="nested/state.db")
    try:
        await invoke(first, "set_note", guild_id=100, note="survives restart")
    finally:
        await first.close()

    second = create_bot(db_backend="sqlite", db_path="nested/state.db")
    try:
        saved = await invoke(second, "get_note", guild_id=100)
        saved.assert_content("survives restart")
        unrelated = await invoke(second, "get_note", guild_id=200)
        unrelated.assert_content("No note saved.")
    finally:
        await second.close()

    fresh = create_bot()
    try:
        empty = await invoke(fresh, "get_note", guild_id=100)
        empty.assert_content("No note saved.")
    finally:
        await fresh.close()

asyncio.run(scenario())
''',
    )
    assert (tmp_path / "nested" / "state.db").exists()


def test_starter_explains_unusable_storage_path_before_login(tmp_path):
    """An existing directory configured as the database must produce a useful error."""
    _write_new_project(tmp_path, "starter", template="minimal")
    (tmp_path / "existing-directory").mkdir()
    result = run_python(
        tmp_path,
        '''
from easycord import Bot
import bot
def unexpected_login(*args, **kwargs):
    raise AssertionError("unusable storage reached login")
Bot.run = unexpected_login
bot.main()
''',
        DISCORD_TOKEN="offline-test-token", DISCORD_GUILD_ID="123456789",
        EASYCORD_DB_PATH=str(tmp_path / "existing-directory"), check=False,
    )
    assert result.returncode != 0
    assert "Traceback" not in result.stderr
    assert "storage" in result.stderr.lower() or "database" in result.stderr.lower()


def test_live_configuration_disables_publication_and_enables_requested_diagnostics(tmp_path):
    """Check actual setup_hook behavior when a developer explicitly disables sync."""
    _write_new_project(tmp_path, "starter", template="minimal")
    run_python(
        tmp_path,
        '''
import asyncio
import logging
from unittest.mock import AsyncMock
from easycord import Bot
import bot

launches = []
def fake_run(instance, token):
    launches.append(token)
    assert instance._guild_sync_timeout == 1.25
    assert logging.getLogger().level == logging.DEBUG
    assert "health" in {item["name"] for item in instance.inspect_interactions()["slash"]}
    instance.tree.sync = AsyncMock(side_effect=AssertionError("sync was disabled"))
    async def startup():
        try:
            await instance.setup_hook()
            instance.tree.sync.assert_not_awaited()
        finally:
            await instance.close()
    asyncio.run(startup())

Bot.run = fake_run
bot.main()
assert launches == ["offline-test-token"], "the configured bot must launch once"
asyncio.run(bot.bot.close())
''',
        DISCORD_TOKEN="offline-test-token", DISCORD_GUILD_ID="123456789",
        EASYCORD_DB_BACKEND="memory", EASYCORD_AUTO_SYNC="false",
        EASYCORD_GUILD_SYNC_TIMEOUT="1.25", EASYCORD_HEALTH_COMMAND="true",
        EASYCORD_LOG_LEVEL="DEBUG",
    )
