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
