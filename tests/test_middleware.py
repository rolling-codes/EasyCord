"""Tests for middleware factories and build_chain."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, PropertyMock

import pytest

from easycord.middleware import (
    admin_only,
    allowed_roles,
    boost_only,
    build_chain,
    catch_errors,
    channel_only,
    dm_only,
    guild_only,
    has_permission,
    log_middleware,
    rate_limit,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ctx(
    *,
    guild=None,
    user_id: int = 1,
    channel=None,
    command_name: str = "cmd",
) -> MagicMock:
    ctx = MagicMock()
    ctx.guild = guild
    ctx.user = MagicMock()
    ctx.user.id = user_id
    ctx.channel = channel
    ctx.command_name = command_name
    ctx.respond = AsyncMock()
    ctx.t = lambda key, default="", **kw: default.format(**kw) if kw else default
    return ctx


def _guild(
    *,
    member_roles: list[int] | None = None,
    is_admin: bool = False,
    is_booster: bool = False,
    member_exists: bool = True,
    permissions: dict[str, bool] | None = None,
) -> MagicMock:
    guild = MagicMock()
    if not member_exists:
        guild.get_member.return_value = None
        return guild
    member = MagicMock()
    roles = []
    for rid in (member_roles or []):
        r = MagicMock()
        r.id = rid
        roles.append(r)
    member.roles = roles
    member.guild_permissions.administrator = is_admin
    member.premium_since = MagicMock() if is_booster else None
    perm_obj = MagicMock()
    for k, v in (permissions or {}).items():
        setattr(perm_obj, k, v)
    member.guild_permissions = perm_obj
    member.guild_permissions.administrator = is_admin
    guild.get_member.return_value = member
    return guild


async def _proceed_fn():
    pass


# ---------------------------------------------------------------------------
# build_chain
# ---------------------------------------------------------------------------

class TestBuildChain:
    @pytest.mark.asyncio
    async def test_chain_calls_invoke(self) -> None:
        ctx = _ctx()
        called = []

        async def invoke():
            called.append("invoke")

        chain = build_chain(ctx, invoke, [])
        await chain()
        assert called == ["invoke"]

    @pytest.mark.asyncio
    async def test_middleware_order(self) -> None:
        ctx = _ctx()
        order = []

        async def mw1(ctx, proceed):
            order.append("mw1_before")
            await proceed()
            order.append("mw1_after")

        async def mw2(ctx, proceed):
            order.append("mw2_before")
            await proceed()
            order.append("mw2_after")

        async def invoke():
            order.append("invoke")

        chain = build_chain(ctx, invoke, [mw1, mw2])
        await chain()
        assert order == ["mw1_before", "mw2_before", "invoke", "mw2_after", "mw1_after"]


# ---------------------------------------------------------------------------
# dm_only
# ---------------------------------------------------------------------------

class TestDmOnly:
    @pytest.mark.asyncio
    async def test_allows_dm(self) -> None:
        ctx = _ctx(guild=None)
        called = []
        mw = dm_only()

        async def proceed():
            called.append(True)

        await mw(ctx, proceed)
        assert called

    @pytest.mark.asyncio
    async def test_blocks_guild(self) -> None:
        ctx = _ctx(guild=MagicMock())
        called = []
        mw = dm_only()

        async def proceed():
            called.append(True)

        await mw(ctx, proceed)
        assert not called
        ctx.respond.assert_called_once()


# ---------------------------------------------------------------------------
# guild_only
# ---------------------------------------------------------------------------

class TestGuildOnly:
    @pytest.mark.asyncio
    async def test_allows_guild(self) -> None:
        ctx = _ctx(guild=MagicMock())
        called = []
        mw = guild_only()

        async def proceed():
            called.append(True)

        await mw(ctx, proceed)
        assert called

    @pytest.mark.asyncio
    async def test_blocks_dm(self) -> None:
        ctx = _ctx(guild=None)
        called = []
        mw = guild_only()

        async def proceed():
            called.append(True)

        await mw(ctx, proceed)
        assert not called
        ctx.respond.assert_called_once()


# ---------------------------------------------------------------------------
# allowed_roles
# ---------------------------------------------------------------------------

class TestAllowedRoles:
    @pytest.mark.asyncio
    async def test_allows_member_with_role(self) -> None:
        ctx = _ctx(guild=_guild(member_roles=[100, 200]))
        called = []
        mw = allowed_roles(100)

        async def proceed():
            called.append(True)

        await mw(ctx, proceed)
        assert called

    @pytest.mark.asyncio
    async def test_blocks_member_without_role(self) -> None:
        ctx = _ctx(guild=_guild(member_roles=[300]))
        called = []
        mw = allowed_roles(100)

        async def proceed():
            called.append(True)

        await mw(ctx, proceed)
        assert not called
        ctx.respond.assert_called_once()

    @pytest.mark.asyncio
    async def test_passes_in_dm(self) -> None:
        ctx = _ctx(guild=None)
        called = []
        mw = allowed_roles(100)

        async def proceed():
            called.append(True)

        await mw(ctx, proceed)
        assert called

    @pytest.mark.asyncio
    async def test_blocks_when_member_not_found(self) -> None:
        ctx = _ctx(guild=_guild(member_exists=False))
        called = []
        mw = allowed_roles(100)

        async def proceed():
            called.append(True)

        await mw(ctx, proceed)
        assert not called

    @pytest.mark.asyncio
    async def test_custom_message(self) -> None:
        ctx = _ctx(guild=_guild(member_roles=[]))
        mw = allowed_roles(100, message="Nope!")

        async def proceed():
            pass

        await mw(ctx, proceed)
        ctx.respond.assert_called_once_with("Nope!", ephemeral=True)


# ---------------------------------------------------------------------------
# channel_only
# ---------------------------------------------------------------------------

class TestChannelOnly:
    @pytest.mark.asyncio
    async def test_allows_correct_channel(self) -> None:
        channel = MagicMock()
        channel.id = 500
        ctx = _ctx(guild=MagicMock(), channel=channel)
        called = []
        mw = channel_only(500)

        async def proceed():
            called.append(True)

        await mw(ctx, proceed)
        assert called

    @pytest.mark.asyncio
    async def test_blocks_wrong_channel(self) -> None:
        channel = MagicMock()
        channel.id = 999
        ctx = _ctx(guild=MagicMock(), channel=channel)
        called = []
        mw = channel_only(500)

        async def proceed():
            called.append(True)

        await mw(ctx, proceed)
        assert not called
        ctx.respond.assert_called_once()

    @pytest.mark.asyncio
    async def test_passes_in_dm(self) -> None:
        ctx = _ctx(guild=None)
        called = []
        mw = channel_only(500)

        async def proceed():
            called.append(True)

        await mw(ctx, proceed)
        assert called


# ---------------------------------------------------------------------------
# admin_only
# ---------------------------------------------------------------------------

class TestAdminOnly:
    @pytest.mark.asyncio
    async def test_allows_admin(self) -> None:
        ctx = _ctx(guild=_guild(is_admin=True))
        called = []
        mw = admin_only()

        async def proceed():
            called.append(True)

        await mw(ctx, proceed)
        assert called

    @pytest.mark.asyncio
    async def test_blocks_non_admin(self) -> None:
        ctx = _ctx(guild=_guild(is_admin=False))
        called = []
        mw = admin_only()

        async def proceed():
            called.append(True)

        await mw(ctx, proceed)
        assert not called

    @pytest.mark.asyncio
    async def test_passes_in_dm(self) -> None:
        ctx = _ctx(guild=None)
        called = []
        mw = admin_only()

        async def proceed():
            called.append(True)

        await mw(ctx, proceed)
        assert called


# ---------------------------------------------------------------------------
# log_middleware
# ---------------------------------------------------------------------------

class TestLogMiddleware:
    @pytest.mark.asyncio
    async def test_calls_proceed(self) -> None:
        ctx = _ctx(guild=MagicMock())
        ctx.guild.__str__ = lambda s: "TestGuild"
        ctx.user.__str__ = lambda s: "TestUser"
        called = []
        mw = log_middleware()

        async def proceed():
            called.append(True)

        await mw(ctx, proceed)
        assert called


# ---------------------------------------------------------------------------
# rate_limit
# ---------------------------------------------------------------------------

class TestRateLimit:
    def test_invalid_limit_raises(self) -> None:
        with pytest.raises(ValueError):
            rate_limit(limit=0)

    def test_invalid_window_raises(self) -> None:
        with pytest.raises(ValueError):
            rate_limit(window=0)

    @pytest.mark.asyncio
    async def test_allows_under_limit(self) -> None:
        ctx = _ctx()
        called = []
        mw = rate_limit(limit=3, window=60.0)

        for _ in range(3):
            async def proceed():
                called.append(True)
            await mw(ctx, proceed)

        assert len(called) == 3

    @pytest.mark.asyncio
    async def test_blocks_over_limit(self) -> None:
        ctx = _ctx()
        called = []
        mw = rate_limit(limit=2, window=60.0)

        async def proceed():
            called.append(True)

        await mw(ctx, proceed)
        await mw(ctx, proceed)
        await mw(ctx, proceed)  # third should be blocked

        assert len(called) == 2
        ctx.respond.assert_called_once()

    @pytest.mark.asyncio
    async def test_different_users_independent(self) -> None:
        ctx1 = _ctx(user_id=1)
        ctx2 = _ctx(user_id=2)
        called = []
        mw = rate_limit(limit=1, window=60.0)

        async def proceed():
            called.append(True)

        await mw(ctx1, proceed)
        await mw(ctx2, proceed)
        assert len(called) == 2


# ---------------------------------------------------------------------------
# boost_only
# ---------------------------------------------------------------------------

class TestBoostOnly:
    @pytest.mark.asyncio
    async def test_allows_booster(self) -> None:
        ctx = _ctx(guild=_guild(is_booster=True))
        called = []
        mw = boost_only()

        async def proceed():
            called.append(True)

        await mw(ctx, proceed)
        assert called

    @pytest.mark.asyncio
    async def test_blocks_non_booster(self) -> None:
        ctx = _ctx(guild=_guild(is_booster=False))
        called = []
        mw = boost_only()

        async def proceed():
            called.append(True)

        await mw(ctx, proceed)
        assert not called

    @pytest.mark.asyncio
    async def test_passes_in_dm(self) -> None:
        ctx = _ctx(guild=None)
        called = []
        mw = boost_only()

        async def proceed():
            called.append(True)

        await mw(ctx, proceed)
        assert called

    @pytest.mark.asyncio
    async def test_custom_message(self) -> None:
        ctx = _ctx(guild=_guild(is_booster=False))
        mw = boost_only(message="Boosters only!")

        await mw(ctx, lambda: None)
        ctx.respond.assert_called_once_with("Boosters only!", ephemeral=True)


# ---------------------------------------------------------------------------
# has_permission
# ---------------------------------------------------------------------------

class TestHasPermission:
    @pytest.mark.asyncio
    async def test_allows_member_with_permission(self) -> None:
        ctx = _ctx(guild=_guild(permissions={"kick_members": True}))
        called = []
        mw = has_permission("kick_members")

        async def proceed():
            called.append(True)

        await mw(ctx, proceed)
        assert called

    @pytest.mark.asyncio
    async def test_blocks_member_missing_permission(self) -> None:
        ctx = _ctx(guild=_guild(permissions={"kick_members": False}))
        called = []
        mw = has_permission("kick_members")

        async def proceed():
            called.append(True)

        await mw(ctx, proceed)
        assert not called

    @pytest.mark.asyncio
    async def test_passes_in_dm(self) -> None:
        ctx = _ctx(guild=None)
        called = []
        mw = has_permission("kick_members")

        async def proceed():
            called.append(True)

        await mw(ctx, proceed)
        assert called

    @pytest.mark.asyncio
    async def test_blocks_when_member_not_found(self) -> None:
        ctx = _ctx(guild=_guild(member_exists=False))
        called = []
        mw = has_permission("kick_members")

        async def proceed():
            called.append(True)

        await mw(ctx, proceed)
        assert not called


# ---------------------------------------------------------------------------
# catch_errors
# ---------------------------------------------------------------------------

class TestCatchErrors:
    @pytest.mark.asyncio
    async def test_passes_through_normally(self) -> None:
        ctx = _ctx()
        called = []
        mw = catch_errors()

        async def proceed():
            called.append(True)

        await mw(ctx, proceed)
        assert called

    @pytest.mark.asyncio
    async def test_catches_exception_and_responds(self) -> None:
        ctx = _ctx()
        mw = catch_errors()

        async def proceed():
            raise RuntimeError("oops")

        await mw(ctx, proceed)
        ctx.respond.assert_called_once()

    @pytest.mark.asyncio
    async def test_custom_error_message(self) -> None:
        ctx = _ctx()
        mw = catch_errors(message="Custom error!")

        async def proceed():
            raise RuntimeError("boom")

        await mw(ctx, proceed)
        ctx.respond.assert_called_once_with("Custom error!", ephemeral=True)
