"""Tests for StarboardPlugin."""
import pytest
from easycord.plugins.starboard import StarboardPlugin


@pytest.fixture
def plugin():
    """Create a StarboardPlugin instance for testing."""
    return StarboardPlugin()


@pytest.mark.asyncio
async def test_plugin_instantiation(plugin):
    """Test StarboardPlugin can be instantiated."""
    assert isinstance(plugin, StarboardPlugin)


@pytest.mark.asyncio
async def test_plugin_has_lifecycle_hooks(plugin):
    """Test StarboardPlugin has required lifecycle hooks."""
    assert hasattr(plugin, 'on_load')
    assert hasattr(plugin, 'on_unload')
