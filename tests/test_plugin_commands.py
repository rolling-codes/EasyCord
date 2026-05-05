"""Tests for plugin slash command handlers using mock Discord context."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from easycord.context import Context
from easycord.plugins.tags import TagsPlugin
from easycord.plugins.polls import PollsPlugin
from easycord.plugins.welcome import WelcomePlugin


# ---------------------------------------------------------------------------
# Mock factory (re-used across tests)
# ---------------------------------------------------------------------------

def _make_ctx(
    *,
    user_id: int = 1,
    guild_id: int = 100,
    is_admin: bool = False,
    with_guild: bool = True,
) -> MagicMock:
    ctx = MagicMock()
    ctx.user = MagicMock()
    ctx.user.id = user_id
    ctx.respond = AsyncMock()
    ctx.t = lambda key, default="", **kw: default.format(**kw) if kw else default

    if with_guild:
        guild = MagicMock()
        guild.id = guild_id
        member = MagicMock()
        perms = MagicMock()
        perms.administrator = is_admin
        member.guild_permissions = perms
        guild.get_member.return_value = member
        ctx.guild = guild
        ctx.guild_id = guild_id
    else:
        ctx.guild = None
        ctx.guild_id = None

    return ctx


# ---------------------------------------------------------------------------
# TagsPlugin command handlers
# ---------------------------------------------------------------------------

class TestTagsPluginCommands:
    @pytest.fixture
    def plugin(self, tmp_path):
        return TagsPlugin(data_dir=str(tmp_path / "tags"))

    @pytest.mark.asyncio
    async def test_set_then_get(self, plugin) -> None:
        ctx = _make_ctx()
        await plugin.set(ctx, "hello", "Hello, world!")
        ctx.respond.assert_called_once()

        ctx2 = _make_ctx()
        await plugin.get(ctx2, "hello")
        ctx2.respond.assert_called_once_with("Hello, world!")

    @pytest.mark.asyncio
    async def test_get_missing_tag(self, plugin) -> None:
        ctx = _make_ctx()
        await plugin.get(ctx, "missing")
        ctx.respond.assert_called_once()
        args = ctx.respond.call_args
        assert args[1].get("ephemeral") is True

    @pytest.mark.asyncio
    async def test_list_empty(self, plugin) -> None:
        ctx = _make_ctx()
        await plugin.list(ctx)
        ctx.respond.assert_called_once()
        assert ctx.respond.call_args[1].get("ephemeral") is True

    @pytest.mark.asyncio
    async def test_list_with_tags(self, plugin) -> None:
        ctx = _make_ctx()
        await plugin.set(ctx, "alpha", "A")
        await plugin.set(ctx, "beta", "B")
        ctx2 = _make_ctx()
        await plugin.list(ctx2)
        response_text = ctx2.respond.call_args[0][0]
        assert "alpha" in response_text
        assert "beta" in response_text

    @pytest.mark.asyncio
    async def test_delete_own_tag(self, plugin) -> None:
        ctx = _make_ctx(user_id=5)
        await plugin.set(ctx, "mytag", "value")
        ctx2 = _make_ctx(user_id=5)
        await plugin.delete(ctx2, "mytag")
        ctx2.respond.assert_called_once()
        # Tag should now be gone
        ctx3 = _make_ctx(user_id=5)
        await plugin.get(ctx3, "mytag")
        assert ctx3.respond.call_args[1].get("ephemeral") is True

    @pytest.mark.asyncio
    async def test_delete_other_user_tag_denied(self, plugin) -> None:
        ctx = _make_ctx(user_id=5)
        await plugin.set(ctx, "mytag", "value")
        ctx2 = _make_ctx(user_id=99, is_admin=False)
        await plugin.delete(ctx2, "mytag")
        ctx2.respond.assert_called_once()
        assert ctx2.respond.call_args[1].get("ephemeral") is True
        # confirm the "cannot delete" response was sent
        response_text = ctx2.respond.call_args[0][0]
        assert len(response_text) > 0

    @pytest.mark.asyncio
    async def test_delete_other_user_tag_admin_allowed(self, plugin) -> None:
        ctx = _make_ctx(user_id=5)
        await plugin.set(ctx, "mytag", "value")
        ctx2 = _make_ctx(user_id=99, is_admin=True)
        await plugin.delete(ctx2, "mytag")
        ctx2.respond.assert_called_once()
        # admin should succeed — tag gone
        ctx3 = _make_ctx()
        await plugin.get(ctx3, "mytag")
        assert ctx3.respond.call_args[1].get("ephemeral") is True

    @pytest.mark.asyncio
    async def test_delete_missing_tag(self, plugin) -> None:
        ctx = _make_ctx()
        await plugin.delete(ctx, "nonexistent")
        ctx.respond.assert_called_once()
        assert ctx.respond.call_args[1].get("ephemeral") is True


# ---------------------------------------------------------------------------
# PollsPlugin command handler
# ---------------------------------------------------------------------------

class TestPollsPluginCommands:
    @pytest.fixture
    def plugin(self) -> PollsPlugin:
        return PollsPlugin()

    @pytest.mark.asyncio
    async def test_poll_too_few_options(self, plugin) -> None:
        ctx = _make_ctx()
        await plugin.poll(ctx, "Question?", "OnlyOne", "", "", "", "", 60)
        ctx.respond.assert_called_once()
        assert ctx.respond.call_args[1].get("ephemeral") is True

    @pytest.mark.asyncio
    async def test_poll_invalid_duration(self, plugin) -> None:
        ctx = _make_ctx()
        await plugin.poll(ctx, "Q?", "A", "B", "", "", "", duration=3)
        ctx.respond.assert_called_once()
        assert ctx.respond.call_args[1].get("ephemeral") is True


# ---------------------------------------------------------------------------
# WelcomePlugin config helpers
# ---------------------------------------------------------------------------

class TestWelcomePluginConfig:
    @pytest.fixture
    def plugin(self, tmp_path):
        return WelcomePlugin(data_dir=str(tmp_path / "welcome"))

    def test_read_config_empty(self, plugin) -> None:
        cfg = plugin._read_config(1)
        assert isinstance(cfg, dict)

    def test_write_and_read_config(self, plugin) -> None:
        plugin._write_config(1, {"welcome_channel": 999})
        cfg = plugin._read_config(1)
        assert cfg["welcome_channel"] == 999

    def test_update_config(self, plugin) -> None:
        plugin._write_config(1, {"x": 1})
        plugin._update(1, x=42, y=7)
        cfg = plugin._read_config(1)
        assert cfg["x"] == 42
        assert cfg["y"] == 7
