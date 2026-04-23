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


def test_user_command_attributes_on_plugin_method():
    from easycord.decorators import user_command
    class MyPlugin(Plugin):
        @user_command(name="Profile")
        async def profile(self, ctx, user):
            pass

    p = MyPlugin()
    assert getattr(p.profile, "_is_user_command", False) is True
    assert p.profile._context_menu_name == "Profile"


def test_message_command_attributes_on_plugin_method():
    from easycord.decorators import message_command
    class MyPlugin(Plugin):
        @message_command(name="Quote")
        async def quote(self, ctx, message):
            pass

    p = MyPlugin()
    assert getattr(p.quote, "_is_message_command", False) is True
    assert p.quote._context_menu_name == "Quote"


def test_component_attributes_on_plugin_method():
    from easycord.decorators import component
    class MyPlugin(Plugin):
        @component("btn_yes")
        async def yes_handler(self, ctx):
            pass
            
        @component
        async def no_handler(self, ctx):
            pass

    p = MyPlugin()
    assert getattr(p.yes_handler, "_is_component", False) is True
    assert p.yes_handler._component_id == "btn_yes"
    assert getattr(p.no_handler, "_is_component", False) is True
    assert p.no_handler._component_id == "no_handler"


def test_plugin_component_collision():
    from easycord.decorators import component
    from easycord.bot import Bot
    
    class PluginA(Plugin):
        @component("btn_same", scoped=False)
        async def handler1(self, ctx):
            pass
            
    class PluginB(Plugin):
        @component("btn_same", scoped=False)
        async def handler2(self, ctx):
            pass

    bot = Bot(db_backend="memory")
    bot.add_plugin(PluginA())
    
    with pytest.raises(ValueError, match="already registered by"):
        bot.add_plugin(PluginB())

def test_plugin_namespacing():
    from easycord.decorators import component
    from easycord.bot import Bot
    
    class PluginC(Plugin):
        @component("btn_same")
        async def handler1(self, ctx):
            pass
            
    class PluginD(Plugin):
        @component("btn_same")
        async def handler2(self, ctx):
            pass

    bot = Bot(db_backend="memory")
    bot.add_plugin(PluginC())
    bot.add_plugin(PluginD())
    
    assert "pluginc:btn_same" in bot.registry.components
    assert "plugind:btn_same" in bot.registry.components

def test_modal_attributes_on_plugin_method():
    from easycord.decorators import modal
    class MyPlugin(Plugin):
        @modal("form_feedback")
        async def feedback_handler(self, ctx, data):
            pass

    p = MyPlugin()
    assert getattr(p.feedback_handler, "_is_modal", False) is True
    assert p.feedback_handler._modal_id == "form_feedback"
    assert p.feedback_handler._modal_scoped is True
