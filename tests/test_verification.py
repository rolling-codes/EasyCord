"""Tests for VerificationPlugin: pure functions, store layer, and command flow."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock

import discord

from easycord.plugins.verification import (
    VerificationPlugin,
    _build_panel_embed,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ctx(guild_id: int = 100, user_id: int = 1, is_admin: bool = True) -> MagicMock:
    ctx = MagicMock()
    ctx.guild = MagicMock()
    ctx.guild.id = guild_id
    ctx.user = MagicMock()
    ctx.user.id = user_id
    ctx.respond = AsyncMock()
    ctx.is_admin = is_admin
    ctx.channel = MagicMock()
    ctx.channel.id = 55
    ctx.member = MagicMock()
    return ctx


def _plugin(tmp_path) -> VerificationPlugin:
    p = VerificationPlugin.__new__(VerificationPlugin)
    VerificationPlugin.__init__(p, store_path=str(tmp_path / "verification"))
    return p


# ---------------------------------------------------------------------------
# Layer 1: pure functions
# ---------------------------------------------------------------------------

class TestBuildPanelEmbed:
    def test_panel_embed_no_question(self) -> None:
        embed = _build_panel_embed(None)
        assert isinstance(embed, discord.Embed)
        assert embed.title is not None
        assert "Verification" in embed.title
        # Question text must not appear
        assert embed.description is not None
        assert "You will be asked" not in embed.description

    def test_panel_embed_with_question(self) -> None:
        question = "What is rule #1?"
        embed = _build_panel_embed(question)
        assert embed.description is not None
        assert question in embed.description
        assert "You will be asked" in embed.description

    def test_panel_embed_returns_discord_embed(self) -> None:
        embed = _build_panel_embed(None)
        assert isinstance(embed, discord.Embed)

    def test_panel_embed_has_footer(self) -> None:
        embed = _build_panel_embed(None)
        assert embed.footer is not None
        assert embed.footer.text is not None

    def test_panel_embed_color_is_green(self) -> None:
        embed = _build_panel_embed(None)
        assert embed.color == discord.Color.green()


# ---------------------------------------------------------------------------
# Layer 2: store / tmp_path
# ---------------------------------------------------------------------------

class TestVerificationStore:
    @pytest.mark.asyncio
    async def test_setup_stores_role_and_channel(self, tmp_path) -> None:
        plugin = _plugin(tmp_path)
        guild_id = 200

        async with plugin._guild_lock(guild_id):
            cfg = await plugin._store.load(guild_id)
            cfg.set_other("verification", {"role_id": 11, "channel_id": 22})
            await plugin._store.save(cfg)

        reloaded = await plugin._store.load(guild_id)
        data = reloaded.get_other("verification", {})
        assert data["role_id"] == 11
        assert data["channel_id"] == 22

    @pytest.mark.asyncio
    async def test_question_stored(self, tmp_path) -> None:
        plugin = _plugin(tmp_path)
        guild_id = 201

        async with plugin._guild_lock(guild_id):
            cfg = await plugin._store.load(guild_id)
            cfg.set_other("verification", {"role_id": 1, "channel_id": 2, "question": "What is 2+2?"})
            await plugin._store.save(cfg)

        reloaded = await plugin._store.load(guild_id)
        data = reloaded.get_other("verification", {})
        assert data["question"] == "What is 2+2?"

    @pytest.mark.asyncio
    async def test_panel_message_id_stored(self, tmp_path) -> None:
        plugin = _plugin(tmp_path)
        guild_id = 202

        async with plugin._guild_lock(guild_id):
            cfg = await plugin._store.load(guild_id)
            cfg.set_other("verification", {"role_id": 1, "channel_id": 2, "panel_message_id": 9999})
            await plugin._store.save(cfg)

        reloaded = await plugin._store.load(guild_id)
        data = reloaded.get_other("verification", {})
        assert data["panel_message_id"] == 9999

    @pytest.mark.asyncio
    async def test_data_missing_before_setup(self, tmp_path) -> None:
        plugin = _plugin(tmp_path)
        cfg = await plugin._store.load(300)
        data = cfg.get_other("verification", {})
        assert data == {}

    @pytest.mark.asyncio
    async def test_guild_isolation(self, tmp_path) -> None:
        plugin = _plugin(tmp_path)

        async with plugin._guild_lock(1):
            cfg1 = await plugin._store.load(1)
            cfg1.set_other("verification", {"role_id": 10})
            await plugin._store.save(cfg1)

        cfg2 = await plugin._store.load(2)
        assert cfg2.get_other("verification", {}) == {}


# ---------------------------------------------------------------------------
# Layer 3: command flow
# ---------------------------------------------------------------------------

class TestVerificationSetupCommand:
    @pytest.mark.asyncio
    async def test_setup_requires_guild(self, tmp_path) -> None:
        plugin = _plugin(tmp_path)
        ctx = _ctx()
        ctx.guild = None
        ctx.is_admin = True

        role = MagicMock(spec=discord.Role)
        role.id = 50
        role.name = "Member"
        channel = MagicMock(spec=discord.TextChannel)
        channel.id = 60
        channel.mention = "#verify"

        await plugin.verification_setup(ctx, role, channel)
        ctx.respond.assert_called_once()
        call_args = ctx.respond.call_args
        assert call_args.kwargs.get("ephemeral", False)

    @pytest.mark.asyncio
    async def test_setup_not_admin_blocked(self, tmp_path) -> None:
        plugin = _plugin(tmp_path)
        ctx = _ctx(is_admin=False)

        role = MagicMock(spec=discord.Role)
        role.id = 50
        role.name = "Member"
        channel = MagicMock(spec=discord.TextChannel)
        channel.id = 60
        channel.mention = "#verify"

        await plugin.verification_setup(ctx, role, channel)
        ctx.respond.assert_called_once()
        call_args = ctx.respond.call_args
        # Should respond with ephemeral error
        assert call_args.kwargs.get("ephemeral", False)
        response_text = call_args.args[0] if call_args.args else ""
        assert "Administrator" in response_text or "permission" in response_text.lower()

    @pytest.mark.asyncio
    async def test_panel_no_config_responds_error(self, tmp_path) -> None:
        plugin = _plugin(tmp_path)
        ctx = _ctx()

        await plugin.verification_panel(ctx)
        ctx.respond.assert_called_once()
        call_args = ctx.respond.call_args
        assert call_args.kwargs.get("ephemeral", False)
        text = call_args.args[0] if call_args.args else ""
        assert "not configured" in text.lower() or "setup" in text.lower()

    @pytest.mark.asyncio
    async def test_setup_stores_correctly(self, tmp_path) -> None:
        plugin = _plugin(tmp_path)
        ctx = _ctx(guild_id=100)

        role = MagicMock(spec=discord.Role)
        role.id = 77
        role.name = "Verified"
        channel = MagicMock(spec=discord.TextChannel)
        channel.id = 88
        channel.mention = "#verify-here"

        await plugin.verification_setup(ctx, role, channel)

        ctx.respond.assert_called_once()
        # Verify data persisted
        cfg = await plugin._store.load(100)
        data = cfg.get_other("verification", {})
        assert data["role_id"] == 77
        assert data["channel_id"] == 88

    @pytest.mark.asyncio
    async def test_question_command_stores_text(self, tmp_path) -> None:
        plugin = _plugin(tmp_path)
        ctx = _ctx(guild_id=100)

        await plugin.verification_question(ctx, "What is rule #1?")

        ctx.respond.assert_called_once()
        cfg = await plugin._store.load(100)
        data = cfg.get_other("verification", {})
        assert data["question"] == "What is rule #1?"

    @pytest.mark.asyncio
    async def test_question_command_clears_with_empty_string(self, tmp_path) -> None:
        plugin = _plugin(tmp_path)
        ctx = _ctx(guild_id=100)

        # First set a question
        async with plugin._guild_lock(100):
            cfg = await plugin._store.load(100)
            cfg.set_other("verification", {"role_id": 1, "channel_id": 2, "question": "Old question"})
            await plugin._store.save(cfg)

        # Now clear it
        await plugin.verification_question(ctx, "  ")

        cfg = await plugin._store.load(100)
        data = cfg.get_other("verification", {})
        assert data.get("question") is None

    @pytest.mark.asyncio
    async def test_question_command_blocked_when_not_admin(self, tmp_path) -> None:
        plugin = _plugin(tmp_path)
        ctx = _ctx(is_admin=False)

        await plugin.verification_question(ctx, "Test question?")
        call_args = ctx.respond.call_args
        assert call_args.kwargs.get("ephemeral", False)

    @pytest.mark.asyncio
    async def test_panel_posts_to_guild_channel(self, tmp_path) -> None:
        plugin = _plugin(tmp_path)
        guild_id = 100
        ctx = _ctx(guild_id=guild_id)

        # Pre-configure verification
        async with plugin._guild_lock(guild_id):
            cfg = await plugin._store.load(guild_id)
            cfg.set_other("verification", {"role_id": 5, "channel_id": 99})
            await plugin._store.save(cfg)

        # Mock guild.get_channel to return a plain mock (has .send by default)
        mock_channel = MagicMock(spec=discord.TextChannel)
        mock_message = MagicMock()
        mock_message.id = 12345
        mock_channel.send = AsyncMock(return_value=mock_message)
        ctx.guild.get_channel = MagicMock(return_value=mock_channel)

        # Mock bot.add_view
        plugin._bot = MagicMock()
        plugin._bot.add_view = MagicMock()

        await plugin.verification_panel(ctx)

        mock_channel.send.assert_called_once()
        # panel_message_id should be stored
        cfg = await plugin._store.load(guild_id)
        data = cfg.get_other("verification", {})
        assert data["panel_message_id"] == 12345
