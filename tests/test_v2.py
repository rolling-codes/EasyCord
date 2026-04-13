"""Tests for EasyCord 2.0 — new features and bug fixes."""
import discord
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from easycord import Bot
from easycord.context import Context


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def interaction():
    m = MagicMock()
    m.response.send_message = AsyncMock()
    m.response.defer = AsyncMock()
    m.followup.send = AsyncMock()
    m.edit_original_response = AsyncMock()
    m.command.name = "test"
    m.guild = MagicMock()
    return m


@pytest.fixture
def ctx(interaction):
    return Context(interaction)


@pytest.fixture
def bot():
    mock_tree = MagicMock()
    mock_tree.add_command = MagicMock()
    mock_tree.sync = AsyncMock()
    with patch("discord.Client.__init__", return_value=None), \
         patch("easycord.bot.app_commands.CommandTree", return_value=mock_tree):
        b = Bot(intents=MagicMock(), auto_sync=False)
        b.is_ready = MagicMock(return_value=False)
        return b


# ── voice_channel property ────────────────────────────────────────────────────

def test_voice_channel_none_when_user_is_not_member(ctx, interaction):
    interaction.user = MagicMock(spec=discord.User)
    assert ctx.voice_channel is None


def test_voice_channel_none_when_not_in_voice(ctx, interaction):
    member = MagicMock(spec=discord.Member)
    member.voice = None
    interaction.user = member
    assert ctx.voice_channel is None


def test_voice_channel_returns_voice_channel(ctx, interaction):
    vc = MagicMock(spec=discord.VoiceChannel)
    vs = MagicMock()
    vs.channel = vc
    member = MagicMock(spec=discord.Member)
    member.voice = vs
    interaction.user = member
    assert ctx.voice_channel is vc


def test_voice_channel_returns_stage_channel(ctx, interaction):
    sc = MagicMock(spec=discord.StageChannel)
    vs = MagicMock()
    vs.channel = sc
    member = MagicMock(spec=discord.Member)
    member.voice = vs
    interaction.user = member
    assert ctx.voice_channel is sc


# ── edit_response ──────────────────────────────────────────────────────────────

async def test_edit_response_content(ctx, interaction):
    await ctx.edit_response("Updated!")
    interaction.edit_original_response.assert_called_once_with(content="Updated!", embed=None)


async def test_edit_response_with_embed(ctx, interaction):
    embed = discord.Embed(title="T")
    await ctx.edit_response(embed=embed)
    interaction.edit_original_response.assert_called_once_with(content=None, embed=embed)


async def test_edit_response_no_args(ctx, interaction):
    await ctx.edit_response()
    interaction.edit_original_response.assert_called_once_with(content=None, embed=None)


# ── pin / unpin ───────────────────────────────────────────────────────────────

async def test_pin_calls_message_pin(ctx):
    message = MagicMock()
    message.pin = AsyncMock()
    await ctx.pin(message)
    message.pin.assert_called_once_with(reason=None)


async def test_pin_passes_reason(ctx):
    message = MagicMock()
    message.pin = AsyncMock()
    await ctx.pin(message, reason="Pinned for reference")
    message.pin.assert_called_once_with(reason="Pinned for reference")


async def test_unpin_calls_message_unpin(ctx):
    message = MagicMock()
    message.unpin = AsyncMock()
    await ctx.unpin(message)
    message.unpin.assert_called_once_with(reason=None)


async def test_unpin_passes_reason(ctx):
    message = MagicMock()
    message.unpin = AsyncMock()
    await ctx.unpin(message, reason="Outdated")
    message.unpin.assert_called_once_with(reason="Outdated")


# ── crosspost ─────────────────────────────────────────────────────────────────

async def test_crosspost_calls_message_publish(ctx):
    message = MagicMock()
    message.publish = AsyncMock()
    await ctx.crosspost(message)
    message.publish.assert_called_once()


# ── get_member ────────────────────────────────────────────────────────────────

def test_get_member_returns_cached_member(ctx, interaction):
    member = MagicMock(spec=discord.Member)
    interaction.guild.get_member = MagicMock(return_value=member)
    assert ctx.get_member(42) is member
    interaction.guild.get_member.assert_called_once_with(42)


def test_get_member_returns_none_when_not_cached(ctx, interaction):
    interaction.guild.get_member = MagicMock(return_value=None)
    assert ctx.get_member(42) is None


def test_get_member_returns_none_in_dm(ctx, interaction):
    interaction.guild = None
    assert ctx.get_member(42) is None


# ── fetch_bans ────────────────────────────────────────────────────────────────

async def test_fetch_bans_returns_list(ctx, interaction):
    ban1 = MagicMock(spec=discord.BanEntry)
    ban2 = MagicMock(spec=discord.BanEntry)

    async def _bans(limit=None):
        for entry in [ban1, ban2]:
            yield entry

    interaction.guild.bans = _bans
    result = await ctx.fetch_bans()
    assert result == [ban1, ban2]


async def test_fetch_bans_respects_limit(ctx, interaction):
    calls = []

    async def _bans(limit=None):
        calls.append(limit)
        return
        yield  # make it an async generator

    interaction.guild.bans = _bans
    await ctx.fetch_bans(limit=10)
    assert calls == [10]


async def test_fetch_bans_raises_outside_guild(ctx, interaction):
    interaction.guild = None
    with pytest.raises(RuntimeError, match="guild context"):
        await ctx.fetch_bans()


# ── purge bug fix: thread support ─────────────────────────────────────────────

async def test_purge_works_in_thread(ctx, interaction):
    thread = MagicMock(spec=discord.Thread)
    thread.purge = AsyncMock(return_value=[MagicMock(), MagicMock()])
    interaction.channel = thread
    count = await ctx.purge(2)
    assert count == 2
    thread.purge.assert_called_once_with(limit=2)


async def test_purge_still_works_in_text_channel(ctx, interaction):
    tc = MagicMock(spec=discord.TextChannel)
    tc.purge = AsyncMock(return_value=[MagicMock()])
    interaction.channel = tc
    count = await ctx.purge(1)
    assert count == 1


async def test_purge_raises_in_dm_channel(ctx, interaction):
    interaction.channel = MagicMock(spec=discord.DMChannel)
    with pytest.raises(RuntimeError, match="purge"):
        await ctx.purge()


# ── move_member bug fix: stage channel support ────────────────────────────────

async def test_move_member_accepts_voice_channel(ctx, interaction):
    vc = MagicMock(spec=discord.VoiceChannel)
    interaction.client.get_channel = MagicMock(return_value=vc)
    member = MagicMock(spec=discord.Member)
    member.edit = AsyncMock()
    await ctx.move_member(member, 123)
    member.edit.assert_called_once_with(voice_channel=vc, reason=None)


async def test_move_member_accepts_stage_channel(ctx, interaction):
    sc = MagicMock(spec=discord.StageChannel)
    interaction.client.get_channel = MagicMock(return_value=sc)
    member = MagicMock(spec=discord.Member)
    member.edit = AsyncMock()
    await ctx.move_member(member, 456)
    member.edit.assert_called_once_with(voice_channel=sc, reason=None)


async def test_move_member_rejects_text_channel(ctx, interaction):
    tc = MagicMock(spec=discord.TextChannel)
    interaction.client.get_channel = MagicMock(return_value=tc)
    member = MagicMock(spec=discord.Member)
    with pytest.raises(ValueError, match="voice or stage"):
        await ctx.move_member(member, 789)


async def test_move_member_disconnects_on_none(ctx, interaction):
    member = MagicMock(spec=discord.Member)
    member.edit = AsyncMock()
    await ctx.move_member(member, None)
    member.edit.assert_called_once_with(voice_channel=None, reason=None)


# ── user_command ──────────────────────────────────────────────────────────────

def test_user_command_registers_context_menu(bot):
    @bot.user_command(name="User Info")
    async def user_info(ctx, member):
        pass

    bot.tree.add_command.assert_called_once()
    cmd = bot.tree.add_command.call_args[0][0]
    assert cmd.name == "User Info"


def test_user_command_defaults_name_to_function_name(bot):
    @bot.user_command()
    async def show_profile(ctx, member):
        pass

    cmd = bot.tree.add_command.call_args[0][0]
    assert cmd.name == "show_profile"


def test_user_command_returns_original_function(bot):
    async def handler(ctx, member):
        pass

    result = bot.user_command(name="X")(handler)
    assert result is handler


async def test_user_command_invokes_handler_with_target(bot):
    received = []

    @bot.user_command(name="Info")
    async def handler(ctx, member):
        received.append(member)

    callback = bot.tree.add_command.call_args[0][0].callback
    interaction = MagicMock()
    interaction.response.send_message = AsyncMock()
    member = MagicMock(spec=discord.Member)
    await callback(interaction, member)
    assert received == [member]


def test_user_command_guild_scoped(bot):
    @bot.user_command(name="X", guild_id=99999)
    async def handler(ctx, member):
        pass

    _, kwargs = bot.tree.add_command.call_args
    assert kwargs.get("guild") is not None
    assert kwargs["guild"].id == 99999


# ── message_command ───────────────────────────────────────────────────────────

def test_message_command_registers_context_menu(bot):
    @bot.message_command(name="Quote")
    async def quote(ctx, message):
        pass

    bot.tree.add_command.assert_called_once()
    cmd = bot.tree.add_command.call_args[0][0]
    assert cmd.name == "Quote"


def test_message_command_defaults_name_to_function_name(bot):
    @bot.message_command()
    async def save_message(ctx, message):
        pass

    cmd = bot.tree.add_command.call_args[0][0]
    assert cmd.name == "save_message"


def test_message_command_returns_original_function(bot):
    async def handler(ctx, message):
        pass

    result = bot.message_command(name="Y")(handler)
    assert result is handler


async def test_message_command_invokes_handler_with_target(bot):
    received = []

    @bot.message_command(name="Archive")
    async def handler(ctx, message):
        received.append(message)

    callback = bot.tree.add_command.call_args[0][0].callback
    interaction = MagicMock()
    interaction.response.send_message = AsyncMock()
    msg = MagicMock(spec=discord.Message)
    await callback(interaction, msg)
    assert received == [msg]


async def test_context_menu_runs_middleware(bot):
    order = []

    async def mw(ctx, proceed):
        order.append("before")
        await proceed()
        order.append("after")

    bot.use(mw)

    @bot.user_command(name="MW Test")
    async def handler(ctx, member):
        order.append("handler")

    callback = bot.tree.add_command.call_args[0][0].callback
    interaction = MagicMock()
    interaction.response.send_message = AsyncMock()
    await callback(interaction, MagicMock(spec=discord.Member))
    assert order == ["before", "handler", "after"]
