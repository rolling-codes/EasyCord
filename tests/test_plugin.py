import pytest
from unittest.mock import MagicMock

from easycord.plugin import Plugin
from easycord.decorators import slash, on


def test_bot_property_raises_when_not_loaded():
    plugin = Plugin()
    with pytest.raises(RuntimeError, match="has not been added"):
        _ = plugin.bot


def test_bot_property_returns_bot_when_loaded():
    plugin = Plugin()
    mock_bot = MagicMock()
    plugin._bot = mock_bot
    assert plugin.bot is mock_bot


async def test_on_load_is_noop():
    plugin = Plugin()
    await plugin.on_load()  # should not raise


async def test_on_unload_is_noop():
    plugin = Plugin()
    await plugin.on_unload()  # should not raise


def test_slash_decorator_attributes_on_plugin_method():
    class MyPlugin(Plugin):
        @slash(description="Say hello", guild_id=99)
        async def hello(self, ctx):
            pass

    p = MyPlugin()
    assert p.hello._is_slash is True
    assert p.hello._slash_name == "hello"
    assert p.hello._slash_desc == "Say hello"
    assert p.hello._slash_guild == 99


def test_on_decorator_attributes_on_plugin_method():
    class MyPlugin(Plugin):
        @on("member_join")
        async def greet(self, member):
            pass

    p = MyPlugin()
    assert p.greet._is_event is True
    assert p.greet._event_name == "member_join"
