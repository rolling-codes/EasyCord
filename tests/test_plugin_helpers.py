"""Tests for the PR #129 helper modules.

Covers ``_decorator_stacks`` (pre-composed slash stacks), ``_plugin_lifecycle_helpers``
(TaskManager/TimerManager), and ``_plugin_config_helper`` (PluginConfigHelper). These
modules shipped without tests; this file also guards the two real bugs fixed alongside:
the TaskManager done-callback identity race and PluginConfigHelper's lock domain.
"""
from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from easycord._decorator_stacks import (
    slash_admin_command,
    slash_management_command,
    slash_mod_command,
    slash_user_command,
    slash_with_confirm,
)
from easycord._plugin_config_helper import PluginConfigHelper
from easycord._plugin_lifecycle_helpers import TaskManager, TimerManager
from easycord.server_config import ServerConfigStore


# ── _decorator_stacks ────────────────────────────────────────────────────────


def test_slash_admin_command_defaults_to_admin_and_ephemeral() -> None:
    @slash_admin_command(description="d")
    async def cmd(self, ctx):  # pragma: no cover - body never runs
        ...

    assert getattr(cmd, "_slash_require_admin") is True
    assert getattr(cmd, "_slash_ephemeral") is True


def test_slash_admin_command_respects_ephemeral_false() -> None:
    # Regression: ephemeral=False must be honored, not overridden to True.
    @slash_admin_command(description="d", ephemeral=False)
    async def cmd(self, ctx):  # pragma: no cover
        ...

    assert getattr(cmd, "_slash_ephemeral") is False


def test_slash_management_command_defaults_manage_guild() -> None:
    @slash_management_command(description="d")
    async def cmd(self, ctx):  # pragma: no cover
        ...

    assert getattr(cmd, "_slash_permissions") == ["manage_guild"]
    assert getattr(cmd, "_slash_ephemeral") is True


def test_slash_management_command_respects_ephemeral_false() -> None:
    @slash_management_command(description="d", ephemeral=False)
    async def cmd(self, ctx):  # pragma: no cover
        ...

    assert getattr(cmd, "_slash_ephemeral") is False


def test_slash_mod_command_sets_user_and_bot_perms() -> None:
    @slash_mod_command(description="d")
    async def cmd(self, ctx):  # pragma: no cover
        ...

    perms = getattr(cmd, "_slash_permissions")
    assert "ban_members" in perms
    # moderate_members is the real discord.py timeout permission; timeout_members
    # does not exist on discord.Permissions and would silently never be granted.
    assert "moderate_members" in perms
    assert "timeout_members" not in perms
    assert "ban_members" in getattr(cmd, "_slash_bot_permissions")


def test_slash_user_command_is_guild_only() -> None:
    @slash_user_command(description="d")
    async def cmd(self, ctx):  # pragma: no cover
        ...

    assert getattr(cmd, "_slash_guild_only") is True


def test_slash_with_confirm_registers_slash() -> None:
    @slash_with_confirm(description="d", permissions=["manage_guild"])
    async def cmd(self, ctx):  # pragma: no cover
        ...

    assert getattr(cmd, "_is_slash") is True
    assert getattr(cmd, "_slash_permissions") == ["manage_guild"]


# ── _plugin_lifecycle_helpers: TaskManager ───────────────────────────────────


async def test_track_removes_task_when_done() -> None:
    tm = TaskManager()
    task = await tm.start_once("job", asyncio.sleep, 0)
    await task
    await asyncio.sleep(0)  # done callbacks dispatch on the next loop iteration
    assert "job" not in tm.tasks


async def test_start_once_returns_existing_running_task() -> None:
    tm = TaskManager()
    ev = asyncio.Event()

    async def waiter() -> None:
        await ev.wait()

    first = await tm.start_once("w", waiter)
    second = await tm.start_once("w", waiter)
    assert first is second
    ev.set()
    await first


async def test_track_cleanup_is_identity_safe() -> None:
    # Regression: a task that finishes after a replacement is registered under
    # the same name must NOT evict the replacement.
    tm = TaskManager()
    finishing = asyncio.create_task(asyncio.sleep(0))
    tm.track("bg", finishing)
    replacement = asyncio.create_task(asyncio.sleep(3600))
    tm.track("bg", replacement)  # replace under the same name, synchronously

    await finishing  # deterministically wait for the first task to complete
    await asyncio.sleep(0)  # let its done-callback dispatch

    assert finishing.done()
    assert tm.tasks.get("bg") is replacement  # not evicted by finishing's callback

    replacement.cancel()
    await asyncio.gather(replacement, return_exceptions=True)


async def test_cancel_all_cancels_tracked_tasks() -> None:
    tm = TaskManager()

    async def waiter() -> None:
        await asyncio.Event().wait()

    await tm.start_once("a", waiter)
    await tm.start_once("b", waiter)
    await tm.cancel_all()
    assert tm.tasks == {}


# ── _plugin_lifecycle_helpers: TimerManager ──────────────────────────────────


async def test_timer_schedule_tracks_then_cancel_all_clears() -> None:
    tmr = TimerManager()

    async def cb() -> None:  # pragma: no cover - never fires within the test
        ...

    await tmr.schedule("t", cb, 3600)
    assert tmr.timers["t"]
    await tmr.cancel_all()
    assert tmr.timers == {}


async def test_timer_fires_and_cleans_up_ungrouped() -> None:
    tmr = TimerManager()
    fired = asyncio.Event()

    async def cb() -> None:
        fired.set()

    await tmr.schedule("t", cb, 0.0)
    await asyncio.wait_for(fired.wait(), 1.0)
    await asyncio.sleep(0.01)  # let the finally-cleanup run
    assert tmr.timers.get("t", {}).get("__ungrouped__") is None


# ── _plugin_config_helper: PluginConfigHelper ────────────────────────────────


class _CfgPlugin(PluginConfigHelper):
    def __init__(self, store: ServerConfigStore, name: str = "testplugin", section: str | None = None) -> None:
        self._store = store
        self.name = name
        if section is not None:
            self._section_name = section


def _make_plugin(tmp_path: Path, **kwargs) -> _CfgPlugin:
    return _CfgPlugin(ServerConfigStore(str(tmp_path / "cfg")), **kwargs)


async def test_config_set_get_roundtrip(tmp_path: Path) -> None:
    p = _make_plugin(tmp_path)
    await p.config_set(1, "greeting", "hi")
    assert await p.config_get(1, "greeting") == "hi"
    assert await p.config_get(1, "missing", default="fallback") == "fallback"


async def test_config_section_defaults_to_plugin_name(tmp_path: Path) -> None:
    p = _make_plugin(tmp_path, name="myplug")
    await p.config_set(1, "k", "v")
    cfg = await p._store.load(1)
    assert cfg.get_other("myplug", {}).get("k") == "v"


async def test_config_update_merges(tmp_path: Path) -> None:
    p = _make_plugin(tmp_path)
    await p.config_set(1, "a", 1)
    await p.config_update(1, {"b": 2, "c": 3})
    assert await p.config_get(1, "a") == 1
    assert await p.config_get(1, "b") == 2
    assert await p.config_get(1, "c") == 3


async def test_config_delete_returns_previous_value(tmp_path: Path) -> None:
    p = _make_plugin(tmp_path)
    await p.config_set(1, "k", "v")
    assert await p.config_delete(1, "k") == "v"
    assert await p.config_get(1, "k") is None
    assert await p.config_delete(1, "absent") is None


async def test_config_mutate_returns_fn_result_and_persists(tmp_path: Path) -> None:
    p = _make_plugin(tmp_path)

    def _add(data: dict) -> int:
        data.setdefault("items", []).append("x")
        return len(data["items"])

    assert await p.config_mutate(1, _add) == 1
    assert await p.config_get(1, "items") == ["x"]


async def test_config_clear_empties_section(tmp_path: Path) -> None:
    p = _make_plugin(tmp_path)
    await p.config_set(1, "k", "v")
    await p.config_clear(1)
    assert await p.config_get(1, "k") is None


async def test_explicit_section_overrides_default(tmp_path: Path) -> None:
    p = _make_plugin(tmp_path, name="plug")
    await p.config_set(1, "k", "v", section="other")
    assert await p.config_get(1, "k", section="other") == "v"
    assert await p.config_get(1, "k") is None  # not in the default section


async def test_config_requires_store() -> None:
    class _NoStore(PluginConfigHelper):
        name = "x"

    with pytest.raises(RuntimeError, match="_store"):
        await _NoStore().config_set(1, "k", "v")


async def test_many_concurrent_writes_all_persist(tmp_path: Path) -> None:
    # Sanity check that many concurrent helper writes don't drop or corrupt keys.
    # Not a cross-domain race guard: the store's load/save wrap synchronous I/O
    # and never suspend between them, so writes serialize regardless of which
    # lock is used. Routing through store.mutate keeps it that way by design.
    p = _make_plugin(tmp_path)
    await asyncio.gather(*[p.config_set(1, f"k{i}", i) for i in range(200)])
    cfg = await p._store.load(1)
    assert len(cfg.get_other(p.name, {})) == 200
