"""Tests for bot.run(reload=True) hot-reload dev mode."""
from __future__ import annotations

import asyncio
import types
from unittest.mock import AsyncMock, patch

from easycord import Bot, Plugin


def _make_bot() -> Bot:
    return Bot(auto_sync=False)


def _make_plugin(name: str = "TestPlugin") -> Plugin:
    plugin = Plugin.__new__(Plugin)
    plugin._bot = None
    plugin.name = name
    plugin.version = "1.0.0"
    plugin.author = ""
    plugin.description = ""
    plugin._instance_id = name
    Plugin.__init__(plugin)
    return plugin


# ── _hot_reload_plugin ────────────────────────────────────────────────────────


async def test_hot_reload_plugin_bad_module_keeps_old():
    """If inspect.getmodule returns None, the original plugin is untouched."""
    bot = _make_bot()
    plugin = _make_plugin()
    bot.add_plugin(plugin)

    with patch("inspect.getmodule", return_value=None):
        with patch.object(bot, "remove_plugin", new_callable=AsyncMock) as mock_remove:
            await bot._hot_reload_plugin(plugin)

    mock_remove.assert_not_called()
    assert plugin in bot._plugins


async def test_hot_reload_plugin_reload_error_keeps_old():
    """If importlib.reload raises, the original plugin is untouched."""
    bot = _make_bot()
    plugin = _make_plugin()
    bot.add_plugin(plugin)

    fake_module = types.ModuleType("fake_module")

    with patch("inspect.getmodule", return_value=fake_module):
        with patch("importlib.reload", side_effect=SyntaxError("bad syntax")):
            with patch.object(bot, "remove_plugin", new_callable=AsyncMock) as mock_remove:
                await bot._hot_reload_plugin(plugin)

    mock_remove.assert_not_called()
    assert plugin in bot._plugins


async def test_hot_reload_plugin_missing_class_keeps_old():
    """If the reloaded module doesn't export the class, the original is kept."""
    bot = _make_bot()
    plugin = _make_plugin("MyPlugin")
    bot.add_plugin(plugin)

    fake_module = types.ModuleType("fake_module")  # no MyPlugin attribute

    with patch("inspect.getmodule", return_value=fake_module):
        with patch("importlib.reload", return_value=fake_module):
            with patch.object(bot, "remove_plugin", new_callable=AsyncMock) as mock_remove:
                await bot._hot_reload_plugin(plugin)

    mock_remove.assert_not_called()
    assert plugin in bot._plugins


async def test_hot_reload_plugin_success_swaps_instance():
    """On success, remove_plugin and add_plugin are called with correct objects."""
    bot = _make_bot()
    old_plugin = _make_plugin("GoodPlugin")
    bot.add_plugin(old_plugin)

    new_plugin = _make_plugin("GoodPlugin")

    class GoodPlugin(Plugin):
        pass

    fake_module = types.ModuleType("fake_module")
    fake_module.GoodPlugin = GoodPlugin  # type: ignore[attr-defined]
    old_plugin.__class__ = GoodPlugin

    with patch("inspect.getmodule", return_value=fake_module):
        with patch("importlib.reload", return_value=fake_module):
            with patch.object(GoodPlugin, "__init__", return_value=None):
                with patch.object(GoodPlugin, "__new__", return_value=new_plugin):
                    with patch.object(bot, "remove_plugin", new_callable=AsyncMock) as mock_remove:
                        with patch.object(bot, "add_plugin") as mock_add:
                            await bot._hot_reload_plugin(old_plugin)

    mock_remove.assert_awaited_once_with(old_plugin)
    mock_add.assert_called_once()


# ── _hot_reload_loop ──────────────────────────────────────────────────────────


async def test_hot_reload_loop_seeds_without_reload():
    """First tick records mtimes but does not call _hot_reload_plugin."""
    bot = _make_bot()
    plugin = _make_plugin()
    bot.add_plugin(plugin)

    call_count = 0

    async def fake_reload(p):
        nonlocal call_count
        call_count += 1

    with patch("inspect.getfile", return_value="/fake/plugin.py"):
        with patch("os.path.getmtime", return_value=1000.0):
            with patch.object(bot, "_hot_reload_plugin", side_effect=fake_reload):
                with patch("asyncio.sleep", new_callable=AsyncMock):
                    # Run exactly one tick then cancel
                    task = asyncio.ensure_future(bot._hot_reload_loop())
                    await asyncio.sleep(0)
                    await asyncio.sleep(0)
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        # Expected: task was explicitly cancelled to stop the loop after one tick.
                        pass

    assert call_count == 0


async def test_hot_reload_loop_fires_on_mtime_change():
    """After the seed tick, a changed mtime triggers _hot_reload_plugin."""
    bot = _make_bot()
    plugin = _make_plugin()
    bot.add_plugin(plugin)

    fired: list[Plugin] = []

    async def fake_reload(p: Plugin) -> None:
        fired.append(p)

    # Tick 1: seed (1000.0), Tick 2: no change (1000.0), Tick 3: change → reload (1001.0)
    mtime_values = iter([1000.0, 1000.0, 1001.0])

    with patch("inspect.getfile", return_value="/fake/plugin.py"):
        with patch("os.path.getmtime", side_effect=mtime_values):
            with patch.object(bot, "_hot_reload_plugin", side_effect=fake_reload):
                sleep_count = 0

                async def fake_sleep(_):
                    nonlocal sleep_count
                    sleep_count += 1
                    if sleep_count >= 4:  # cancel after tick 3 body completes
                        raise asyncio.CancelledError

                with patch("asyncio.sleep", side_effect=fake_sleep):
                    try:
                        await bot._hot_reload_loop()
                    except asyncio.CancelledError:
                        # Expected: fake_sleep cancels the loop to end the test after tick processing.
                        _ = None
    assert len(fired) == 1
    assert fired[0] is plugin


# ── run(reload=True) integration ──────────────────────────────────────────────


def test_run_reload_flag_sets_attribute():
    """bot.run(reload=True) stores the flag before handing off to discord.py."""
    import discord

    bot = _make_bot()

    with patch.object(discord.Client, "run", return_value=None):
        bot.run("fake-token", reload=True)

    assert getattr(bot, "_dev_reload", False) is True


async def test_setup_hook_starts_watcher_when_dev_reload():
    """setup_hook schedules _hot_reload_loop into _background_tasks when reload=True."""
    bot = _make_bot()
    bot._dev_reload = True

    loop_started: list[bool] = []

    async def fake_loop():
        loop_started.append(True)
        await asyncio.sleep(9999)

    with patch.object(bot, "_hot_reload_loop", side_effect=fake_loop):
        with patch.object(bot.db, "ensure_schema", new_callable=AsyncMock):
            with patch.object(bot.db, "sync_guilds", new_callable=AsyncMock):
                with patch.object(bot.tree, "sync", new_callable=AsyncMock):
                    await bot.setup_hook()
                    # Give the event loop one tick to schedule the task
                    await asyncio.sleep(0)

    assert len(bot._background_tasks) >= 1


async def test_setup_hook_no_watcher_by_default():
    """setup_hook does NOT start the watcher when reload=False."""
    bot = _make_bot()

    with patch.object(bot, "_hot_reload_loop", new_callable=AsyncMock) as mock_loop:
        with patch.object(bot.db, "ensure_schema", new_callable=AsyncMock):
            with patch.object(bot.db, "sync_guilds", new_callable=AsyncMock):
                with patch.object(bot.tree, "sync", new_callable=AsyncMock):
                    await bot.setup_hook()

    mock_loop.assert_not_called()


# ── on_reload() lifecycle hook ────────────────────────────────────────────────


async def test_on_reload_called_on_new_instance():
    """on_reload() fires on the new instance — not the old one — after a swap."""
    bot = _make_bot()

    reload_log: list[Plugin] = []

    class TrackPlugin(Plugin):
        async def on_reload(self) -> None:
            reload_log.append(self)

    original = TrackPlugin()
    bot.add_plugin(original)

    fake_module = types.ModuleType("fake")
    fake_module.TrackPlugin = TrackPlugin  # type: ignore[attr-defined]

    with patch("inspect.getmodule", return_value=fake_module):
        with patch("importlib.reload", return_value=fake_module):
            await bot._hot_reload_plugin(original)

    assert len(reload_log) == 1
    assert reload_log[0] is not original          # fired on the NEW instance
    assert isinstance(reload_log[0], TrackPlugin)


async def test_on_reload_not_called_on_failure():
    """on_reload() must not fire if the reload itself failed."""
    bot = _make_bot()

    reload_log: list[Plugin] = []

    class TrackPlugin(Plugin):
        async def on_reload(self) -> None:
            reload_log.append(self)

    original = TrackPlugin()
    bot.add_plugin(original)

    with patch("inspect.getmodule", return_value=None):
        await bot._hot_reload_plugin(original)

    assert reload_log == []


# ── Logging levels ────────────────────────────────────────────────────────────


async def test_reload_logs_error_on_module_none():
    """logger.error fires (not warning) when module cannot be determined."""
    import easycord._bot_plugins as bp_module

    bot = _make_bot()
    plugin = _make_plugin()
    bot.add_plugin(plugin)

    with patch("inspect.getmodule", return_value=None):
        with patch.object(bp_module.logger, "error") as mock_error:
            await bot._hot_reload_plugin(plugin)

    mock_error.assert_called_once()
    assert "cannot determine module" in mock_error.call_args[0][0]


async def test_reload_logs_debug_on_trigger():
    """logger.debug fires at the start of every reload attempt."""
    import easycord._bot_plugins as bp_module

    bot = _make_bot()
    plugin = _make_plugin()
    bot.add_plugin(plugin)

    with patch("inspect.getmodule", return_value=None):
        with patch.object(bp_module.logger, "debug") as mock_debug:
            await bot._hot_reload_plugin(plugin)

    mock_debug.assert_called_once()
    assert plugin.name in str(mock_debug.call_args)


async def test_reload_logs_info_on_success():
    """logger.info fires after a successful hot-reload swap."""
    import easycord._bot_plugins as bp_module

    bot = _make_bot()

    class SimplePlugin(Plugin):
        pass

    plugin = SimplePlugin()
    bot.add_plugin(plugin)

    fake_module = types.ModuleType("fake")
    fake_module.SimplePlugin = SimplePlugin  # type: ignore[attr-defined]

    with patch("inspect.getmodule", return_value=fake_module):
        with patch("importlib.reload", return_value=fake_module):
            with patch.object(bp_module.logger, "info") as mock_info:
                await bot._hot_reload_plugin(plugin)

    mock_info.assert_called_once()
    assert "reloaded" in mock_info.call_args[0][0].lower()


# ── In-flight command safety ──────────────────────────────────────────────────


async def test_in_flight_coroutine_completes_after_reload():
    """A coroutine already running on the old instance completes normally after reload.

    The old plugin's `_bot` reference stays valid even after remove_plugin() — the
    running coroutine holds its own `self`, so there's nothing to break.
    """
    bot = _make_bot()
    completed: list[str] = []

    class SlowPlugin(Plugin):
        async def slow_work(self) -> None:
            await asyncio.sleep(0.02)
            completed.append("done")

    plugin = SlowPlugin()
    bot.add_plugin(plugin)

    # Start slow_work without awaiting — it will run concurrently
    in_flight = asyncio.create_task(plugin.slow_work())

    # Reload fires while slow_work is sleeping
    fake_module = types.ModuleType("fake")
    fake_module.SlowPlugin = SlowPlugin  # type: ignore[attr-defined]

    with patch("inspect.getmodule", return_value=fake_module):
        with patch("importlib.reload", return_value=fake_module):
            await bot._hot_reload_plugin(plugin)

    # Give slow_work time to finish; gather re-raises any exception from the task.
    await asyncio.gather(in_flight)

    assert completed == ["done"]


# ── reload/dispatch serialization lock ────────────────────────────────────────


def test_get_reload_lock_is_idempotent():
    """The bot-wide reload lock is created once and reused."""
    bot = _make_bot()
    first = bot._get_reload_lock()
    second = bot._get_reload_lock()
    assert first is second
    assert isinstance(first, asyncio.Lock)


async def test_reload_lock_held_across_swap():
    """The reload lock is held while remove/add/on_reload run, so a command
    dispatch gated on it cannot interleave with a half-removed registry."""
    bot = _make_bot()
    observed: dict[str, bool] = {}

    class LockProbe(Plugin):
        async def on_reload(self) -> None:
            lock = getattr(bot, "_reload_lock", None)
            observed["locked_during_on_reload"] = bool(lock is not None and lock.locked())

    original = LockProbe()
    bot.add_plugin(original)

    fake_module = types.ModuleType("fake")
    fake_module.LockProbe = LockProbe  # type: ignore[attr-defined]

    with patch("inspect.getmodule", return_value=fake_module):
        with patch("importlib.reload", return_value=fake_module):
            await bot._hot_reload_plugin(original)

    assert observed.get("locked_during_on_reload") is True
    # Lock is released once the swap finishes.
    assert not bot._reload_lock.locked()


async def test_hot_reload_loop_activates_dispatch_gate():
    """Starting the dev watcher flips the flag that makes command dispatch
    acquire the reload lock (lock-free in production where the loop never runs)."""
    import pytest

    bot = _make_bot()
    assert getattr(bot, "_hot_reload_active", False) is False

    # The flag is set before the first sleep; raise from sleep to exit the loop.
    with patch("asyncio.sleep", new_callable=AsyncMock, side_effect=asyncio.CancelledError):
        with pytest.raises(asyncio.CancelledError):
            await bot._hot_reload_loop()

    assert bot._hot_reload_active is True
    assert isinstance(bot._reload_lock, asyncio.Lock)
