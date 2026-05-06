"""Tests for OpenClawPlugin autonomous agent runner."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from easycord.orchestrator import FallbackStrategy, Orchestrator
from easycord.plugins.openclaw import OpenClawPlugin
from easycord.tools import ToolRegistry, ToolSafety


class StringProvider:
    def __init__(self, text: str = "done") -> None:
        self.text = text

    async def query(self, prompt: str) -> str:
        return self.text


class SlowProvider:
    def __init__(self) -> None:
        self.started = asyncio.Event()

    async def query(self, prompt: str) -> str:
        self.started.set()
        await asyncio.sleep(60)
        return "never"


def _orchestrator(provider=None, registry=None):
    return Orchestrator(
        strategy=FallbackStrategy([provider or StringProvider()]),
        tools=registry or ToolRegistry(),
    )


def _ctx(*, guild_id: int = 100, user_id: int = 1, is_admin: bool = True, mod: bool = False):
    ctx = MagicMock()
    ctx.guild = MagicMock()
    ctx.guild.id = guild_id
    ctx.guild_id = guild_id
    ctx.channel = MagicMock()
    ctx.channel.id = 55
    ctx.user = MagicMock()
    ctx.user.id = user_id
    perms = MagicMock()
    perms.manage_messages = mod
    perms.moderate_members = mod
    ctx.user.guild_permissions = perms
    ctx.is_admin = is_admin
    ctx.respond = AsyncMock()
    return ctx


def _plugin(tmp_path, *, orchestrator=None, **kwargs):
    return OpenClawPlugin(
        orchestrator=orchestrator or _orchestrator(),
        store_path=str(tmp_path / "openclaw"),
        **kwargs,
    )


def _attach_bot(plugin, registry):
    bot = MagicMock()
    bot.tool_registry = registry
    plugin._bot = bot
    return plugin


class TestOpenClawPlugin:
    def test_initializes_with_defaults(self, tmp_path) -> None:
        plugin = _plugin(tmp_path)
        assert plugin.max_steps == 10
        assert plugin.require_admin is True
        assert plugin.max_safety is ToolSafety.SAFE
        assert plugin.allowed_tools == []

    @pytest.mark.asyncio
    async def test_task_rejects_missing_backend(self, tmp_path) -> None:
        plugin = OpenClawPlugin(store_path=str(tmp_path / "openclaw"))
        ctx = _ctx()
        await plugin.openclaw_task(ctx, "review messages")
        assert "not configured" in ctx.respond.call_args[0][0]
        assert ctx.respond.call_args[1]["ephemeral"] is True

    @pytest.mark.asyncio
    async def test_non_admin_denied_when_admin_required(self, tmp_path) -> None:
        plugin = _plugin(tmp_path, require_admin=True)
        ctx = _ctx(is_admin=False, mod=True)
        await plugin.openclaw_task(ctx, "review messages")
        assert "requires admin" in ctx.respond.call_args[0][0].lower()
        assert ctx.respond.call_args[1]["ephemeral"] is True

    @pytest.mark.asyncio
    async def test_moderator_allowed_when_admin_not_required(self, tmp_path) -> None:
        plugin = _plugin(tmp_path, require_admin=False)
        ctx = _ctx(is_admin=False, mod=True)
        await plugin.openclaw_task(ctx, "review messages")
        await asyncio.sleep(0)
        assert "started" in ctx.respond.call_args[0][0]

    @pytest.mark.asyncio
    async def test_admin_can_start_and_history_records_completion(self, tmp_path) -> None:
        plugin = _plugin(tmp_path, orchestrator=_orchestrator(StringProvider("complete")))
        ctx = _ctx(is_admin=True)
        await plugin.openclaw_task(ctx, "review messages")
        await asyncio.sleep(0.05)
        history = await plugin._load_history(ctx.guild.id)
        assert ctx.respond.call_args[1]["ephemeral"] is True
        assert history[-1]["status"] == "completed"
        assert history[-1]["result"] == "complete"

    @pytest.mark.asyncio
    async def test_second_task_rejected_while_active(self, tmp_path) -> None:
        provider = SlowProvider()
        plugin = _plugin(tmp_path, orchestrator=_orchestrator(provider))
        ctx = _ctx()
        await plugin.openclaw_task(ctx, "first")
        await provider.started.wait()

        ctx2 = _ctx()
        await plugin.openclaw_task(ctx2, "second")
        assert "already running" in ctx2.respond.call_args[0][0]

        await plugin.openclaw_stop(_ctx())

    @pytest.mark.asyncio
    async def test_status_reports_running_task(self, tmp_path) -> None:
        provider = SlowProvider()
        plugin = _plugin(tmp_path, orchestrator=_orchestrator(provider))
        ctx = _ctx()
        await plugin.openclaw_task(ctx, "first")
        await provider.started.wait()

        status_ctx = _ctx()
        await plugin.openclaw_status(status_ctx)
        assert "running" in status_ctx.respond.call_args[0][0]
        assert status_ctx.respond.call_args[1]["ephemeral"] is True

        await plugin.openclaw_stop(_ctx())

    @pytest.mark.asyncio
    async def test_stop_cancels_task_and_writes_history(self, tmp_path) -> None:
        provider = SlowProvider()
        plugin = _plugin(tmp_path, orchestrator=_orchestrator(provider))
        ctx = _ctx()
        await plugin.openclaw_task(ctx, "first")
        await provider.started.wait()

        stop_ctx = _ctx()
        await plugin.openclaw_stop(stop_ctx)
        history = await plugin._load_history(ctx.guild.id)

        assert "cancelled" in stop_ctx.respond.call_args[0][0]
        assert history[-1]["status"] == "cancelled"
        assert ctx.guild.id not in plugin._active

    @pytest.mark.asyncio
    async def test_history_command_lists_recent_tasks(self, tmp_path) -> None:
        plugin = _plugin(tmp_path, orchestrator=_orchestrator(StringProvider("complete")))
        ctx = _ctx()
        await plugin.openclaw_task(ctx, "review messages")
        await asyncio.sleep(0.05)

        history_ctx = _ctx()
        await plugin.openclaw_history(history_ctx)
        assert "Recent OpenClaw tasks" in history_ctx.respond.call_args[0][0]
        assert "review messages" in history_ctx.respond.call_args[0][0]

    @pytest.mark.asyncio
    async def test_default_tool_filter_excludes_controlled_and_restricted(self, tmp_path) -> None:
        registry = ToolRegistry()
        registry.register("safe", lambda ctx: "safe", "Safe", ToolSafety.SAFE, require_guild=False)
        registry.register("controlled", lambda ctx: "controlled", "Controlled", ToolSafety.CONTROLLED, require_guild=False)
        registry.register("restricted", lambda ctx: "restricted", "Restricted", ToolSafety.RESTRICTED, require_guild=False)
        plugin = _attach_bot(_plugin(tmp_path), registry)

        sandbox, blocked = await plugin._build_sandbox(_ctx())

        assert set(sandbox._tools) == {"safe"}
        assert blocked == []

    @pytest.mark.asyncio
    async def test_allowed_tools_limits_exposure(self, tmp_path) -> None:
        registry = ToolRegistry()
        registry.register("safe_a", lambda ctx: "a", "A", ToolSafety.SAFE, require_guild=False)
        registry.register("safe_b", lambda ctx: "b", "B", ToolSafety.SAFE, require_guild=False)
        plugin = _attach_bot(_plugin(tmp_path, allowed_tools=["safe_b"]), registry)

        sandbox, _ = await plugin._build_sandbox(_ctx())

        assert set(sandbox._tools) == {"safe_b"}

    @pytest.mark.asyncio
    async def test_restricted_tools_pause_instead_of_execute(self, tmp_path) -> None:
        registry = ToolRegistry()
        called = False

        def restricted(ctx):
            nonlocal called
            called = True
            return "bad"

        registry.register("danger", restricted, "Danger", ToolSafety.RESTRICTED, require_guild=False)
        plugin = _attach_bot(
            _plugin(tmp_path, allowed_tools=["danger"], max_safety=ToolSafety.RESTRICTED),
            registry,
        )
        ctx = _ctx()
        await plugin.openclaw_task(ctx, "do danger")
        await asyncio.sleep(0.05)
        history = await plugin._load_history(ctx.guild.id)

        assert called is False
        assert history[-1]["status"] == "paused"
        assert "Approval required" in history[-1]["last_update"]
