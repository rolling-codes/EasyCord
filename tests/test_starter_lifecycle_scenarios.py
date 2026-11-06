"""Exercise generated starters across startup, restart, and repeated-test boundaries."""
from __future__ import annotations

import pytest
from starter_helpers import run_python

from easycord.cli import _write_new_project


@pytest.mark.parametrize("template", ["minimal", "plugin", "community", "ai", "database"])
def test_generated_live_startup_publishes_complete_command_tree_to_test_guild(tmp_path, template):
    """Run the real setup hook, faking only Discord's publication boundary."""
    project = tmp_path / "starter"
    _write_new_project(project, "starter", template=template)
    run_python(project, '''
import asyncio
from unittest.mock import AsyncMock
import discord
from bot import create_bot, bot as offline

async def scenario():
    live = create_bot(auto_sync=True, sync_guild_id=123456789, db_backend="sqlite", db_path="live.db")
    live.tree.sync = AsyncMock(return_value=[])
    guild = discord.Object(id=123456789)
    def schema(tree, scope=None):
        return sorted((cmd.to_dict(tree) for cmd in tree.get_commands(guild=scope)), key=lambda cmd: cmd["name"])
    try:
        expected = schema(offline.tree)
        assert expected
        await live.setup_hook()
        live.tree.sync.assert_awaited_once()
        assert live.tree.sync.await_args.kwargs["guild"].id == guild.id
        assert schema(live.tree, guild) == expected
        # Groups such as /tag must publish their nested options too.
        assert schema(live.tree) == expected
    finally:
        await live.close()
        await offline.close()
    assert not live._background_tasks
    assert not live._task_handles
asyncio.run(scenario())
''')


def test_generated_community_fixtures_isolate_file_backed_plugin_state(tmp_path):
    """Two tests using fresh bots must not leak JSON-backed tags into each other."""
    project = tmp_path / "starter"
    _write_new_project(project, "starter", template="community")
    (project / "tests" / "test_tag_isolation.py").write_text('''
from easycord.testing import FakeContext, FakeInteraction

async def invoke_tag(bot, command_name, **kwargs):
    command = bot.tree.get_command("tag").get_command(command_name)
    interaction = FakeInteraction(client=bot, command=command, guild_id=100)
    await command.callback(interaction, **kwargs)
    return FakeContext(interaction)

async def test_write_a_tag(bot):
    ctx = await invoke_tag(bot, "set", name="isolation", text="previous test data")
    ctx.assert_contains("saved")

async def test_next_fixture_cannot_read_previous_tag(bot):
    ctx = await invoke_tag(bot, "get", name="isolation")
    ctx.assert_contains("not found")
''')
    run_python(project, '''
import subprocess, sys
result = subprocess.run([sys.executable, "-m", "pytest", "-q", "tests/test_tag_isolation.py"], check=False)
raise SystemExit(result.returncode)
''')


def test_failed_publication_propagates_and_can_be_cleaned_up(tmp_path):
    """A failed Discord boundary must not look like a successful startup."""
    _write_new_project(tmp_path, "starter", template="minimal")
    run_python(tmp_path, '''
import asyncio
from unittest.mock import AsyncMock
from bot import create_bot, bot as offline

async def scenario():
    live = create_bot(auto_sync=True, sync_guild_id=123456789)
    failure = RuntimeError("Discord publication unavailable")
    live.tree.sync = AsyncMock(side_effect=failure)
    try:
        try:
            await live.setup_hook()
        except RuntimeError as caught:
            assert caught is failure
        else:
            raise AssertionError("startup swallowed a publication failure")
        live.tree.sync.assert_awaited_once()
        assert live.tree.sync.await_args.kwargs["guild"].id == 123456789
    finally:
        await live.close()
        await offline.close()
    assert not live._background_tasks

asyncio.run(scenario())
''')


def test_generated_community_offline_checks_do_not_read_live_plugin_files(tmp_path):
    """A real main() instance writes a tag; the imported offline bot cannot read it."""
    project = tmp_path / "starter"
    _write_new_project(project, "starter", template="community")
    run_python(project, '''
import asyncio
import os
from pathlib import Path
from easycord import Bot
from easycord.testing import FakeContext, FakeInteraction
import bot

launches = []
async def invoke_tag(app, action, **kwargs):
    command = app.tree.get_command("tag").get_command(action)
    interaction = FakeInteraction(client=app, command=command, guild_id=100)
    await command.callback(interaction, **kwargs)
    return FakeContext(interaction)

def fake_run(live, token):
    launches.append(token)
    async def scenario():
        try:
            (await invoke_tag(live, "set", name="production", text="live-only value")).assert_contains("saved")
            (await invoke_tag(bot.bot, "get", name="production")).assert_contains("not found")
            (await invoke_tag(bot.bot, "set", name="production", text="offline-only value")).assert_contains("saved")
            (await invoke_tag(live, "get", name="production")).assert_content("live-only value")
            custom = bot.create_bot(data_dir="custom-sandbox")
            try:
                (await invoke_tag(custom, "get", name="production")).assert_contains("not found")
            finally:
                await custom.close()
        finally:
            await live.close()
            await bot.bot.close()
    asyncio.run(scenario())

os.environ.update(DISCORD_TOKEN="test-token", DISCORD_GUILD_ID="123456789")
Bot.run = fake_run
bot.main()
assert launches == ["test-token"], "the live bot must launch once"
''')
