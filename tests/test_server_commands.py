from server_commands import (
    DEFAULT_PLUGINS,
    FunPlugin,
    InfoPlugin,
    ModerationPlugin,
    build_default_plugins,
    load_default_plugins,
)


def test_default_plugins_are_defined_in_one_place():
    assert DEFAULT_PLUGINS == (FunPlugin, ModerationPlugin, InfoPlugin)


def test_build_default_plugins_creates_plugin_instances():
    plugins = build_default_plugins()

    assert isinstance(plugins[0], FunPlugin)
    assert isinstance(plugins[1], ModerationPlugin)
    assert isinstance(plugins[2], InfoPlugin)


def test_load_default_plugins_registers_each_plugin():
    class Collector:
        def __init__(self):
            self.plugins = []

        def add_plugin(self, plugin):
            self.plugins.append(plugin)

    bot = Collector()

    load_default_plugins(bot)

    assert len(bot.plugins) == 3
    assert isinstance(bot.plugins[0], FunPlugin)
    assert isinstance(bot.plugins[1], ModerationPlugin)
    assert isinstance(bot.plugins[2], InfoPlugin)


def test_load_default_plugins_prefers_bulk_add_plugins():
    class Collector:
        def __init__(self):
            self.plugins = []
            self.calls = 0

        def add_plugins(self, *plugins):
            self.calls += 1
            self.plugins.extend(plugins)

        def add_plugin(self, plugin):
            raise AssertionError("fallback path should not be used when add_plugins exists")

    bot = Collector()

    load_default_plugins(bot)

    assert bot.calls == 1
    assert len(bot.plugins) == 3
    assert isinstance(bot.plugins[0], FunPlugin)
    assert isinstance(bot.plugins[1], ModerationPlugin)
    assert isinstance(bot.plugins[2], InfoPlugin)
