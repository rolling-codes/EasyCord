"""Tests for MemberLoggingPlugin."""
import pytest
from easycord.plugins.member_logging import MemberLoggingPlugin
from easycord.testing import FakeContextBuilder


@pytest.fixture
def plugin():
    """Create a MemberLoggingPlugin instance for testing."""
    return MemberLoggingPlugin()


@pytest.mark.asyncio
async def test_on_member_join_without_channel(plugin):
    """Test member join event when no log channel configured."""
    from unittest.mock import Mock
    member = Mock()
    member.id = 123
    member.mention = "<@123>"
    member.guild = Mock()
    member.guild.id = 456
    member.guild.get_channel = Mock(return_value=None)

    # Should not raise when no channel is configured
    await plugin._on_member_join(member)


@pytest.mark.asyncio
async def test_on_member_remove_without_channel(plugin):
    """Test member remove event when no log channel configured."""
    from unittest.mock import Mock
    member = Mock()
    member.id = 123
    member.mention = "<@123>"
    member.guild = Mock()
    member.guild.id = 456
    member.guild.get_channel = Mock(return_value=None)

    # Should not raise when no channel is configured
    await plugin._on_member_remove(member)


@pytest.mark.asyncio
async def test_on_guild_channel_delete_without_log_channel(plugin):
    """Test channel delete event handles missing log channel gracefully."""
    from unittest.mock import Mock
    channel = Mock()
    channel.id = 123
    channel.guild = Mock()
    channel.guild.id = 456

    # Should not raise when channel doesn't match log channel
    await plugin._on_guild_channel_delete(channel)


@pytest.mark.asyncio
async def test_plugin_instantiation(plugin):
    """Test MemberLoggingPlugin can be instantiated."""
    assert isinstance(plugin, MemberLoggingPlugin)
