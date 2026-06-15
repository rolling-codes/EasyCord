"""Tests for AutoRolePlugin — pure functions, store layer, command flow, and event handler."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from easycord.plugins.auto_role import AutoRolePlugin, _missing_roles
from easycord.server_config import ServerConfigStore


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ctx(guild_id: int = 100, user_id: int = 1) -> MagicMock:
    ctx = MagicMock()
    ctx.guild = MagicMock()
    ctx.guild.id = guild_id
    ctx.user = MagicMock()
    ctx.user.id = user_id
    ctx.respond = AsyncMock()
    ctx.is_admin = True
    return ctx


def _plugin(tmp_path) -> AutoRolePlugin:
    p = AutoRolePlugin.__new__(AutoRolePlugin)
    AutoRolePlugin.__init__(p, store_path=str(tmp_path / "auto_role"))
    return p


def _make_guild(*, role_ids: list[int]) -> MagicMock:
    guild = MagicMock(spec=discord.Guild)
    roles: list[MagicMock] = []
    for rid in role_ids:
        role = MagicMock(spec=discord.Role)
        role.id = rid
        roles.append(role)
    guild.roles = roles
    guild.get_role = lambda rid: next((r for r in roles if r.id == rid), None)
    return guild


def _make_role(role_id: int) -> MagicMock:
    role = MagicMock(spec=discord.Role)
    role.id = role_id
    role.mention = f"<@&{role_id}>"
    return role


# ---------------------------------------------------------------------------
# Layer 1 — pure functions
# ---------------------------------------------------------------------------

class TestMissingRoles:
    def test_missing_roles_none_missing(self) -> None:
        guild = _make_guild(role_ids=[1, 2, 3])
        result = _missing_roles([1, 2, 3], guild)
        assert result == []

    def test_missing_roles_some_missing(self) -> None:
        guild = _make_guild(role_ids=[1, 3])
        result = _missing_roles([1, 2, 3], guild)
        assert result == [2]

    def test_missing_roles_all_missing(self) -> None:
        guild = _make_guild(role_ids=[])
        result = _missing_roles([10, 20], guild)
        assert result == [10, 20]

    def test_missing_roles_empty_list(self) -> None:
        guild = _make_guild(role_ids=[1, 2])
        result = _missing_roles([], guild)
        assert result == []


# ---------------------------------------------------------------------------
# Layer 2 — store operations via plugin internals
# ---------------------------------------------------------------------------

class TestAutoRoleStore:
    @pytest.mark.asyncio
    async def test_add_role_persists(self, tmp_path) -> None:
        plugin = _plugin(tmp_path)
        ctx = _ctx()
        role = _make_role(111)
        await plugin.autorole_add(ctx, role)
        store = ServerConfigStore(str(tmp_path / "auto_role"))
        cfg = await store.load(100)
        data = cfg.get_other("auto_role", {})
        assert 111 in data.get("role_ids", [])

    @pytest.mark.asyncio
    async def test_remove_role(self, tmp_path) -> None:
        plugin = _plugin(tmp_path)
        ctx = _ctx()
        role = _make_role(111)
        await plugin.autorole_add(ctx, role)
        await plugin.autorole_remove(ctx, role)
        store = ServerConfigStore(str(tmp_path / "auto_role"))
        cfg = await store.load(100)
        data = cfg.get_other("auto_role", {})
        assert 111 not in data.get("role_ids", [])

    @pytest.mark.asyncio
    async def test_add_duplicate_not_doubled(self, tmp_path) -> None:
        plugin = _plugin(tmp_path)
        ctx = _ctx()
        role = _make_role(111)
        await plugin.autorole_add(ctx, role)
        await plugin.autorole_add(ctx, role)
        store = ServerConfigStore(str(tmp_path / "auto_role"))
        cfg = await store.load(100)
        data = cfg.get_other("auto_role", {})
        role_ids = data.get("role_ids", [])
        assert role_ids.count(111) == 1

    @pytest.mark.asyncio
    async def test_delay_stored(self, tmp_path) -> None:
        plugin = _plugin(tmp_path)
        ctx = _ctx()
        await plugin.autorole_delay(ctx, 30)
        store = ServerConfigStore(str(tmp_path / "auto_role"))
        cfg = await store.load(100)
        data = cfg.get_other("auto_role", {})
        assert data.get("delay_seconds") == 30

    @pytest.mark.asyncio
    async def test_guilds_isolated(self, tmp_path) -> None:
        plugin = _plugin(tmp_path)
        ctx1 = _ctx(guild_id=1)
        ctx2 = _ctx(guild_id=2)
        role = _make_role(999)
        await plugin.autorole_add(ctx1, role)
        store = ServerConfigStore(str(tmp_path / "auto_role"))
        cfg2 = await store.load(2)
        data2 = cfg2.get_other("auto_role", {})
        assert 999 not in data2.get("role_ids", [])


# ---------------------------------------------------------------------------
# Layer 3 — command flow
# ---------------------------------------------------------------------------

class TestAutoRoleCommands:
    @pytest.mark.asyncio
    async def test_autorole_add_stores_role(self, tmp_path) -> None:
        plugin = _plugin(tmp_path)
        ctx = _ctx()
        role = _make_role(55)
        await plugin.autorole_add(ctx, role)
        ctx.respond.assert_called_once()
        store = ServerConfigStore(str(tmp_path / "auto_role"))
        cfg = await store.load(100)
        data = cfg.get_other("auto_role", {})
        assert 55 in data.get("role_ids", [])

    @pytest.mark.asyncio
    async def test_autorole_remove_missing_is_ok(self, tmp_path) -> None:
        plugin = _plugin(tmp_path)
        ctx = _ctx()
        role = _make_role(55)
        # Remove without adding first — should not raise
        await plugin.autorole_remove(ctx, role)
        ctx.respond.assert_called_once()

    @pytest.mark.asyncio
    async def test_autorole_list_empty(self, tmp_path) -> None:
        plugin = _plugin(tmp_path)
        ctx = _ctx()
        await plugin.autorole_list(ctx)
        ctx.respond.assert_called_once()
        call_args = ctx.respond.call_args
        text = call_args[0][0] if call_args[0] else ""
        assert "No auto-roles" in text

    @pytest.mark.asyncio
    async def test_autorole_list_shows_roles(self, tmp_path) -> None:
        plugin = _plugin(tmp_path)
        ctx = _ctx()
        role = _make_role(77)
        await plugin.autorole_add(ctx, role)
        ctx2 = _ctx()
        await plugin.autorole_list(ctx2)
        ctx2.respond.assert_called_once()
        call_args = ctx2.respond.call_args
        text = call_args[0][0] if call_args[0] else ""
        assert "77" in text

    @pytest.mark.asyncio
    async def test_autorole_delay_stores_value(self, tmp_path) -> None:
        plugin = _plugin(tmp_path)
        ctx = _ctx()
        await plugin.autorole_delay(ctx, 60)
        ctx.respond.assert_called_once()
        store = ServerConfigStore(str(tmp_path / "auto_role"))
        cfg = await store.load(100)
        data = cfg.get_other("auto_role", {})
        assert data.get("delay_seconds") == 60


# ---------------------------------------------------------------------------
# Event handler — member_join
# ---------------------------------------------------------------------------

class TestAutoRoleMemberJoin:
    @pytest.mark.asyncio
    async def test_member_join_assigns_roles(self, tmp_path) -> None:
        plugin = _plugin(tmp_path)

        # Pre-configure a role in the store
        ctx = _ctx(guild_id=200)
        role = _make_role(333)
        await plugin.autorole_add(ctx, role)

        # Build a mock member
        guild = MagicMock(spec=discord.Guild)
        guild.id = 200
        real_role = MagicMock(spec=discord.Role)
        real_role.id = 333
        guild.get_role = lambda rid: real_role if rid == 333 else None

        member = MagicMock(spec=discord.Member)
        member.bot = False
        member.guild = guild
        member.add_roles = AsyncMock()

        await plugin._on_member_join(member)

        member.add_roles.assert_called_once_with(real_role, reason="AutoRolePlugin")

    @pytest.mark.asyncio
    async def test_member_join_skips_bots(self, tmp_path) -> None:
        plugin = _plugin(tmp_path)

        member = MagicMock(spec=discord.Member)
        member.bot = True
        member.add_roles = AsyncMock()

        await plugin._on_member_join(member)

        member.add_roles.assert_not_called()

    @pytest.mark.asyncio
    async def test_member_join_no_roles_configured(self, tmp_path) -> None:
        plugin = _plugin(tmp_path)

        guild = MagicMock(spec=discord.Guild)
        guild.id = 300

        member = MagicMock(spec=discord.Member)
        member.bot = False
        member.guild = guild
        member.add_roles = AsyncMock()

        await plugin._on_member_join(member)

        member.add_roles.assert_not_called()
