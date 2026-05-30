"""Tests for InviteTrackerPlugin."""
import pytest
from easycord.plugins.invite_tracker import InviteTrackerPlugin
from easycord.testing import FakeContextBuilder


@pytest.fixture
def plugin():
    """Create an InviteTrackerPlugin instance for testing."""
    return InviteTrackerPlugin()


@pytest.mark.asyncio
async def test_invite_tracker_config_shows_current(plugin):
    """Test invite_tracker_config command displays current settings."""
    ctx = FakeContextBuilder().build()
    await plugin.invite_tracker_config(ctx)
    assert "invite" in ctx.last_response.lower() or "config" in ctx.last_response.lower()


@pytest.mark.asyncio
async def test_on_guild_channel_delete_without_log_channel(plugin):
    """Test channel delete handles missing log channel gracefully."""
    from unittest.mock import Mock
    channel = Mock()
    channel.id = 123
    channel.guild = Mock()
    channel.guild.id = 456

    # Should not raise when no log channel configured
    await plugin._on_guild_channel_delete(channel)


@pytest.mark.asyncio
async def test_plugin_instantiation(plugin):
    """Test InviteTrackerPlugin can be instantiated."""
    assert isinstance(plugin, InviteTrackerPlugin)
