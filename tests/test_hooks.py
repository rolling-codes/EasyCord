"""Tests for easycord.hooks.HookRegistry."""
from __future__ import annotations

import asyncio

import pytest

from easycord.hooks import SUPPORTED_HOOKS, HookRegistry


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
