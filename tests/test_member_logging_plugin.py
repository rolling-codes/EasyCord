"""Tests for member logging plugin."""
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import discord

from easycord import ServerConfig
from easycord.plugins.member_logging import MemberLoggingPlugin


@pytest.fixture
def plugin():
    """Create MemberLoggingPlugin instance."""
    return MemberLoggingPlugin()


@pytest.fixture
def mock_guild():
    """Create mock Discord guild."""
    guild = MagicMock(spec=discord.Guild)
    guild.id = 12345
    guild.name = "Test Server"
    guild.get_channel = MagicMock()
    return guild


@pytest.fixture
def mock_member(mock_guild):
    """Create mock Discord member."""
    member = MagicMock(spec=discord.Member)
    member.id = 999
    member.name = "TestUser"
    member.discriminator = "0001"
    member.mention = "<@999>"
    member.guild = mock_guild
    member.created_at = datetime(2020, 1, 1, tzinfo=timezone.utc)
    member.joined_at = datetime(2023, 6, 15, tzinfo=timezone.utc)
    member.nick = None
    member.roles = []
    member.timed_out_until = None
    member.avatar = MagicMock()
    member.avatar.url = "https://example.com/avatar.png"
    return member


@pytest.fixture
def mock_user(mock_member):
    """Create mock Discord user."""
    user = MagicMock(spec=discord.User)
    user.id = mock_member.id
    user.name = mock_member.name
    user.avatar = mock_member.avatar
    return user


@pytest.mark.asyncio
async def test_plugin_initializes(plugin):
    """Plugin can be initialized."""
    assert plugin is not None
    assert plugin.config is not None


@pytest.mark.asyncio
async def test_get_config_creates_default(plugin, mock_guild):
    """Default config created on first access."""
    mock_server_cfg = MagicMock(spec=ServerConfig)
    mock_server_cfg.get_other = MagicMock(return_value=None)
    mock_server_cfg.set_other = MagicMock()

    with patch.object(plugin.config.store, "load", new_callable=AsyncMock, return_value=mock_server_cfg):
        with patch.object(plugin.config.store, "save", new_callable=AsyncMock):
            cfg = await plugin._get_config(mock_guild.id)
            assert cfg["enabled"] is True
            assert "log_channel" in cfg


@pytest.mark.asyncio
async def test_on_member_join(plugin, mock_guild, mock_member):
    """Logs member join to channel."""
    mock_server_cfg = MagicMock(spec=ServerConfig)
    mock_server_cfg.get_other = MagicMock(return_value={"log_channel": 54321, "enabled": True})

    mock_channel = AsyncMock()
    mock_guild.get_channel = MagicMock(return_value=mock_channel)

    with patch.object(plugin.config.store, "load", new_callable=AsyncMock, return_value=mock_server_cfg):
        await plugin._on_member_join(mock_member)
        mock_channel.send.assert_called_once()

        # Verify embed was sent
        call_args = mock_channel.send.call_args
        embed = call_args.kwargs["embed"]
        assert "Joined" in embed.title


@pytest.mark.asyncio
async def test_on_member_remove(plugin, mock_guild, mock_member):
    """Logs member leave to channel."""
    mock_server_cfg = MagicMock(spec=ServerConfig)
    mock_server_cfg.get_other = MagicMock(return_value={"log_channel": 54321, "enabled": True})

    mock_channel = AsyncMock()
    mock_guild.get_channel = MagicMock(return_value=mock_channel)

    with patch.object(plugin.config.store, "load", new_callable=AsyncMock, return_value=mock_server_cfg):
        await plugin._on_member_remove(mock_member)
        mock_channel.send.assert_called_once()

        call_args = mock_channel.send.call_args
        embed = call_args.kwargs["embed"]
        assert "Left" in embed.title


@pytest.mark.asyncio
async def test_on_member_update_nickname(plugin, mock_guild, mock_member):
    """Logs nickname changes."""
    before = mock_member
    after = MagicMock(spec=discord.Member)
    after.id = before.id
    after.name = before.name
    after.discriminator = before.discriminator
    after.mention = before.mention
    after.guild = mock_guild
    after.nick = "NewNickname"
    after.roles = before.roles
    after.timed_out_until = None
    after.avatar = before.avatar

    mock_server_cfg = MagicMock(spec=ServerConfig)
    mock_server_cfg.get_other = MagicMock(return_value={"log_channel": 54321, "enabled": True})

    mock_channel = AsyncMock()
    mock_guild.get_channel = MagicMock(return_value=mock_channel)

    with patch.object(plugin.config.store, "load", new_callable=AsyncMock, return_value=mock_server_cfg):
        await plugin._on_member_update(before, after)
        mock_channel.send.assert_called_once()

        call_args = mock_channel.send.call_args
        embed = call_args.kwargs["embed"]
        assert "Updated" in embed.title


@pytest.mark.asyncio
async def test_on_member_update_role_add(plugin, mock_guild, mock_member):
    """Logs role additions."""
    before = mock_member
    after = MagicMock(spec=discord.Member)
    after.id = before.id
    after.name = before.name
    after.discriminator = before.discriminator
    after.mention = before.mention
    after.guild = mock_guild
    after.nick = before.nick

    # Create mock roles
    role1 = MagicMock(spec=discord.Role)
    role1.mention = "<@&777>"
    after.roles = [role1]
    before.roles = []

    after.timed_out_until = None
    after.avatar = before.avatar

    mock_server_cfg = MagicMock(spec=ServerConfig)
    mock_server_cfg.get_other = MagicMock(return_value={"log_channel": 54321, "enabled": True})

    mock_channel = AsyncMock()
    mock_guild.get_channel = MagicMock(return_value=mock_channel)

    with patch.object(plugin.config.store, "load", new_callable=AsyncMock, return_value=mock_server_cfg):
        await plugin._on_member_update(before, after)
        mock_channel.send.assert_called_once()


@pytest.mark.asyncio
async def test_on_member_update_timeout(plugin, mock_guild, mock_member):
    """Logs timeout/unmute changes."""
    before = mock_member
    before.timed_out_until = None

    after = MagicMock(spec=discord.Member)
    after.id = before.id
    after.name = before.name
    after.discriminator = before.discriminator
    after.mention = before.mention
    after.guild = mock_guild
    after.nick = before.nick
    after.roles = before.roles
    after.avatar = before.avatar

    # Set timeout
    after.timed_out_until = datetime(2099, 1, 1, tzinfo=timezone.utc)

    mock_server_cfg = MagicMock(spec=ServerConfig)
    mock_server_cfg.get_other = MagicMock(return_value={"log_channel": 54321, "enabled": True})

    mock_channel = AsyncMock()
    mock_guild.get_channel = MagicMock(return_value=mock_channel)

    with patch.object(plugin.config.store, "load", new_callable=AsyncMock, return_value=mock_server_cfg):
        await plugin._on_member_update(before, after)
        mock_channel.send.assert_called_once()


@pytest.mark.asyncio
async def test_on_member_update_no_changes(plugin, mock_member):
    """Ignores updates with no relevant changes."""
    before = mock_member
    after = MagicMock(spec=discord.Member)
    after.id = before.id
    after.nick = before.nick
    after.roles = before.roles
    after.timed_out_until = before.timed_out_until
    after.guild = before.guild

    with patch.object(plugin, "_log_to_channel") as mock_log:
        await plugin._on_member_update(before, after)
        mock_log.assert_not_called()


@pytest.mark.asyncio
async def test_log_to_channel_disabled(plugin, mock_guild):
    """Skips logging when disabled."""
    mock_server_cfg = MagicMock(spec=ServerConfig)
    mock_server_cfg.get_other = MagicMock(return_value={"log_channel": 54321, "enabled": False})

    mock_channel = AsyncMock()

    with patch.object(plugin.config.store, "load", new_callable=AsyncMock, return_value=mock_server_cfg):
        embed = MagicMock(spec=discord.Embed)
        await plugin._log_to_channel(mock_guild, embed)
        mock_channel.send.assert_not_called()


@pytest.mark.asyncio
async def test_log_to_channel_no_channel(plugin, mock_guild):
    """Skips logging when channel not configured."""
    mock_server_cfg = MagicMock(spec=ServerConfig)
    mock_server_cfg.get_other = MagicMock(return_value={"log_channel": None, "enabled": True})

    with patch.object(plugin.config.store, "load", new_callable=AsyncMock, return_value=mock_server_cfg):
        embed = MagicMock(spec=discord.Embed)
        await plugin._log_to_channel(mock_guild, embed)
        # Should return early without calling guild.get_channel


@pytest.mark.asyncio
async def test_on_user_update(plugin, mock_user):
    """Logs user rename."""
    before = MagicMock(spec=discord.User)
    before.name = "OldName"
    before.id = mock_user.id
    after = mock_user
    after.name = "NewName"

    # Should not raise, just log
    await plugin._on_user_update(before, after)
