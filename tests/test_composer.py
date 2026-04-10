import logging

import pytest

from easycord.composer import Composer
from easycord.bot import EasyCord
from easycord.plugin import Plugin


# ── build() ──────────────────────────────────────────────────


def test_build_returns_easycord():
    bot = Composer().build()
    assert isinstance(bot, EasyCord)


def test_default_sync_commands_is_true():
    bot = Composer().build()
    assert bot._sync_commands is True


def test_sync_commands_disabled():
    bot = Composer().sync_commands(False).build()
    assert bot._sync_commands is False


# ── Middleware registration ───────────────────────────────────


def test_use_logging_adds_middleware():
    bot = Composer().use_logging().build()
    assert len(bot._middleware) == 1


def test_use_guild_only_adds_middleware():
    bot = Composer().use_guild_only().build()
    assert len(bot._middleware) == 1


def test_use_rate_limit_adds_middleware():
    bot = Composer().use_rate_limit(max_calls=3, window_seconds=5.0).build()
    assert len(bot._middleware) == 1


def test_use_error_handler_adds_middleware():
    bot = Composer().use_error_handler().build()
    assert len(bot._middleware) == 1


def test_use_custom_middleware():
    async def my_mw(ctx, next):
        await next()

    bot = Composer().use(my_mw).build()
    assert bot._middleware == [my_mw]


def test_middleware_order_is_preserved():
    calls = []

    async def mw_a(ctx, next):
        calls.append("a")
        await next()

    async def mw_b(ctx, next):
        calls.append("b")
        await next()

    bot = Composer().use(mw_a).use(mw_b).build()
    assert bot._middleware == [mw_a, mw_b]


def test_chained_middleware_accumulates():
    bot = (
        Composer()
        .use_logging()
        .use_guild_only()
        .use_rate_limit()
        .use_error_handler()
        .build()
    )
    assert len(bot._middleware) == 4


# ── Plugin loading ────────────────────────────────────────────


def test_load_plugin_registers_plugin():
    class MyPlugin(Plugin):
        pass

    plugin = MyPlugin()
    bot = Composer().load_plugin(plugin).build()
    assert plugin in bot._plugins


def test_multiple_plugins_all_registered():
    class A(Plugin):
        pass

    class B(Plugin):
        pass

    a, b = A(), B()
    bot = Composer().load_plugin(a).load_plugin(b).build()
    assert bot._plugins == [a, b]


# ── Fluent interface ──────────────────────────────────────────


def test_all_methods_return_composer():
    async def dummy_mw(ctx, next):
        await next()

    c = Composer()
    assert c.sync_commands() is c
    assert c.use_logging() is c
    assert c.use_guild_only() is c
    assert c.use_rate_limit() is c
    assert c.use_error_handler() is c
    assert c.use(dummy_mw) is c
    assert c.load_plugin(Plugin()) is c
