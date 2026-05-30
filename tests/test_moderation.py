"""Tests for ModerationPlugin."""
import pytest
from easycord.plugins.moderation import ModerationPlugin
from easycord.testing import FakeContextBuilder


@pytest.fixture
def plugin():
    """Create a ModerationPlugin instance for testing."""
    return ModerationPlugin()


@pytest.mark.asyncio
async def test_kick_requires_permission(plugin):
    """Test kick command checks permissions."""
    ctx = FakeContextBuilder().build()
    from unittest.mock import Mock
    user = Mock()
    user.id = 123
    user.mention = "<@123>"

    await plugin.kick(ctx, user)
    assert "lack" in ctx.last_response or "permission" in ctx.last_response


@pytest.mark.asyncio
async def test_ban_requires_permission(plugin):
    """Test ban command checks permissions."""
    ctx = FakeContextBuilder().build()
    from unittest.mock import Mock
    user = Mock()
    user.id = 123
    user.mention = "<@123>"

    await plugin.ban(ctx, user)
    assert "lack" in ctx.last_response or "permission" in ctx.last_response


@pytest.mark.asyncio
async def test_timeout_requires_permission(plugin):
    """Test timeout command checks permissions."""
    ctx = FakeContextBuilder().build()
    from unittest.mock import Mock
    user = Mock()
    user.id = 123
    user.mention = "<@123>"

    await plugin.timeout(ctx, user, 5)
    assert "lack" in ctx.last_response or "permission" in ctx.last_response


@pytest.mark.asyncio
async def test_warn_requires_permission(plugin):
    """Test warn command checks permissions."""
    ctx = FakeContextBuilder().build()
    from unittest.mock import Mock
    user = Mock()
    user.id = 123
    user.mention = "<@123>"

    await plugin.warn(ctx, user)
    assert "lack" in ctx.last_response or "permission" in ctx.last_response


@pytest.mark.asyncio
async def test_unmute_requires_permission(plugin):
    """Test unmute command checks permissions."""
    ctx = FakeContextBuilder().build()
    from unittest.mock import Mock
    user = Mock()
    user.id = 123
    user.mention = "<@123>"

    await plugin.unmute(ctx, user)
    assert "lack" in ctx.last_response or "permission" in ctx.last_response


@pytest.mark.asyncio
async def test_warnings_empty(plugin):
    """Test viewing warnings when user has none."""
    ctx = FakeContextBuilder().build()
    from unittest.mock import Mock
    user = Mock()
    user.id = 123
    user.mention = "<@123>"
    user.name = "TestUser"

    await plugin.warnings(ctx, user)
    assert "no warnings" in ctx.last_response
