"""Tests for RolePersistencePlugin save/restore logic.

Pins three defects in the leave/rejoin pipeline:

1. Save must record roles by identity, not by the bot's *current* hierarchy, so a
   role above the bot at leave time can still be restored later.
2. Assignability is gated at restore time; a failed restore (Forbidden/HTTP) must
   keep the saved record so a later rejoin can retry.
3. A successful restore clears the record, and an entry whose roles were all
   deleted from the guild must not leak forever.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from easycord.plugins._config_manager import PluginConfigManager
from easycord.plugins.role_persistence import RolePersistencePlugin

GUILD = 1
MEMBER = 5


def _make_plugin(tmp_path) -> RolePersistencePlugin:
    plugin = RolePersistencePlugin()
    plugin.config = PluginConfigManager(str(tmp_path / "role-persistence"))
    return plugin


def _role(role_id: int, *, assignable: bool = True, managed: bool = False, default: bool = False) -> MagicMock:
    role = MagicMock()
    role.id = role_id
    role.managed = managed
    role.is_assignable.return_value = assignable
    role.is_default.return_value = default
    return role


def _guild(roles_by_id: dict[int, MagicMock] | None = None) -> MagicMock:
    guild = MagicMock()
    guild.id = GUILD
    table = roles_by_id or {}
    guild.get_role.side_effect = lambda rid: table.get(rid)
    return guild


def _member(guild: MagicMock, *, roles=(), bot: bool = False) -> MagicMock:
    member = MagicMock()
    member.id = MEMBER
    member.bot = bot
    member.guild = guild
    member.roles = list(roles)
    member.add_roles = AsyncMock()
    return member


async def _saved_ids(plugin: RolePersistencePlugin) -> dict:
    cfg = await plugin.config.store.load(GUILD)
    return cfg.get_other("saved_roles", {})


@pytest.mark.asyncio
async def test_role_above_bot_is_saved(tmp_path) -> None:
    plugin = _make_plugin(tmp_path)
    # Currently not assignable (above the bot) — must still be recorded.
    above = _role(100, assignable=False)
    guild = _guild({100: above})
    await plugin._on_member_remove(_member(guild, roles=[above]))
    assert (await _saved_ids(plugin)) == {str(MEMBER): [100]}


@pytest.mark.asyncio
async def test_everyone_and_managed_roles_are_not_saved(tmp_path) -> None:
    plugin = _make_plugin(tmp_path)
    everyone = _role(1, default=True)
    booster = _role(2, managed=True)
    normal = _role(3)
    guild = _guild({1: everyone, 2: booster, 3: normal})
    await plugin._on_member_remove(_member(guild, roles=[everyone, booster, normal]))
    assert (await _saved_ids(plugin)) == {str(MEMBER): [3]}


@pytest.mark.asyncio
async def test_role_restored_only_once_assignable_record_retained_meanwhile(tmp_path) -> None:
    plugin = _make_plugin(tmp_path)
    role = _role(100, assignable=False)
    guild = _guild({100: role})
    await plugin._on_member_remove(_member(guild, roles=[role]))

    # Rejoin while still not assignable: no restore, record kept for retry.
    rejoin = _member(guild)
    await plugin._on_member_join(rejoin)
    rejoin.add_roles.assert_not_called()
    assert str(MEMBER) in (await _saved_ids(plugin))

    # Bot position improves; role becomes assignable -> restored + record cleared.
    role.is_assignable.return_value = True
    rejoin2 = _member(guild)
    await plugin._on_member_join(rejoin2)
    rejoin2.add_roles.assert_awaited_once()
    assert str(MEMBER) not in (await _saved_ids(plugin))


@pytest.mark.asyncio
async def test_forbidden_restore_keeps_record(tmp_path) -> None:
    plugin = _make_plugin(tmp_path)
    role = _role(100)
    guild = _guild({100: role})
    await plugin._on_member_remove(_member(guild, roles=[role]))

    rejoin = _member(guild)
    rejoin.add_roles = AsyncMock(side_effect=discord.Forbidden(MagicMock(), "no perms"))
    await plugin._on_member_join(rejoin)
    # Restore failed — record must survive so a future rejoin can retry.
    assert str(MEMBER) in (await _saved_ids(plugin))


@pytest.mark.asyncio
async def test_successful_restore_clears_record(tmp_path) -> None:
    plugin = _make_plugin(tmp_path)
    role = _role(100)
    guild = _guild({100: role})
    await plugin._on_member_remove(_member(guild, roles=[role]))

    rejoin = _member(guild)
    await plugin._on_member_join(rejoin)
    rejoin.add_roles.assert_awaited_once()
    assert str(MEMBER) not in (await _saved_ids(plugin))


@pytest.mark.asyncio
async def test_all_saved_roles_deleted_clears_stale_entry(tmp_path) -> None:
    plugin = _make_plugin(tmp_path)
    role = _role(100)
    guild = _guild({100: role})
    await plugin._on_member_remove(_member(guild, roles=[role]))

    # Role deleted from the guild before the member rejoins.
    empty_guild = _guild({})
    rejoin = _member(empty_guild)
    await plugin._on_member_join(rejoin)
    rejoin.add_roles.assert_not_called()
    # Stale, unrestorable entry must be cleaned up rather than leak forever.
    assert str(MEMBER) not in (await _saved_ids(plugin))
