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
