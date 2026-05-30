"""Tests for SuggestionsPlugin."""
import pytest
from easycord.plugins.suggestions import SuggestionsPlugin
from easycord.testing import FakeContextBuilder


@pytest.fixture
def plugin():
    """Create a SuggestionsPlugin instance for testing."""
    return SuggestionsPlugin()


@pytest.mark.asyncio
async def test_suggest_channel_not_configured(plugin):
    """Test suggest command fails gracefully when channel not configured."""
    ctx = FakeContextBuilder().build()
    await plugin.suggest(ctx, "This is my great idea")
    assert "not configured" in ctx.last_response


@pytest.mark.asyncio
async def test_suggestion_approve_not_found(plugin):
    """Test approving a non-existent suggestion."""
    ctx = FakeContextBuilder().with_permissions(manage_guild=True).build()
    await plugin.suggestion_approve(ctx, 999)
    assert "not found" in ctx.last_response


@pytest.mark.asyncio
async def test_suggestion_reject_not_found(plugin):
    """Test rejecting a non-existent suggestion."""
    ctx = FakeContextBuilder().with_permissions(manage_guild=True).build()
    await plugin.suggestion_reject(ctx, 999)
    assert "not found" in ctx.last_response


@pytest.mark.asyncio
async def test_suggestions_empty(plugin):
    """Test viewing suggestions when none exist."""
    ctx = FakeContextBuilder().build()
    await plugin.suggestions(ctx)
    assert "no pending" in ctx.last_response.lower()


@pytest.mark.asyncio
async def test_get_next_id_increments(plugin):
    """Test suggestion ID counter increments."""
    guild_id = 12345
    id1 = await plugin._get_next_id(guild_id)
    id2 = await plugin._get_next_id(guild_id)
    assert id2 > id1
