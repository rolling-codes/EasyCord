"""Concurrency stress tests and lock duration warning tests for PR #71."""
from __future__ import annotations

import asyncio
import json
import logging
from unittest.mock import AsyncMock, MagicMock

import pytest

from easycord.plugins._config_manager import PluginConfigManager
from easycord.plugins.role_persistence import RolePersistencePlugin
from easycord.plugins.suggestions import SuggestionsPlugin
from easycord.server_config import ServerConfigStore


@pytest.fixture
def store(tmp_path):
    return ServerConfigStore(str(tmp_path / "cfg"))


# ---------------------------------------------------------------------------
# ServerConfigStore.mutate Concurrency & Instrumentation Tests
# ---------------------------------------------------------------------------

class TestServerConfigStoreConcurrency:
    @pytest.mark.asyncio
    async def test_1000_concurrent_increments_no_lost_writes(self, store) -> None:
        """1000 concurrent mutate operations on the same guild must serialise
        properly without any lost writes.
        """
        guild_id = 123

        def _increment(cfg):
            count = cfg.get_other("count", 0)
            cfg.set_other("count", count + 1)

        # Run 1000 concurrent mutations
        await asyncio.gather(*[store.mutate(guild_id, _increment) for _ in range(1000)])

        # Verify final state is correct (invariants check)
        final_cfg = await store.load(guild_id)
        assert final_cfg.get_other("count") == 1000

        # Assert persisted file is valid JSON
        path = store._path(guild_id)
        assert path.exists()
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data["other"]["count"] == 1000

    @pytest.mark.asyncio
    async def test_mutate_different_guilds_independent(self, store) -> None:
        """Isolated guild locks must ensure concurrent writes across different guilds
        do not block each other, and merge correctly.
        """
        n_guilds = 50
        n_mutates = 20

        def _increment(cfg):
            count = cfg.get_other("count", 0)
            cfg.set_other("count", count + 1)

        # 50 guilds * 20 concurrent mutates = 1000 total tasks
        tasks = [
            store.mutate(guild_id, _increment)
            for guild_id in range(1, n_guilds + 1)
            for _ in range(n_mutates)
        ]
        await asyncio.gather(*tasks)

        # Verify invariants for each guild independently
        for guild_id in range(1, n_guilds + 1):
            cfg = await store.load(guild_id)
            assert cfg.get_other("count") == n_mutates

            # Assert valid JSON file format
            path = store._path(guild_id)
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            assert data["other"]["count"] == n_mutates

    @pytest.mark.asyncio
    async def test_slow_callback_triggers_warning(self, store, caplog) -> None:
        """A callback executing longer than 50ms must trigger a warning log."""
        guild_id = 1

        def slow_callback(cfg):
            import time
            time.sleep(0.06)  # 60ms sleep
            cfg.set_other("status", "slow")

        with caplog.at_level(logging.WARNING, logger="easycord.server_config"):
            await store.mutate(guild_id, slow_callback)

        assert any("Slow config mutation callback" in record.message for record in caplog.records)
        cfg = await store.load(guild_id)
        assert cfg.get_other("status") == "slow"

    @pytest.mark.asyncio
    async def test_fast_callback_no_warning(self, store, caplog) -> None:
        """A callback executing under 50ms must not trigger any warnings."""
        guild_id = 1

        def fast_callback(cfg):
            cfg.set_other("status", "fast")

        with caplog.at_level(logging.WARNING, logger="easycord.server_config"):
            await store.mutate(guild_id, fast_callback)

        assert not any("Slow config mutation callback" in record.message for record in caplog.records)
        cfg = await store.load(guild_id)
        assert cfg.get_other("status") == "fast"


# ---------------------------------------------------------------------------
# Suggestions Plugin Stress Tests
# ---------------------------------------------------------------------------

class TestSuggestionsPluginStress:
    def _make_plugin(self, tmp_path) -> SuggestionsPlugin:
        plugin = SuggestionsPlugin()
        plugin.config = PluginConfigManager(str(tmp_path / "suggestions"))
        return plugin

    @pytest.mark.asyncio
    async def test_1000_concurrent_suggest_ids_all_unique_and_contiguous(self, tmp_path) -> None:
        """1000 concurrent suggestion submissions must result in unique,
        monotonic, and contiguous IDs.
        """
        plugin = self._make_plugin(tmp_path)
        guild_id = 1

        # Run 1000 concurrent id allocations
        ids = await asyncio.gather(*[plugin._get_next_id(guild_id) for _ in range(1000)])

        # Assert ID invariants
        assert len(ids) == 1000
        assert len(set(ids)) == 1000
        assert sorted(ids) == list(range(1, 1001))


# ---------------------------------------------------------------------------
# Role Persistence Plugin Stress Tests
# ---------------------------------------------------------------------------

class TestRolePersistenceStress:
    def _make_plugin(self, tmp_path) -> RolePersistencePlugin:
        plugin = RolePersistencePlugin()
        plugin.config = PluginConfigManager(str(tmp_path / "role-persistence"))
        return plugin

    def _role(self, role_id: int) -> MagicMock:
        role = MagicMock()
        role.id = role_id
        role.managed = False
        role.is_assignable.return_value = True
        role.is_default.return_value = False
        return role

    def _guild(self, guild_id: int, roles_dict: dict[int, MagicMock]) -> MagicMock:
        guild = MagicMock()
        guild.id = guild_id
        guild.get_role.side_effect = lambda rid: roles_dict.get(rid)
        return guild

    def _member(self, member_id: int, guild: MagicMock, roles: list[MagicMock]) -> MagicMock:
        member = MagicMock()
        member.id = member_id
        member.bot = False
        member.guild = guild
        member.roles = roles
        member.add_roles = AsyncMock()
        return member

    @pytest.mark.asyncio
    async def test_concurrent_leave_and_rejoin_preserves_determinism(self, tmp_path) -> None:
        """Under concurrent member join/leave operations, role persistence must
        be deterministic, avoiding partial writes or stale data leaks.
        """
        plugin = self._make_plugin(tmp_path)
        guild_id = 999
        n_members = 200

        # Create shared mock guild roles
        role1 = self._role(101)
        role2 = self._role(102)
        roles_dict = {101: role1, 102: role2}
        guild = self._guild(guild_id, roles_dict)

        # 1. Concurrent member remove (saving roles)
        members_remove = [
            self._member(member_id, guild, [role1, role2])
            for member_id in range(1, n_members + 1)
        ]
        await asyncio.gather(*[plugin._on_member_remove(m) for m in members_remove])

        # Verify all saved roles are registered
        cfg = await plugin.config.store.load(guild_id)
        saved_roles = cfg.get_other("saved_roles", {})
        assert len(saved_roles) == n_members
        for member_id in range(1, n_members + 1):
            assert saved_roles[str(member_id)] == [101, 102]

        # 2. Concurrent member join (restoring roles)
        members_join = [
            self._member(member_id, guild, [])
            for member_id in range(1, n_members + 1)
        ]
        await asyncio.gather(*[plugin._on_member_join(m) for m in members_join])

        # Verify all roles were restored
        for m in members_join:
            m.add_roles.assert_awaited_once_with(role1, role2, reason="RolePersistencePlugin: restoring roles")

        # Verify the saved record has been completely cleaned up (no leak)
        cfg_after = await plugin.config.store.load(guild_id)
        assert cfg_after.get_other("saved_roles") == {}
