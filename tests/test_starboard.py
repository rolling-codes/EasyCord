"""Tests for StarboardPlugin: config, archived-map RMW, archive/unarchive, gating."""
from __future__ import annotations

import datetime
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from easycord.plugins._config_manager import PluginConfigManager
from easycord.plugins.starboard import StarboardPlugin


def _make_plugin(tmp_path) -> StarboardPlugin:
    plugin = StarboardPlugin()
    plugin.config = PluginConfigManager(str(tmp_path / "starboard"))
    plugin._bot = MagicMock()
    return plugin


def _make_message(*, guild_id: int = 1, message_id: int = 555) -> MagicMock:
    message = MagicMock(spec=discord.Message)
    message.id = message_id
    message.content = "a starred message"
    message.created_at = datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)
    message.jump_url = "https://discord.com/jump"
    message.attachments = []
    message.author = MagicMock()
    message.author.display_name = "Author"
    message.author.avatar = None
    guild = MagicMock()
    guild.id = guild_id
    message.guild = guild
    return message


def _sendable_channel() -> MagicMock:
    channel = MagicMock(spec=discord.TextChannel)
    channel.send = AsyncMock()
    channel.fetch_message = AsyncMock()
    return channel


# ── config + archived-map RMW ─────────────────────────────────


@pytest.mark.asyncio
async def test_get_config_returns_defaults(tmp_path) -> None:
    plugin = _make_plugin(tmp_path)
    cfg = await plugin._get_config(1)
    assert cfg.get("emoji") == "⭐"
    assert cfg.get("threshold") == 3
    assert cfg.get("channel_id") is None


@pytest.mark.asyncio
async def test_update_config_persists(tmp_path) -> None:
    plugin = _make_plugin(tmp_path)
    await plugin._update_config(1, threshold=7, channel_id=42)
    cfg = await plugin._get_config(1)
    assert cfg.get("threshold") == 7
    assert cfg.get("channel_id") == 42


@pytest.mark.asyncio
async def test_archived_map_roundtrip(tmp_path) -> None:
    plugin = _make_plugin(tmp_path)
    await plugin._set_archived(1, message_id=555, post_id=999)
    archived = await plugin._get_archived(1)
    assert archived == {"555": 999}


@pytest.mark.asyncio
async def test_remove_archived_clears_entry(tmp_path) -> None:
    plugin = _make_plugin(tmp_path)
    await plugin._set_archived(1, message_id=555, post_id=999)
    await plugin._remove_archived(1, 555)
    assert await plugin._get_archived(1) == {}


# ── archive / unarchive flows ─────────────────────────────────


@pytest.mark.asyncio
async def test_archive_message_returns_early_without_channel(tmp_path) -> None:
    plugin = _make_plugin(tmp_path)
    message = _make_message()
    # No channel_id configured -> nothing posted, nothing archived.
    await plugin._archive_message(message, reaction_count=5)
    assert await plugin._get_archived(1) == {}


@pytest.mark.asyncio
async def test_archive_message_posts_and_stores_mapping(tmp_path) -> None:
    plugin = _make_plugin(tmp_path)
    await plugin._update_config(1, channel_id=123)
    channel = _sendable_channel()
    post = MagicMock()
    post.id = 999
    channel.send.return_value = post
    message = _make_message()
    message.guild.get_channel.return_value = channel

    await plugin._archive_message(message, reaction_count=5)

    channel.send.assert_awaited_once()
    assert await plugin._get_archived(1) == {"555": 999}


@pytest.mark.asyncio
async def test_archive_message_edits_existing_post(tmp_path) -> None:
    plugin = _make_plugin(tmp_path)
    await plugin._update_config(1, channel_id=123)
    await plugin._set_archived(1, message_id=555, post_id=999)
    channel = _sendable_channel()
    existing = MagicMock()
    existing.edit = AsyncMock()
    channel.fetch_message.return_value = existing
    message = _make_message()
    message.guild.get_channel.return_value = channel

    await plugin._archive_message(message, reaction_count=9)

    existing.edit.assert_awaited_once()
    channel.send.assert_not_called()


@pytest.mark.asyncio
async def test_unarchive_message_deletes_and_clears(tmp_path) -> None:
    plugin = _make_plugin(tmp_path)
    await plugin._update_config(1, channel_id=123)
    await plugin._set_archived(1, message_id=555, post_id=999)
    channel = _sendable_channel()
    post = MagicMock()
    post.delete = AsyncMock()
    channel.fetch_message.return_value = post
    guild = MagicMock()
    guild.get_channel.return_value = channel
    bot = MagicMock()
    bot.get_guild.return_value = guild
    plugin._bot = bot

    await plugin._unarchive_message(1, 555)

    post.delete.assert_awaited_once()
    assert await plugin._get_archived(1) == {}


@pytest.mark.asyncio
async def test_unarchive_message_cleans_up_on_notfound(tmp_path) -> None:
    plugin = _make_plugin(tmp_path)
    await plugin._update_config(1, channel_id=123)
    await plugin._set_archived(1, message_id=555, post_id=999)
    channel = _sendable_channel()
    channel.fetch_message.side_effect = discord.NotFound(MagicMock(), "gone")
    guild = MagicMock()
    guild.get_channel.return_value = channel
    bot = MagicMock()
    bot.get_guild.return_value = guild
    plugin._bot = bot

    await plugin._unarchive_message(1, 555)

    # Even though the post was already gone, the mapping must be removed.
    assert await plugin._get_archived(1) == {}


# ── slash command gating ──────────────────────────────────────


@pytest.mark.asyncio
async def test_threshold_rejects_below_one(tmp_path) -> None:
    plugin = _make_plugin(tmp_path)
    ctx = MagicMock()
    ctx.guild = MagicMock()
    ctx.guild.id = 1
    ctx.respond = AsyncMock()
    await plugin.starboard_threshold(ctx, 0)
    assert "at least 1" in ctx.respond.call_args.args[0].lower()
    # Config unchanged.
    cfg = await plugin._get_config(1)
    assert cfg.get("threshold") == 3


@pytest.mark.asyncio
async def test_set_channel_updates_config(tmp_path) -> None:
    plugin = _make_plugin(tmp_path)
    ctx = MagicMock()
    ctx.guild = MagicMock()
    ctx.guild.id = 1
    ctx.respond = AsyncMock()
    channel = MagicMock(spec=discord.TextChannel)
    channel.id = 777
    channel.mention = "#starboard"
    await plugin.starboard_channel(ctx, channel)
    cfg = await plugin._get_config(1)
    assert cfg.get("channel_id") == 777


@pytest.mark.asyncio
async def test_set_emoji_updates_config(tmp_path) -> None:
    plugin = _make_plugin(tmp_path)
    ctx = MagicMock()
    ctx.guild = MagicMock()
    ctx.guild.id = 1
    ctx.respond = AsyncMock()
    await plugin.starboard_emoji(ctx, "🌟")
    cfg = await plugin._get_config(1)
    assert cfg.get("emoji") == "🌟"


@pytest.mark.asyncio
async def test_starboard_config_shows_unset_channel(tmp_path) -> None:
    plugin = _make_plugin(tmp_path)
    ctx = MagicMock()
    ctx.guild = MagicMock()
    ctx.guild.id = 1
    ctx.guild.name = "Test Guild"
    ctx.respond = AsyncMock()
    await plugin.starboard_config(ctx)
    embed = ctx.respond.call_args.kwargs.get("embed")
    assert embed is not None
    fields = {f.name: f.value for f in embed.fields}
    assert fields["Channel"] == "*not set*"
    assert fields["Threshold"] == "3"
    assert fields["Emoji"] == "⭐"


# ── reaction event handlers ───────────────────────────────────


def _make_payload(*, guild_id=1, user_id=2, channel_id=10, message_id=555, emoji="⭐") -> MagicMock:
    payload = MagicMock()
    payload.guild_id = guild_id
    payload.user_id = user_id
    payload.channel_id = channel_id
    payload.message_id = message_id
    payload.emoji = emoji  # str(str) round-trips, matching str(payload.emoji) in the plugin
    return payload


def _make_bot(guild: MagicMock) -> MagicMock:
    bot = MagicMock()
    bot.user = MagicMock()
    bot.user.id = 999_999
    bot.get_guild.return_value = guild
    return bot


def _make_reaction(count: int, emoji: str = "⭐") -> MagicMock:
    reaction = MagicMock()
    reaction.emoji = emoji
    reaction.count = count
    return reaction


@pytest.mark.asyncio
async def test_reaction_add_ignores_dms(tmp_path) -> None:
    plugin = _make_plugin(tmp_path)
    bot = _make_bot(MagicMock())
    plugin._bot = bot
    await plugin._on_reaction_add(_make_payload(guild_id=None))
    bot.get_guild.assert_not_called()


@pytest.mark.asyncio
async def test_reaction_add_ignores_bots_own_reaction(tmp_path) -> None:
    plugin = _make_plugin(tmp_path)
    bot = _make_bot(MagicMock())
    plugin._bot = bot
    await plugin._on_reaction_add(_make_payload(user_id=bot.user.id))
    bot.get_guild.assert_not_called()


@pytest.mark.asyncio
async def test_reaction_add_ignores_unconfigured_emoji(tmp_path) -> None:
    plugin = _make_plugin(tmp_path)
    guild = MagicMock()
    guild.id = 1
    plugin._bot = _make_bot(guild)
    await plugin._on_reaction_add(_make_payload(emoji="🎉"))
    guild.get_channel.assert_not_called()


@pytest.mark.asyncio
async def test_reaction_add_skips_when_disabled(tmp_path) -> None:
    plugin = _make_plugin(tmp_path)
    await plugin._update_config(1, enabled=False)
    guild = MagicMock()
    guild.id = 1
    plugin._bot = _make_bot(guild)
    await plugin._on_reaction_add(_make_payload())
    guild.get_channel.assert_not_called()


@pytest.mark.asyncio
async def test_reaction_add_archives_at_threshold(tmp_path) -> None:
    plugin = _make_plugin(tmp_path)
    await plugin._update_config(1, channel_id=123)

    star_channel = _sendable_channel()
    post = MagicMock()
    post.id = 999
    star_channel.send.return_value = post

    message = _make_message()
    message.reactions = [_make_reaction(3)]
    message.guild.get_channel.return_value = star_channel

    source_channel = _sendable_channel()
    source_channel.fetch_message.return_value = message

    guild = MagicMock()
    guild.id = 1
    guild.get_channel.return_value = source_channel
    plugin._bot = _make_bot(guild)

    await plugin._on_reaction_add(_make_payload())

    star_channel.send.assert_awaited_once()
    assert await plugin._get_archived(1) == {"555": 999}


@pytest.mark.asyncio
async def test_reaction_add_below_threshold_does_not_archive(tmp_path) -> None:
    plugin = _make_plugin(tmp_path)
    await plugin._update_config(1, channel_id=123)

    star_channel = _sendable_channel()
    message = _make_message()
    message.reactions = [_make_reaction(2)]  # threshold defaults to 3
    message.guild.get_channel.return_value = star_channel

    source_channel = _sendable_channel()
    source_channel.fetch_message.return_value = message

    guild = MagicMock()
    guild.id = 1
    guild.get_channel.return_value = source_channel
    plugin._bot = _make_bot(guild)

    await plugin._on_reaction_add(_make_payload())

    star_channel.send.assert_not_called()
    assert await plugin._get_archived(1) == {}


@pytest.mark.asyncio
async def test_reaction_remove_unarchives_below_threshold(tmp_path) -> None:
    plugin = _make_plugin(tmp_path)
    await plugin._update_config(1, channel_id=123)
    await plugin._set_archived(1, message_id=555, post_id=999)

    post = MagicMock()
    post.delete = AsyncMock()
    star_channel = _sendable_channel()
    star_channel.fetch_message.return_value = post

    message = _make_message()
    message.reactions = []  # all stars gone

    source_channel = _sendable_channel()
    source_channel.fetch_message.return_value = message

    guild = MagicMock()
    guild.id = 1
    guild.get_channel.side_effect = lambda cid: {10: source_channel, 123: star_channel}[cid]
    plugin._bot = _make_bot(guild)

    await plugin._on_reaction_remove(_make_payload())

    post.delete.assert_awaited_once()
    assert await plugin._get_archived(1) == {}


@pytest.mark.asyncio
async def test_reaction_remove_keeps_archive_at_threshold(tmp_path) -> None:
    plugin = _make_plugin(tmp_path)
    await plugin._update_config(1, channel_id=123)
    await plugin._set_archived(1, message_id=555, post_id=999)

    star_channel = _sendable_channel()
    message = _make_message()
    message.reactions = [_make_reaction(5)]  # still >= threshold

    source_channel = _sendable_channel()
    source_channel.fetch_message.return_value = message

    guild = MagicMock()
    guild.id = 1
    guild.get_channel.side_effect = lambda cid: {10: source_channel, 123: star_channel}[cid]
    plugin._bot = _make_bot(guild)

    await plugin._on_reaction_remove(_make_payload())

    star_channel.fetch_message.assert_not_called()
    assert await plugin._get_archived(1) == {"555": 999}


@pytest.mark.asyncio
async def test_reaction_remove_ignores_unconfigured_emoji(tmp_path) -> None:
    plugin = _make_plugin(tmp_path)
    await plugin._set_archived(1, message_id=555, post_id=999)
    guild = MagicMock()
    guild.id = 1
    plugin._bot = _make_bot(guild)

    await plugin._on_reaction_remove(_make_payload(emoji="🎉"))

    guild.get_channel.assert_not_called()
    assert await plugin._get_archived(1) == {"555": 999}


@pytest.mark.asyncio
async def test_archive_message_forbidden_stores_nothing(tmp_path) -> None:
    plugin = _make_plugin(tmp_path)
    await plugin._update_config(1, channel_id=123)
    channel = _sendable_channel()
    channel.send.side_effect = discord.Forbidden(MagicMock(), "no perms")
    message = _make_message()
    message.guild.get_channel.return_value = channel

    # Must swallow the error, not raise into the dispatcher.
    await plugin._archive_message(message, reaction_count=5)

    assert await plugin._get_archived(1) == {}


@pytest.mark.asyncio
async def test_archive_message_resends_when_existing_post_gone(tmp_path) -> None:
    plugin = _make_plugin(tmp_path)
    await plugin._update_config(1, channel_id=123)
    await plugin._set_archived(1, message_id=555, post_id=999)

    channel = _sendable_channel()
    channel.fetch_message.side_effect = discord.NotFound(MagicMock(), "gone")
    new_post = MagicMock()
    new_post.id = 1000
    channel.send.return_value = new_post
    message = _make_message()
    message.guild.get_channel.return_value = channel

    await plugin._archive_message(message, reaction_count=5)

    channel.send.assert_awaited_once()
    assert await plugin._get_archived(1) == {"555": 1000}


@pytest.mark.asyncio
async def test_archive_message_skips_unsendable_channel(tmp_path) -> None:
    plugin = _make_plugin(tmp_path)
    await plugin._update_config(1, channel_id=123)
    message = _make_message()
    # Channel type outside SENDABLE_CHANNEL_TYPES (e.g. a category)
    message.guild.get_channel.return_value = MagicMock(spec=discord.CategoryChannel)

    await plugin._archive_message(message, reaction_count=5)

    assert await plugin._get_archived(1) == {}
