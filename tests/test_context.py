import discord
import pytest
from unittest.mock import AsyncMock, MagicMock

from easycord.context import Context


@pytest.fixture
def interaction():
    m = MagicMock()
    m.response.send_message = AsyncMock()
    m.response.defer = AsyncMock()
    m.followup.send = AsyncMock()
    m.command.name = "test"
    return m


@pytest.fixture
def ctx(interaction):
    return Context(interaction)


# --- Properties ---

def test_user_property(ctx, interaction):
    assert ctx.user is interaction.user


def test_guild_property(ctx, interaction):
    assert ctx.guild is interaction.guild


def test_channel_property(ctx, interaction):
    assert ctx.channel is interaction.channel


def test_data_property(ctx, interaction):
    assert ctx.data is interaction.data


def test_command_name(ctx, interaction):
    interaction.command.name = "ping"
    assert ctx.command_name == "ping"


def test_command_name_no_command(ctx, interaction):
    interaction.command = None
    assert ctx.command_name is None


def test_member_returns_member_in_guild(ctx, interaction):
    member = MagicMock(spec=discord.Member)
    interaction.user = member
    assert ctx.member is member


def test_member_returns_none_in_dm(ctx, interaction):
    interaction.user = MagicMock(spec=discord.User)
    assert ctx.member is None


def test_guild_id_returns_id_in_guild(ctx, interaction):
    interaction.guild = MagicMock()
    interaction.guild.id = 999
    assert ctx.guild_id == 999


def test_guild_id_returns_none_in_dm(ctx, interaction):
    interaction.guild = None
    assert ctx.guild_id is None


def test_is_admin_true_for_administrator(ctx, interaction):
    member = MagicMock(spec=discord.Member)
    member.guild_permissions = MagicMock()
    member.guild_permissions.administrator = True
    interaction.user = member
    interaction.guild = MagicMock()
    assert ctx.is_admin is True


def test_is_admin_false_for_non_admin(ctx, interaction):
    member = MagicMock(spec=discord.Member)
    member.guild_permissions = MagicMock()
    member.guild_permissions.administrator = False
    interaction.user = member
    interaction.guild = MagicMock()
    assert ctx.is_admin is False


def test_is_admin_false_in_dm(ctx, interaction):
    interaction.user = MagicMock(spec=discord.User)
    interaction.guild = None
    assert ctx.is_admin is False


# --- respond ---

async def test_respond_first_call_uses_send_message(ctx, interaction):
    await ctx.respond("Hello", ephemeral=True)
    interaction.response.send_message.assert_called_once_with(
        "Hello", ephemeral=True, embed=None
    )
    assert ctx._responded is True


async def test_respond_second_call_uses_followup(ctx, interaction):
    await ctx.respond("First")
    await ctx.respond("Second", ephemeral=True)
    interaction.followup.send.assert_called_once_with(
        "Second", ephemeral=True, embed=None
    )
    interaction.response.send_message.assert_called_once()


async def test_respond_with_embed(ctx, interaction):
    embed = discord.Embed(title="T")
    await ctx.respond(embed=embed)
    interaction.response.send_message.assert_called_once_with(
        None, ephemeral=False, embed=embed
    )


# --- defer ---

async def test_defer_marks_responded(ctx, interaction):
    await ctx.defer(ephemeral=True)
    interaction.response.defer.assert_called_once_with(ephemeral=True)
    assert ctx._responded is True


async def test_defer_then_respond_uses_followup(ctx, interaction):
    await ctx.defer()
    await ctx.respond("Late reply")
    interaction.followup.send.assert_called_once()


# --- send_embed ---

async def test_send_embed_sends_embed(ctx, interaction):
    await ctx.send_embed("Title", "Body")
    kwargs = interaction.response.send_message.call_args.kwargs
    embed = kwargs["embed"]
    assert embed.title == "Title"
    assert embed.description == "Body"
    assert kwargs["ephemeral"] is False


async def test_send_embed_custom_color(ctx, interaction):
    color = discord.Color.red()
    await ctx.send_embed("T", color=color)
    embed = interaction.response.send_message.call_args.kwargs["embed"]
    assert embed.color == color


async def test_send_embed_ephemeral(ctx, interaction):
    await ctx.send_embed("Title", ephemeral=True)
    assert interaction.response.send_message.call_args.kwargs["ephemeral"] is True


async def test_send_embed_with_fields(ctx, interaction):
    await ctx.send_embed("Stats", fields=[("Members", "150"), ("Online", "42")])
    embed = interaction.response.send_message.call_args.kwargs["embed"]
    assert len(embed.fields) == 2
    assert embed.fields[0].name == "Members"
    assert embed.fields[0].value == "150"
    assert embed.fields[1].name == "Online"
    assert embed.fields[1].value == "42"


async def test_send_embed_fields_inline_default(ctx, interaction):
    await ctx.send_embed("T", fields=[("A", "1")])
    embed = interaction.response.send_message.call_args.kwargs["embed"]
    assert embed.fields[0].inline is True


async def test_send_embed_fields_inline_custom(ctx, interaction):
    await ctx.send_embed("T", fields=[("A", "1", False)])
    embed = interaction.response.send_message.call_args.kwargs["embed"]
    assert embed.fields[0].inline is False


async def test_send_embed_with_footer(ctx, interaction):
    await ctx.send_embed("T", footer="Updated just now")
    embed = interaction.response.send_message.call_args.kwargs["embed"]
    assert embed.footer.text == "Updated just now"


async def test_send_embed_no_footer_by_default(ctx, interaction):
    await ctx.send_embed("T")
    embed = interaction.response.send_message.call_args.kwargs["embed"]
    assert not embed.footer.text


# --- dm ---

async def test_dm_calls_user_send(ctx, interaction):
    interaction.user.send = AsyncMock()
    await ctx.dm("Hello!")
    interaction.user.send.assert_called_once_with("Hello!", embed=None)


async def test_dm_passes_kwargs(ctx, interaction):
    interaction.user.send = AsyncMock()
    embed = discord.Embed(title="T")
    await ctx.dm(embed=embed)
    interaction.user.send.assert_called_once_with(None, embed=embed)


# --- send_to ---

async def test_send_to_uses_cached_channel(ctx, interaction):
    mock_channel = MagicMock()
    mock_channel.send = AsyncMock()
    interaction.client.get_channel = MagicMock(return_value=mock_channel)
    await ctx.send_to(999, "hi")
    interaction.client.get_channel.assert_called_once_with(999)
    mock_channel.send.assert_called_once_with("hi")


async def test_send_to_fetches_when_not_cached(ctx, interaction):
    mock_channel = MagicMock()
    mock_channel.send = AsyncMock()
    interaction.client.get_channel = MagicMock(return_value=None)
    interaction.client.fetch_channel = AsyncMock(return_value=mock_channel)
    await ctx.send_to(999, "hi")
    interaction.client.fetch_channel.assert_called_once_with(999)
    mock_channel.send.assert_called_once_with("hi")


# ── voice_channel ─────────────────────────────────────────────────────────────

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


# ── edit_response ─────────────────────────────────────────────────────────────

async def test_edit_response_content(ctx, interaction):
    interaction.edit_original_response = AsyncMock()
    await ctx.edit_response("Updated!")
    interaction.edit_original_response.assert_called_once_with(content="Updated!", embed=None)


async def test_edit_response_with_embed(ctx, interaction):
    interaction.edit_original_response = AsyncMock()
    embed = discord.Embed(title="T")
    await ctx.edit_response(embed=embed)
    interaction.edit_original_response.assert_called_once_with(content=None, embed=embed)


async def test_edit_response_no_args(ctx, interaction):
    interaction.edit_original_response = AsyncMock()
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
        yield

    interaction.guild.bans = _bans
    await ctx.fetch_bans(limit=10)
    assert calls == [10]


async def test_fetch_bans_raises_outside_guild(ctx, interaction):
    interaction.guild = None
    with pytest.raises(RuntimeError, match="guild context"):
        await ctx.fetch_bans()


# ── purge (thread support) ────────────────────────────────────────────────────

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


# ── move_member (stage channel support) ──────────────────────────────────────

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


# ── fetch_member ──────────────────────────────────────────────────────────────

async def test_fetch_member_returns_member(ctx, interaction):
    member = MagicMock(spec=discord.Member)
    interaction.guild.fetch_member = AsyncMock(return_value=member)
    result = await ctx.fetch_member(42)
    assert result is member
    interaction.guild.fetch_member.assert_called_once_with(42)


async def test_fetch_member_raises_outside_guild(ctx, interaction):
    interaction.guild = None
    with pytest.raises(RuntimeError, match="guild context"):
        await ctx.fetch_member(42)


# ── bot_permissions ───────────────────────────────────────────────────────────

def test_bot_permissions_returns_permissions(ctx, interaction):
    perms = MagicMock(spec=discord.Permissions)
    me = MagicMock()
    interaction.guild.me = me
    interaction.channel.permissions_for = MagicMock(return_value=perms)
    result = ctx.bot_permissions
    assert result is perms
    interaction.channel.permissions_for.assert_called_once_with(me)


def test_bot_permissions_raises_outside_guild(ctx, interaction):
    interaction.guild = None
    with pytest.raises(RuntimeError, match="guild context"):
        _ = ctx.bot_permissions


# ── typing ────────────────────────────────────────────────────────────────────

def test_typing_delegates_to_channel(ctx, interaction):
    typing_cm = MagicMock()
    interaction.channel.typing = MagicMock(return_value=typing_cm)
    result = ctx.typing()
    assert result is typing_cm
    interaction.channel.typing.assert_called_once()


def test_typing_raises_when_no_channel(ctx, interaction):
    interaction.channel = None
    with pytest.raises(RuntimeError, match="channel"):
        ctx.typing()


# ── fetch_pinned_messages ─────────────────────────────────────────────────────

async def test_fetch_pinned_messages_returns_list(ctx, interaction):
    msg1 = MagicMock(spec=discord.Message)
    msg2 = MagicMock(spec=discord.Message)
    interaction.channel.pins = AsyncMock(return_value=[msg1, msg2])
    result = await ctx.fetch_pinned_messages()
    assert result == [msg1, msg2]
    interaction.channel.pins.assert_called_once()


async def test_fetch_pinned_messages_raises_when_no_channel(ctx, interaction):
    interaction.channel = None
    with pytest.raises(RuntimeError, match="channel"):
        await ctx.fetch_pinned_messages()
