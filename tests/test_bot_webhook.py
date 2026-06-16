"""Tests for Bot.send_webhook argument forwarding and stale-webhook recovery."""
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from easycord import Bot


def _text_channel_with_webhook(webhook: MagicMock) -> MagicMock:
    channel = MagicMock(spec=discord.TextChannel)
    channel.create_webhook = AsyncMock(return_value=webhook)
    return channel


@pytest.mark.asyncio
async def test_send_webhook_only_forwards_supplied_arguments() -> None:
    # Arrange
    bot = Bot(auto_sync=False, db_backend="memory")
    webhook = MagicMock()
    webhook.send = AsyncMock()
    bot.get_channel = MagicMock(return_value=_text_channel_with_webhook(webhook))

    # Act
    await bot.send_webhook(123, "hello")

    # Assert — None-valued username/avatar_url/embed are omitted, not passed as None
    webhook.send.assert_awaited_once_with(content="hello")


@pytest.mark.asyncio
async def test_send_webhook_forwards_all_provided_keyword_arguments() -> None:
    # Arrange
    bot = Bot(auto_sync=False, db_backend="memory")
    webhook = MagicMock()
    webhook.send = AsyncMock()
    bot.get_channel = MagicMock(return_value=_text_channel_with_webhook(webhook))
    embed = discord.Embed(title="hi")

    # Act
    await bot.send_webhook(123, "body", username="Robo", avatar_url="http://x/a.png", embed=embed)

    # Assert
    webhook.send.assert_awaited_once_with(
        content="body", username="Robo", avatar_url="http://x/a.png", embed=embed
    )


@pytest.mark.asyncio
async def test_send_webhook_rejects_non_text_channel() -> None:
    # Arrange
    bot = Bot(auto_sync=False, db_backend="memory")
    bot.get_channel = MagicMock(return_value=MagicMock(spec=discord.VoiceChannel))

    # Act / Assert
    with pytest.raises(RuntimeError, match="not a text channel"):
        await bot.send_webhook(123, "hello")


@pytest.mark.asyncio
async def test_send_webhook_recreates_stale_webhook_on_not_found() -> None:
    # Arrange
    bot = Bot(auto_sync=False, db_backend="memory")
    stale = MagicMock()
    stale.send = AsyncMock(
        side_effect=discord.NotFound(MagicMock(status=404), "gone")
    )
    fresh = MagicMock()
    fresh.send = AsyncMock()
    channel = MagicMock(spec=discord.TextChannel)
    channel.create_webhook = AsyncMock(side_effect=[stale, fresh])
    bot.get_channel = MagicMock(return_value=channel)

    # Act
    await bot.send_webhook(123, "hello")

    # Assert — the cache was rebuilt and the retry used the fresh webhook
    fresh.send.assert_awaited_once_with(content="hello")
    assert channel.create_webhook.await_count == 2
