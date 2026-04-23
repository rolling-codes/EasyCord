import pytest
import discord
from unittest.mock import AsyncMock, MagicMock

from easycord.audit import AuditLog
from easycord.context import Context
from easycord.server_config import ServerConfig, ServerConfigStore


def _make_ctx(*, guild_id: int | None = 12345):
    interaction = MagicMock()
    interaction.user = MagicMock()
    interaction.command.name = "test"
    if guild_id is not None:
        guild = MagicMock()
        guild.id = guild_id
        interaction.guild = guild
    else:
        interaction.guild = None
    interaction.response.send_message = AsyncMock()
    return Context(interaction)


async def test_log_sends_embed_to_channel():
    store = MagicMock(spec=ServerConfigStore)
    cfg = ServerConfig(12345)
    cfg.set_channel("audit_log", 999)
    store.load = AsyncMock(return_value=cfg)

    mock_channel = MagicMock()
    mock_channel.send = AsyncMock()

    ctx = _make_ctx()
    ctx.interaction.client.get_channel = MagicMock(return_value=mock_channel)

    audit = AuditLog(store)
    await audit.log(ctx, action="kick", reason="Spamming")

    mock_channel.send.assert_called_once()
    embed = mock_channel.send.call_args.kwargs["embed"]
    assert "kick" in embed.title
    assert embed.color == discord.Color.orange()


async def test_log_includes_reason_field():
    store = MagicMock(spec=ServerConfigStore)
    cfg = ServerConfig(12345)
    cfg.set_channel("audit_log", 999)
    store.load = AsyncMock(return_value=cfg)

    mock_channel = MagicMock()
    mock_channel.send = AsyncMock()

    ctx = _make_ctx()
    ctx.interaction.client.get_channel = MagicMock(return_value=mock_channel)

    audit = AuditLog(store)
    await audit.log(ctx, action="ban", reason="Rule violation")

    embed = mock_channel.send.call_args.kwargs["embed"]
    field_names = [f.name for f in embed.fields]
    assert "Reason" in field_names


async def test_log_silent_when_no_channel_configured():
    store = MagicMock(spec=ServerConfigStore)
    cfg = ServerConfig(12345)  # no channel set
    store.load = AsyncMock(return_value=cfg)

    mock_channel = MagicMock()
    mock_channel.send = AsyncMock()

    ctx = _make_ctx()
    ctx.interaction.client.get_channel = MagicMock(return_value=mock_channel)

    audit = AuditLog(store, silent=True)
    await audit.log(ctx, action="kick")

    mock_channel.send.assert_not_called()


async def test_log_skips_in_dm():
    store = MagicMock(spec=ServerConfigStore)
    store.load = AsyncMock()

    ctx = _make_ctx(guild_id=None)

    audit = AuditLog(store)
    await audit.log(ctx, action="kick")

    store.load.assert_not_called()


async def test_log_extra_fields_appear_in_embed():
    store = MagicMock(spec=ServerConfigStore)
    cfg = ServerConfig(12345)
    cfg.set_channel("audit_log", 999)
    store.load = AsyncMock(return_value=cfg)

    mock_channel = MagicMock()
    mock_channel.send = AsyncMock()

    ctx = _make_ctx()
    ctx.interaction.client.get_channel = MagicMock(return_value=mock_channel)

    audit = AuditLog(store)
    await audit.log(ctx, action="warn", channel_name="general")

    embed = mock_channel.send.call_args.kwargs["embed"]
    field_names = [f.name for f in embed.fields]
    assert "Channel Name" in field_names


async def test_log_custom_channel_key():
    store = MagicMock(spec=ServerConfigStore)
    cfg = ServerConfig(12345)
    cfg.set_channel("mod_log", 888)
    store.load = AsyncMock(return_value=cfg)

    mock_channel = MagicMock()
    mock_channel.send = AsyncMock()

    ctx = _make_ctx()
    ctx.interaction.client.get_channel = MagicMock(return_value=mock_channel)

    audit = AuditLog(store, channel_key="mod_log")
    await audit.log(ctx, action="mute")

    mock_channel.send.assert_called_once()


async def test_log_fetch_channel_when_not_cached():
    store = MagicMock(spec=ServerConfigStore)
    cfg = ServerConfig(12345)
    cfg.set_channel("audit_log", 999)
    store.load = AsyncMock(return_value=cfg)

    mock_channel = MagicMock()
    mock_channel.send = AsyncMock()

    ctx = _make_ctx()
    ctx.interaction.client.get_channel = MagicMock(return_value=None)
    ctx.interaction.client.fetch_channel = AsyncMock(return_value=mock_channel)

    audit = AuditLog(store)
    await audit.log(ctx, action="kick")

    ctx.interaction.client.fetch_channel.assert_called_once_with(999)
    mock_channel.send.assert_called_once()


async def test_log_skips_when_client_missing():
    store = MagicMock(spec=ServerConfigStore)
    cfg = ServerConfig(12345)
    cfg.set_channel("audit_log", 999)
    store.load = AsyncMock(return_value=cfg)

    ctx = _make_ctx()
    ctx.interaction.client = None

    audit = AuditLog(store)
    await audit.log(ctx, action="kick")


async def test_log_skips_non_messageable_channel():
    store = MagicMock(spec=ServerConfigStore)
    cfg = ServerConfig(12345)
    cfg.set_channel("audit_log", 999)
    store.load = AsyncMock(return_value=cfg)

    ctx = _make_ctx()
    ctx.interaction.client.get_channel = MagicMock(return_value=object())

    audit = AuditLog(store)
    await audit.log(ctx, action="kick")
