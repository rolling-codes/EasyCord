"""Tests for WordFilterPlugin — pure functions, store layer, and command flow."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from easycord.plugins.word_filter import WordFilterPlugin, _is_exempt, _matches
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


def _plugin(tmp_path) -> WordFilterPlugin:
    p = WordFilterPlugin.__new__(WordFilterPlugin)
    WordFilterPlugin.__init__(p, store_path=str(tmp_path / "word_filter"))
    return p


def _member(*, manage_messages: bool = False, role_ids: list[int] | None = None) -> MagicMock:
    m = MagicMock(spec=discord.Member)
    perms = MagicMock(spec=discord.Permissions)
    perms.manage_messages = manage_messages
    m.guild_permissions = perms
    roles: list[MagicMock] = []
    for rid in (role_ids or []):
        role = MagicMock(spec=discord.Role)
        role.id = rid
        roles.append(role)
    m.roles = roles
    return m


# ---------------------------------------------------------------------------
# Layer 1 — pure functions
# ---------------------------------------------------------------------------

class TestMatches:
    def test_matches_exact_word(self) -> None:
        assert _matches("badword", ["badword"]) is True

    def test_matches_substring(self) -> None:
        assert _matches("this contains badword here", ["badword"]) is True

    def test_matches_case_insensitive(self) -> None:
        assert _matches("BADWORD in message", ["badword"]) is True

    def test_no_match(self) -> None:
        assert _matches("perfectly fine message", ["badword"]) is False

    def test_matches_empty_word_list(self) -> None:
        assert _matches("some message", []) is False


class TestIsExempt:
    def test_is_exempt_manage_messages(self) -> None:
        member = _member(manage_messages=True)
        assert _is_exempt(member, None) is True

    def test_is_exempt_by_role(self) -> None:
        member = _member(manage_messages=False, role_ids=[42])
        assert _is_exempt(member, 42) is True

    def test_is_exempt_wrong_role(self) -> None:
        member = _member(manage_messages=False, role_ids=[99])
        assert _is_exempt(member, 42) is False

    def test_is_exempt_no_role_configured(self) -> None:
        member = _member(manage_messages=False, role_ids=[42])
        assert _is_exempt(member, None) is False


# ---------------------------------------------------------------------------
# Layer 2 — store operations via plugin internals
# ---------------------------------------------------------------------------

class TestWordFilterStore:
    @pytest.mark.asyncio
    async def test_add_word_persists(self, tmp_path) -> None:
        plugin = _plugin(tmp_path)
        ctx = _ctx()
        await plugin.filter_add(ctx, "spam")
        store = ServerConfigStore(str(tmp_path / "word_filter"))
        cfg = await store.load(100)
        data = cfg.get_other("word_filter", {})
        assert "spam" in data.get("words", [])

    @pytest.mark.asyncio
    async def test_remove_word(self, tmp_path) -> None:
        plugin = _plugin(tmp_path)
        ctx = _ctx()
        await plugin.filter_add(ctx, "spam")
        await plugin.filter_remove(ctx, "spam")
        store = ServerConfigStore(str(tmp_path / "word_filter"))
        cfg = await store.load(100)
        data = cfg.get_other("word_filter", {})
        assert "spam" not in data.get("words", [])

    @pytest.mark.asyncio
    async def test_list_words(self, tmp_path) -> None:
        plugin = _plugin(tmp_path)
        ctx = _ctx()
        await plugin.filter_add(ctx, "alpha")
        await plugin.filter_add(ctx, "beta")
        store = ServerConfigStore(str(tmp_path / "word_filter"))
        cfg = await store.load(100)
        data = cfg.get_other("word_filter", {})
        words = data.get("words", [])
        assert "alpha" in words
        assert "beta" in words

    @pytest.mark.asyncio
    async def test_set_action(self, tmp_path) -> None:
        plugin = _plugin(tmp_path)
        ctx = _ctx()
        await plugin.filter_action(ctx, "delete")
        store = ServerConfigStore(str(tmp_path / "word_filter"))
        cfg = await store.load(100)
        data = cfg.get_other("word_filter", {})
        assert data.get("action") == "delete"

    @pytest.mark.asyncio
    async def test_guilds_isolated(self, tmp_path) -> None:
        plugin = _plugin(tmp_path)
        ctx1 = _ctx(guild_id=1)
        ctx2 = _ctx(guild_id=2)
        await plugin.filter_add(ctx1, "guildone")
        store = ServerConfigStore(str(tmp_path / "word_filter"))
        cfg2 = await store.load(2)
        data2 = cfg2.get_other("word_filter", {})
        assert "guildone" not in data2.get("words", [])


# ---------------------------------------------------------------------------
# Layer 3 — command flow
# ---------------------------------------------------------------------------

class TestWordFilterCommands:
    @pytest.mark.asyncio
    async def test_filter_add_stores_word(self, tmp_path) -> None:
        plugin = _plugin(tmp_path)
        ctx = _ctx()
        await plugin.filter_add(ctx, "banned")
        ctx.respond.assert_called_once()
        call_args = ctx.respond.call_args
        text = call_args[0][0] if call_args[0] else ""
        assert "banned" in text

    @pytest.mark.asyncio
    async def test_filter_add_duplicate_not_doubled(self, tmp_path) -> None:
        plugin = _plugin(tmp_path)
        ctx = _ctx()
        await plugin.filter_add(ctx, "spam")
        await plugin.filter_add(ctx, "spam")
        store = ServerConfigStore(str(tmp_path / "word_filter"))
        cfg = await store.load(100)
        data = cfg.get_other("word_filter", {})
        words = data.get("words", [])
        assert words.count("spam") == 1

    @pytest.mark.asyncio
    async def test_filter_remove_missing_is_noop(self, tmp_path) -> None:
        plugin = _plugin(tmp_path)
        ctx = _ctx()
        await plugin.filter_remove(ctx, "notexist")
        ctx.respond.assert_called_once()
        call_args = ctx.respond.call_args
        text = call_args[0][0] if call_args[0] else ""
        assert "not in the blocklist" in text

    @pytest.mark.asyncio
    async def test_filter_action_invalid(self, tmp_path) -> None:
        plugin = _plugin(tmp_path)
        ctx = _ctx()
        await plugin.filter_action(ctx, "explode")
        ctx.respond.assert_called_once()
        call_args = ctx.respond.call_args
        text = call_args[0][0] if call_args[0] else ""
        assert "delete" in text or "warn" in text or "both" in text
        # Verify ephemeral=True was passed
        assert call_args[1].get("ephemeral") is True

    @pytest.mark.asyncio
    async def test_filter_list_empty(self, tmp_path) -> None:
        plugin = _plugin(tmp_path)
        ctx = _ctx()
        await plugin.filter_list(ctx)
        ctx.respond.assert_called_once()
        call_args = ctx.respond.call_args
        text = call_args[0][0] if call_args[0] else ""
        assert "No blocked" in text

    @pytest.mark.asyncio
    async def test_filter_list_shows_words(self, tmp_path) -> None:
        plugin = _plugin(tmp_path)
        ctx = _ctx()
        await plugin.filter_add(ctx, "badword")
        ctx2 = _ctx()
        await plugin.filter_list(ctx2)
        ctx2.respond.assert_called_once()
        call_args = ctx2.respond.call_args
        text = call_args[0][0] if call_args[0] else ""
        assert "badword" in text
