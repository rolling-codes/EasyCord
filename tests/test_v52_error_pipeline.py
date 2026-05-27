"""Tests for the unified EasyCord v5.2 error pipeline routing."""
from __future__ import annotations

import asyncio

import pytest

from easycord import Bot, Plugin, autocomplete, component, modal, slash, task
from easycord.testing import FakeInteraction


async def test_component_error_routes_to_plugin_on_error() -> None:
    error_seen = None

    class CrashPlugin(Plugin):
        @component("crash_btn")
        async def crash_btn(self, ctx):
            raise RuntimeError("component boom")

        async def on_error(self, ctx, exc):
            nonlocal error_seen
            error_seen = exc

    bot = Bot(auto_sync=False, db_backend="memory")
    try:
        bot.add_plugin(CrashPlugin())
        interaction = FakeInteraction(client=bot)
        interaction.data = {"custom_id": "crashplugin:crash_btn"}
        await bot._dispatch_component(interaction)

        assert isinstance(error_seen, RuntimeError)
        assert str(error_seen) == "component boom"
    finally:
        await bot.close()


async def test_component_error_routes_to_global_on_error_if_no_plugin_handler() -> None:
    error_seen = None

    class SilentPlugin(Plugin):
        @component("silent_crash")
        async def silent_crash(self, ctx):
            raise ValueError("global boom")

    bot = Bot(auto_sync=False, db_backend="memory")
    try:
        @bot.on_error
        async def global_error(ctx, exc):
            nonlocal error_seen
            error_seen = exc

        bot.add_plugin(SilentPlugin())
        interaction = FakeInteraction(client=bot)
        interaction.data = {"custom_id": "silentplugin:silent_crash"}
        await bot._dispatch_component(interaction)

        assert isinstance(error_seen, ValueError)
        assert str(error_seen) == "global boom"
    finally:
        await bot.close()


async def test_modal_error_routes_to_error_pipeline() -> None:
    error_seen = None

    class ModalPlugin(Plugin):
        @modal("crash_modal")
        async def crash_modal(self, ctx, data):
            raise TypeError("modal boom")

        async def on_error(self, ctx, exc):
            nonlocal error_seen
            error_seen = exc

    bot = Bot(auto_sync=False, db_backend="memory")
    try:
        bot.add_plugin(ModalPlugin())
        interaction = FakeInteraction(client=bot)
        interaction.data = {"custom_id": "modalplugin:crash_modal", "components": []}
        await bot._dispatch_modal(interaction)

        assert isinstance(error_seen, TypeError)
        assert str(error_seen) == "modal boom"
    finally:
        await bot.close()


async def test_autocomplete_error_returns_empty_and_routes_to_error_pipeline() -> None:
    error_seen = None

    class AutoPlugin(Plugin):
        @autocomplete("opt", command="cmd")
        async def auto_opt(self, ctx, current, options):
            raise ZeroDivisionError("auto boom")

        @slash(name="cmd", description="dummy cmd")
        async def cmd(self, ctx, opt: str):
            pass

        async def on_error(self, ctx, exc):
            nonlocal error_seen
            error_seen = exc

    bot = Bot(auto_sync=False, db_backend="memory")
    try:
        bot.add_plugin(AutoPlugin())
        
        # In order to safely test the error wrapper returned by _make_autocomplete
        # we can fetch the command object and pull its autocomplete callback, 
        # or just extract the wrapper that we know discord.py receives.
        cmd = bot.tree.get_command("cmd")
        interaction = FakeInteraction(client=bot)
        interaction.command = cmd
        interaction.data = {"options": [{"name": "opt", "value": "val", "focused": True}]}
        
        # discord.py 2.0+ stores autocomplete in _params for the Command object
        # We find the opt parameter and call its autocomplete directly.
        if cmd is not None and getattr(cmd, "_params", None):
            for param_name, param in cmd._params.items():
                if param_name == "opt" and getattr(param, "autocomplete", None):
                    choices = await param.autocomplete(interaction, "val")
                    assert choices == []
        
        assert isinstance(error_seen, ZeroDivisionError)
        assert str(error_seen) == "auto boom"
    finally:
        await bot.close()


async def test_task_error_records_failure_and_routes_to_error_pipeline() -> None:
    error_seen = None

    class TaskPlugin(Plugin):
        @task(seconds=0.001)
        async def crash_task(self):
            raise KeyError("task boom")

        async def on_error(self, ctx, exc):
            nonlocal error_seen
            error_seen = exc

    bot = Bot(auto_sync=False, db_backend="memory")
    try:
        plugin = TaskPlugin()
        bot.add_plugin(plugin)
        bot._start_plugin_tasks(plugin)
        
        await asyncio.sleep(0.02)
        
        status = bot.task_statuses()[f"{plugin._instance_id}.crash_task"]
        assert status["state"] == "failed"
        assert "task boom" in status["last_error"]
        
        assert isinstance(error_seen, KeyError)
        assert error_seen.args == ("task boom",)
    finally:
        await bot.close()


async def test_task_cancellation_during_unload_is_not_a_crash() -> None:
    error_seen = False

    class TaskPlugin(Plugin):
        @task(seconds=1.0)
        async def sleep_task(self):
            await asyncio.sleep(5.0)

        async def on_error(self, ctx, exc):
            nonlocal error_seen
            error_seen = True

    bot = Bot(auto_sync=False, db_backend="memory")
    try:
        plugin = TaskPlugin()
        bot.add_plugin(plugin)
        bot._start_plugin_tasks(plugin)
        
        await asyncio.sleep(0.01)
        
        await bot.remove_plugin(plugin)
        
        status = bot.task_statuses()[f"{plugin._instance_id}.sleep_task"]
        assert status["state"] == "stopped"  # Not failed
        assert error_seen is False
    finally:
        await bot.close()
