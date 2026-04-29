import logging

import pytest
from unittest.mock import MagicMock, patch

from easycord.bot import Bot
from easycord.composer import Composer
from easycord.plugin import Plugin


# ── build() ──────────────────────────────────────────────────


def test_build_returns_bot():
    bot = Composer().build()
    assert isinstance(bot, Bot)


def test_default_auto_sync_is_true():
    bot = Composer().build()
    assert bot._auto_sync is True


def test_auto_sync_disabled():
    bot = Composer().auto_sync(False).build()
    assert bot._auto_sync is False


def test_database_settings_forward_to_bot():
    db = MagicMock()
    with patch("easycord.composer.Bot", return_value=MagicMock()) as mock_bot:
        Composer().database(db).db_backend("memory").db_path("x.db").db_auto_sync_guilds(False).build()

    kwargs = mock_bot.call_args.kwargs
    assert kwargs["database"] is db
    assert kwargs["db_backend"] == "memory"
    assert kwargs["db_path"] == "x.db"
    assert kwargs["db_auto_sync_guilds"] is False


def test_builtin_plugins_flag_forwards_to_bot():
    with patch("easycord.composer.Bot", return_value=MagicMock()) as mock_bot:
        Composer().builtin_plugins().build()

    assert mock_bot.call_args.kwargs["load_builtin_plugins"] is True


def test_localization_settings_forward_to_bot():
    translations = {"en-US": {"hello": "Hello"}}
    localization = MagicMock()
    auto_translator = MagicMock()
    with patch("easycord.composer.Bot", return_value=MagicMock()) as mock_bot:
        (
            Composer()
            .localization(localization)
            .default_locale("en-US")
            .translations(translations)
            .auto_translator(auto_translator)
            .build()
        )

    kwargs = mock_bot.call_args.kwargs
    assert kwargs["localization"] is localization
    assert kwargs["default_locale"] == "en-US"
    assert kwargs["translations"] is translations
    assert kwargs["auto_translator"] is auto_translator


# ── Middleware registration ───────────────────────────────────


def test_log_adds_middleware():
    bot = Composer().log().build()
    assert len(bot._middleware) == 1


def test_guild_only_adds_middleware():
    bot = Composer().guild_only().build()
    assert len(bot._middleware) == 1


def test_rate_limit_adds_middleware():
    bot = Composer().rate_limit(limit=3, window=5.0).build()
    assert len(bot._middleware) == 1


def test_catch_errors_adds_middleware():
    bot = Composer().catch_errors().build()
    assert len(bot._middleware) == 1


def test_use_custom_middleware():
    async def my_mw(ctx, proceed):
        await proceed()

    bot = Composer().use(my_mw).build()
    assert bot._middleware == [my_mw]


def test_middleware_order_is_preserved():
    async def mw_a(ctx, proceed):
        await proceed()

    async def mw_b(ctx, proceed):
        await proceed()

    bot = Composer().use(mw_a).use(mw_b).build()
    assert bot._middleware == [mw_a, mw_b]


def test_chained_middleware_accumulates():
    bot = (
        Composer()
        .log()
        .guild_only()
        .rate_limit()
        .catch_errors()
        .build()
    )
    assert len(bot._middleware) == 4


def test_secure_defaults_adds_three_middlewares():
    bot = Composer().secure_defaults().build()
    assert len(bot._middleware) == 3


def test_convenience_framework_applies_expected_defaults():
    bot = Composer().convenience_framework(secure=True, guild_only=True).build()
    assert len(bot._middleware) == 4


def test_convenience_framework_can_enable_builtin_plugins():
    with patch("easycord.composer.Bot", return_value=MagicMock()) as mock_bot:
        Composer().convenience_framework(builtin_plugins=True).build()
    assert mock_bot.call_args.kwargs["load_builtin_plugins"] is True


# ── Plugin loading ────────────────────────────────────────────


def test_add_plugin_registers_plugin():
    class MyPlugin(Plugin):
        pass

    plugin = MyPlugin()
    bot = Composer().add_plugin(plugin).build()
    assert plugin in bot._plugins


def test_multiple_plugins_all_registered():
    class A(Plugin):
        pass

    class B(Plugin):
        pass

    a, b = A(), B()
    bot = Composer().add_plugin(a).add_plugin(b).build()
    assert bot._plugins == [a, b]


def test_add_plugins_registers_many():
    class A(Plugin):
        pass

    class B(Plugin):
        pass

    a, b = A(), B()
    bot = Composer().add_plugins(a, b).build()
    assert bot._plugins == [a, b]


def test_add_groups_registers_many():
    from easycord import SlashGroup

    class A(SlashGroup, name="a", description="A"):
        pass

    class B(SlashGroup, name="b", description="B"):
        pass

    a, b = A(), B()
    composer = Composer().add_groups(a, b)
    assert composer._groups == [a, b]

    bot = composer.build()
    assert bot._plugins == [a, b]


# ── Fluent interface ──────────────────────────────────────────


def test_all_methods_return_composer():
    async def dummy_mw(ctx, proceed):
        await proceed()

    c = Composer()
    assert c.auto_sync() is c
    assert c.log() is c
    assert c.guild_only() is c
    assert c.rate_limit() is c
    assert c.catch_errors() is c
    assert c.default_locale("en-US") is c
    assert c.translations({"en-US": {"hello": "Hello"}}) is c
    assert c.auto_translator(None) is c
    assert c.use(dummy_mw) is c
    assert c.add_plugin(Plugin()) is c
    assert c.add_plugins(Plugin(), Plugin()) is c
    assert c.add_groups() is c
