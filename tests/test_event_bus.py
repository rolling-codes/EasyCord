"""Tests for easycord.event_bus.EventBus."""
from __future__ import annotations

import logging

import pytest

from easycord.event_bus import EventBus


async def test_subscribe_and_publish_sync_callback():
    bus = EventBus()
    received: list[int] = []
    bus.subscribe("test_event", lambda x: received.append(x))
    await bus.publish("test_event", x=42)
    assert received == [42]


async def test_subscribe_and_publish_async_callback():
    bus = EventBus()
    received: list[int] = []

    async def handler(x: int) -> None:
        received.append(x)

    bus.subscribe("test_event", handler)
    await bus.publish("test_event", x=99)
    assert received == [99]


async def test_multiple_subscribers_all_called():
    bus = EventBus()
    log: list[str] = []
    bus.subscribe("ev", lambda: log.append("a"))
    bus.subscribe("ev", lambda: log.append("b"))
    await bus.publish("ev")
    assert log == ["a", "b"]


async def test_publish_unknown_event_is_noop():
    bus = EventBus()
    await bus.publish("does_not_exist")  # must not raise


async def test_unsubscribe_removes_callback():
    bus = EventBus()
    called: list[bool] = []

    def handler() -> None:
        called.append(True)

    bus.subscribe("ev", handler)
    bus.unsubscribe("ev", handler)
    await bus.publish("ev")
    assert called == []


async def test_unsubscribe_cleans_up_empty_listener_list():
    bus = EventBus()

    def handler() -> None:
        pass

    bus.subscribe("ev", handler)
    bus.unsubscribe("ev", handler)
    assert "ev" not in bus._listeners


async def test_unsubscribe_unknown_event_does_not_raise():
    bus = EventBus()
    bus.unsubscribe("nonexistent", lambda: None)


async def test_unsubscribe_wrong_callback_does_not_raise():
    bus = EventBus()
    bus.subscribe("ev", lambda: None)
    bus.unsubscribe("ev", lambda: None)  # different object — ValueError swallowed


async def test_subscribe_empty_event_name_raises():
    bus = EventBus()
    with pytest.raises(ValueError, match="cannot be empty"):
        bus.subscribe("", lambda: None)


async def test_subscribe_non_callable_raises():
    bus = EventBus()
    with pytest.raises(TypeError, match="Callback must be callable"):
        bus.subscribe("ev", "not_a_function")  # type: ignore[arg-type]


async def test_publish_sync_exception_is_logged_and_other_handlers_run():
    bus = EventBus()
    log: list[str] = []

    def bad() -> None:
        raise RuntimeError("boom")

    bus.subscribe("ev", bad)
    bus.subscribe("ev", lambda: log.append("ok"))
    await bus.publish("ev")
    assert log == ["ok"]


async def test_publish_async_exception_is_logged(caplog: pytest.LogCaptureFixture) -> None:
    bus = EventBus()

    async def bad() -> None:
        raise ValueError("async boom")

    bus.subscribe("ev", bad)
    with caplog.at_level(logging.ERROR, logger="easycord"):
        await bus.publish("ev")
    assert "async boom" in caplog.text


async def test_publish_mixed_sync_and_async_subscribers():
    bus = EventBus()
    log: list[int] = []

    async def async_handler(n: int) -> None:
        log.append(n * 2)

    bus.subscribe("ev", lambda n: log.append(n))
    bus.subscribe("ev", async_handler)
    await bus.publish("ev", n=5)
    assert 5 in log
    assert 10 in log


async def test_subscribe_same_callback_twice_fires_twice():
    bus = EventBus()
    count: list[int] = [0]

    def handler() -> None:
        count[0] += 1

    bus.subscribe("ev", handler)
    bus.subscribe("ev", handler)
    await bus.publish("ev")
    assert count[0] == 2


async def test_publish_kwargs_forwarded_to_callback():
    bus = EventBus()
    received: dict[str, object] = {}

    def handler(a: int, b: str) -> None:
        received["a"] = a
        received["b"] = b

    bus.subscribe("ev", handler)
    await bus.publish("ev", a=1, b="hello")
    assert received == {"a": 1, "b": "hello"}


# ── REQ-04 observability regression guards (plan 01-04) ──────────────────────


async def test_publish_sync_failure_log_names_handler(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """BUG (REQ-04): EventBus subscriber-failure logs once omitted the failing
    handler's identity, making failures unattributable. Fixed: ``publish()``
    logs ``getattr(callback, "__qualname__", repr(callback))``. Guards the
    sync-callback except path.
    """
    bus = EventBus()

    def sync_boom_handler() -> None:
        raise RuntimeError("sync boom")

    bus.subscribe("ev", sync_boom_handler)
    with caplog.at_level(logging.ERROR, logger="easycord"):
        await bus.publish("ev")

    assert sync_boom_handler.__qualname__ in caplog.text
    assert "sync boom" in caplog.text


async def test_publish_async_failure_log_names_handler(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """BUG (REQ-04): the async publish path once collected bare coroutines,
    discarding the callback reference, so gather-result error logs could not
    name the failing handler. Fixed: each failure is logged with the handler's
    ``__qualname__``. Guards the async-callback except path.
    """
    bus = EventBus()

    async def async_boom_handler() -> None:
        raise ValueError("async boom")

    bus.subscribe("ev", async_boom_handler)
    with caplog.at_level(logging.ERROR, logger="easycord"):
        await bus.publish("ev")

    assert async_boom_handler.__qualname__ in caplog.text
    assert "async boom" in caplog.text


async def test_listeners_fire_in_registration_order() -> None:
    """Contract (REQ-04): listeners for an event are invoked in registration
    order — ``_listeners`` is a ``dict[str, list]`` appended by ``subscribe``
    and iterated in order by ``publish``. This guards the documented ordering
    so ordering-dependent subscribers stay debuggable.
    """
    bus = EventBus()
    order: list[str] = []

    def first() -> None:
        order.append("first")

    async def second() -> None:
        order.append("second")

    def third() -> None:
        order.append("third")

    async def fourth() -> None:
        order.append("fourth")

    for callback in (first, second, third, fourth):
        bus.subscribe("ev", callback)
    await bus.publish("ev")

    assert order == ["first", "second", "third", "fourth"]
