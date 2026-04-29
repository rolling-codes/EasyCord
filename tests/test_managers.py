import logging

from easycord import Composer
from easycord.bot import Bot
from easycord.managers import FrameworkManager, SecurityManager
from easycord.plugin import Plugin


def test_security_manager_build_returns_three_middleware_items():
    manager = SecurityManager()
    built = manager.build()
    assert len(built) == 3


def test_security_manager_apply_to_bot_registers_middleware():
    bot = Bot(auto_sync=False)
    manager = SecurityManager(
        log_level=logging.DEBUG,
        rate_limit=3,
        rate_window=4.0,
    )
    manager.apply(bot)
    assert len(bot._middleware) == 3


def test_security_manager_apply_to_composer_registers_middleware():
    composer = Composer()
    SecurityManager().apply_to_composer(composer)
    bot = composer.build()
    assert len(bot._middleware) == 3


def test_framework_manager_bootstrap_secure_and_guild_only():
    composer = FrameworkManager.bootstrap(secure=True, guild_only=True)
    bot = composer.build()
    assert len(bot._middleware) == 4


def test_framework_manager_bootstrap_supports_plugins():
    class DemoPlugin(Plugin):
        pass

    plugin = DemoPlugin()
    composer = FrameworkManager.bootstrap(plugins=(plugin,))
    bot = composer.build()
    assert plugin in bot._plugins


def test_framework_manager_build_bot_shortcuts_composer_build():
    bot = FrameworkManager.build_bot(secure=True, guild_only=True)
    assert len(bot._middleware) == 4
