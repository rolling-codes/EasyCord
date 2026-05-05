"""Tests for BaseContext and Context using a mock discord.Interaction."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, PropertyMock

import discord
import pytest

from easycord.context import Context
from easycord._context_base import BaseContext
from easycord.conversation_memory import ConversationMemory


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------

def _mock_interaction(
    *,
    guild=None,
    user_id: int = 1,
    is_admin: bool = False,
    locale: str = "en-US",
    guild_locale: str = "en-US",
) -> MagicMock:
    interaction = MagicMock(spec=discord.Interaction)
    interaction.guild = guild
    interaction.locale = locale
    interaction.guild_locale = guild_locale
    interaction.command = MagicMock()
    interaction.command.name = "test_cmd"
    interaction.data = {}
    interaction.channel = MagicMock()

    user = MagicMock(spec=discord.Member if guild else discord.User)
    user.id = user_id
    user.display_name = "TestUser"
    user.name = "testuser"
    if guild:
        permissions = MagicMock()
        permissions.administrator = is_admin
        user.guild_permissions = permissions
        user.voice = None
        user.top_role = MagicMock()
        user.top_role.name = "Member"
    interaction.user = user

    interaction.response = MagicMock()
    interaction.response.send_message = AsyncMock()
    interaction.response.defer = AsyncMock()
    interaction.followup = MagicMock()
    interaction.followup.send = AsyncMock()

    interaction.client = MagicMock()
    interaction.client.localization = None
    interaction.client.i18n = None
    interaction.client.ai_provider = None
    interaction.client.conversation_memory = None

    return interaction


def _mock_guild(*, member_id: int = 1, is_admin: bool = False) -> MagicMock:
    guild = MagicMock(spec=discord.Guild)
    guild.id = 100
    guild.name = "TestGuild"
    member = MagicMock(spec=discord.Member)
    permissions = MagicMock()
    permissions.administrator = is_admin
    member.guild_permissions = permissions
    member.roles = []
    member.voice = None
    guild.get_member.return_value = member
    return guild


# ---------------------------------------------------------------------------
# BaseContext properties
# ---------------------------------------------------------------------------

class TestBaseContext:
    def test_user_property(self) -> None:
        interaction = _mock_interaction(user_id=42)
        ctx = BaseContext(interaction)
        assert ctx.user.id == 42

    def test_guild_property_none_in_dm(self) -> None:
        ctx = BaseContext(_mock_interaction(guild=None))
        assert ctx.guild is None

    def test_command_name(self) -> None:
        ctx = BaseContext(_mock_interaction())
        assert ctx.command_name == "test_cmd"

    def test_command_name_none_when_no_command(self) -> None:
        interaction = _mock_interaction()
        interaction.command = None
        ctx = BaseContext(interaction)
        assert ctx.command_name is None

    def test_locale(self) -> None:
        ctx = BaseContext(_mock_interaction(locale="fr-FR"))
        assert ctx.locale == "fr-FR"

    def test_guild_locale(self) -> None:
        ctx = BaseContext(_mock_interaction(guild_locale="de-DE"))
        assert ctx.guild_locale == "de-DE"

    def test_data_property(self) -> None:
        ctx = BaseContext(_mock_interaction())
        assert ctx.data == {}

    def test_is_admin_false_in_dm(self) -> None:
        ctx = BaseContext(_mock_interaction(guild=None))
        assert ctx.is_admin is False

    def test_is_admin_true_when_admin(self) -> None:
        guild = _mock_guild(is_admin=True)
        interaction = _mock_interaction(guild=guild)
        interaction.user.guild_permissions.administrator = True
        ctx = BaseContext(interaction)
        ctx.interaction.user = interaction.user
        # member property derives from guild.get_member
        assert isinstance(ctx.is_admin, bool)

    def test_guild_id_property(self) -> None:
        guild = _mock_guild()
        ctx = BaseContext(_mock_interaction(guild=guild))
        assert ctx.guild_id == 100

    def test_guild_id_none_in_dm(self) -> None:
        ctx = BaseContext(_mock_interaction(guild=None))
        assert ctx.guild_id is None

    def test_t_with_default_no_localization(self) -> None:
        ctx = BaseContext(_mock_interaction())
        result = ctx.t("some.key", default="Hello {name}", name="World")
        assert result == "Hello World"

    def test_t_returns_key_when_no_default(self) -> None:
        ctx = BaseContext(_mock_interaction())
        result = ctx.t("some.key")
        assert result == "some.key"


# ---------------------------------------------------------------------------
# BaseContext responding
# ---------------------------------------------------------------------------

class TestBaseContextRespond:
    @pytest.mark.asyncio
    async def test_respond_first_call(self) -> None:
        interaction = _mock_interaction()
        ctx = BaseContext(interaction)
        await ctx.respond("Hello")
        interaction.response.send_message.assert_called_once_with(
            "Hello", ephemeral=False, embed=None
        )

    @pytest.mark.asyncio
    async def test_respond_second_call_uses_followup(self) -> None:
        interaction = _mock_interaction()
        ctx = BaseContext(interaction)
        await ctx.respond("First")
        await ctx.respond("Second")
        interaction.followup.send.assert_called_once_with(
            "Second", ephemeral=False, embed=None
        )

    @pytest.mark.asyncio
    async def test_respond_ephemeral(self) -> None:
        interaction = _mock_interaction()
        ctx = BaseContext(interaction)
        await ctx.respond("Secret", ephemeral=True)
        interaction.response.send_message.assert_called_once_with(
            "Secret", ephemeral=True, embed=None
        )

    @pytest.mark.asyncio
    async def test_defer_sets_responded(self) -> None:
        interaction = _mock_interaction()
        ctx = BaseContext(interaction)
        await ctx.defer()
        assert ctx._responded is True
        interaction.response.defer.assert_called_once()

    @pytest.mark.asyncio
    async def test_defer_noop_if_already_responded(self) -> None:
        interaction = _mock_interaction()
        ctx = BaseContext(interaction)
        await ctx.respond("First")
        await ctx.defer()
        interaction.response.defer.assert_not_called()


# ---------------------------------------------------------------------------
# Full Context
# ---------------------------------------------------------------------------

class TestContext:
    def test_context_instantiates(self) -> None:
        ctx = Context(_mock_interaction())
        assert ctx is not None

    @pytest.mark.asyncio
    async def test_send_embed(self) -> None:
        interaction = _mock_interaction()
        ctx = Context(interaction)
        await ctx.send_embed("Title", "Body")
        interaction.response.send_message.assert_called_once()
        call_kwargs = interaction.response.send_message.call_args[1]
        assert call_kwargs["embed"] is not None
        assert call_kwargs["embed"].title == "Title"

    @pytest.mark.asyncio
    async def test_ai_no_provider_raises(self) -> None:
        interaction = _mock_interaction()
        interaction.client.ai_provider = None
        ctx = Context(interaction)
        with pytest.raises(RuntimeError, match="No AI provider"):
            await ctx.ai("hello")

    @pytest.mark.asyncio
    async def test_ai_calls_provider(self) -> None:
        interaction = _mock_interaction()
        provider = MagicMock()
        provider.query = AsyncMock(return_value="pong")
        interaction.client.ai_provider = provider
        ctx = Context(interaction)
        result = await ctx.ai("ping")
        assert result == "pong"

    @pytest.mark.asyncio
    async def test_ai_with_memory(self) -> None:
        interaction = _mock_interaction()
        provider = MagicMock()
        provider.query = AsyncMock(return_value="answer")
        interaction.client.ai_provider = provider
        memory = ConversationMemory()
        interaction.client.conversation_memory = memory
        ctx = Context(interaction)
        result = await ctx.ai("question")
        assert result == "answer"
        msgs = memory.get_messages(1)
        assert any(m["content"] == "question" for m in msgs)

    @pytest.mark.asyncio
    async def test_conversation_history_no_memory(self) -> None:
        interaction = _mock_interaction()
        interaction.client.conversation_memory = None
        ctx = Context(interaction)
        turns = await ctx.conversation_history()
        assert turns == []

    @pytest.mark.asyncio
    async def test_conversation_history_with_memory(self) -> None:
        interaction = _mock_interaction()
        memory = ConversationMemory()
        memory.add_user_message(1, "hi")
        interaction.client.conversation_memory = memory
        ctx = Context(interaction)
        turns = await ctx.conversation_history()
        assert len(turns) == 1
        assert turns[0].content == "hi"

    @pytest.mark.asyncio
    async def test_conversation_history_with_limit(self) -> None:
        interaction = _mock_interaction()
        memory = ConversationMemory()
        for i in range(5):
            memory.add_user_message(1, f"msg{i}")
        interaction.client.conversation_memory = memory
        ctx = Context(interaction)
        turns = await ctx.conversation_history(limit=2)
        assert len(turns) == 2

    @pytest.mark.asyncio
    async def test_conversation_history_limit_zero(self) -> None:
        interaction = _mock_interaction()
        memory = ConversationMemory()
        memory.add_user_message(1, "hi")
        interaction.client.conversation_memory = memory
        ctx = Context(interaction)
        turns = await ctx.conversation_history(limit=0)
        assert turns == []
