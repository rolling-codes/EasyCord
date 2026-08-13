"""Tests for easycord.hooks.HookRegistry."""
from __future__ import annotations


import pytest

from easycord import Bot, Plugin, slash
from easycord.hooks import SUPPORTED_HOOKS, HookRegistry
from easycord.testing import invoke


def test_registry_initialises_all_supported_hooks():
    registry = HookRegistry()
    assert set(registry._callbacks.keys()) == SUPPORTED_HOOKS


async def test_register_and_fire_sync_callback():
    registry = HookRegistry()
    log: list[str] = []
    registry.register("before_command", lambda ctx: log.append(ctx))
    await registry.fire("before_command", ctx="fake_ctx")
    assert log == ["fake_ctx"]


async def test_register_and_fire_async_callback():
    registry = HookRegistry()
    log: list[str] = []

    async def handler(ctx: str) -> None:
        log.append(ctx)

    registry.register("after_command", handler)
    await registry.fire("after_command", ctx="fake_ctx")
    assert log == ["fake_ctx"]


async def test_multiple_callbacks_all_fired_in_order():
    registry = HookRegistry()
    log: list[str] = []
    registry.register("before_command", lambda: log.append("first"))
    registry.register("before_command", lambda: log.append("second"))
    await registry.fire("before_command")
    assert log == ["first", "second"]


async def test_fire_hook_with_no_registered_callbacks():
    registry = HookRegistry()
    await registry.fire("on_plugin_load")  # must not raise


def test_register_unsupported_hook_raises_value_error():
    registry = HookRegistry()
    with pytest.raises(ValueError, match="Unsupported hook"):
        registry.register("nonexistent_hook", lambda: None)


async def test_fire_unsupported_hook_raises_value_error():
    registry = HookRegistry()
    with pytest.raises(ValueError, match="Unsupported hook"):
        await registry.fire("nonexistent_hook")


def test_register_non_callable_raises_type_error():
    registry = HookRegistry()
    with pytest.raises(TypeError, match="Callback must be callable"):
        registry.register("before_command", "not_a_callable")  # type: ignore[arg-type]


async def test_before_command_hook_receives_kwargs():
    registry = HookRegistry()
    received: dict[str, object] = {}

    def handler(ctx: object, name: str) -> None:
        received["ctx"] = ctx
        received["name"] = name

    registry.register("before_command", handler)
    await registry.fire("before_command", ctx="ctx_obj", name="ping")
    assert received == {"ctx": "ctx_obj", "name": "ping"}


async def test_after_command_hook():
    registry = HookRegistry()
    called: list[bool] = []
    registry.register("after_command", lambda: called.append(True))
    await registry.fire("after_command")
    assert called == [True]


async def test_on_plugin_load_hook():
    registry = HookRegistry()
    plugins: list[str] = []
    registry.register("on_plugin_load", lambda plugin: plugins.append(plugin))
    await registry.fire("on_plugin_load", plugin="MyPlugin")
    assert plugins == ["MyPlugin"]


async def test_on_plugin_unload_hook():
    registry = HookRegistry()
    plugins: list[str] = []
    registry.register("on_plugin_unload", lambda plugin: plugins.append(plugin))
    await registry.fire("on_plugin_unload", plugin="MyPlugin")
    assert plugins == ["MyPlugin"]


async def test_mixed_sync_and_async_callbacks_in_same_hook():
    registry = HookRegistry()
    log: list[str] = []

    async def async_cb() -> None:
        log.append("async")

    registry.register("before_command", lambda: log.append("sync"))
    registry.register("before_command", async_cb)
    await registry.fire("before_command")
    assert log == ["sync", "async"]


async def test_all_four_hooks_can_register_and_fire():
    registry = HookRegistry()
    fired: set[str] = set()
    for hook in SUPPORTED_HOOKS:
        registry.register(hook, lambda h=hook: fired.add(h))
    for hook in SUPPORTED_HOOKS:
        await registry.fire(hook)
    assert fired == SUPPORTED_HOOKS


async def test_unregister_removes_callback():
    registry = HookRegistry()
    called = []
    cb = lambda **kw: called.append(kw)
    registry.register("before_command", cb)
    assert registry.unregister("before_command", cb) is True
    await registry.fire("before_command", ctx=None, name="ping")
    assert called == []


async def test_unregister_returns_false_when_not_registered():
    registry = HookRegistry()
    cb = lambda **kw: None
    result = registry.unregister("before_command", cb)
    assert result is False


async def test_unregister_idempotent_on_repeat():
    registry = HookRegistry()
    cb = lambda **kw: None
    registry.register("after_command", cb)
    assert registry.unregister("after_command", cb) is True
    assert registry.unregister("after_command", cb) is False


async def test_unregister_invalid_hook_raises():
    registry = HookRegistry()
    with pytest.raises(ValueError, match="Unsupported hook"):
        registry.unregister("no_such_hook", lambda: None)


async def test_unregister_removes_only_target_callback():
    registry = HookRegistry()
    calls: list[str] = []
    cb_a = lambda **kw: calls.append("a")
    cb_b = lambda **kw: calls.append("b")
    registry.register("before_command", cb_a)
    registry.register("before_command", cb_b)
    registry.unregister("before_command", cb_a)
    await registry.fire("before_command", ctx=None, name="x")
    assert calls == ["b"]


async def test_bot_exposes_hooks_and_fires_around_command_execution():
    bot = Bot(auto_sync=False, db_backend="memory")
    calls: list[tuple[str, str]] = []

    bot.hooks.register("before_command", lambda ctx, name: calls.append(("before", name)))
    bot.hooks.register("after_command", lambda ctx, name: calls.append(("after", name)))

    @bot.slash(description="Ping")
    async def ping(ctx):
        calls.append(("handler", "ping"))
        await ctx.respond("pong")

    try:
        ctx = await invoke(bot, "ping")
        assert ctx.last_response == "pong"
        assert calls == [("before", "ping"), ("handler", "ping"), ("after", "ping")]
    finally:
        await bot.close()


async def test_bot_fires_plugin_unload_hook():
    class EmptyPlugin(Plugin):
        pass

    bot = Bot(auto_sync=False, db_backend="memory")
    unloaded: list[str] = []
    bot.hooks.register("on_plugin_unload", lambda plugin_name: unloaded.append(plugin_name))

    plugin = EmptyPlugin()
    bot.add_plugin(plugin)
    try:
        await bot.remove_plugin(plugin)
        assert unloaded == [plugin.name]
    finally:
        await bot.close()
