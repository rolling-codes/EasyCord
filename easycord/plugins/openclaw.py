"""OpenClaw autonomous agent runner for Discord servers."""
from __future__ import annotations

import asyncio
import copy
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from easycord import Plugin, ToolSafety, slash
from easycord.orchestrator import Orchestrator, RunContext
from easycord.plugins._config_manager import PluginConfigManager
from easycord.tools import ToolRegistry

if TYPE_CHECKING:
    from easycord import Context


_HISTORY_KEY = "openclaw_history"
_STATUS_RUNNING = "running"
_STATUS_COMPLETED = "completed"
_STATUS_CANCELLED = "cancelled"
_STATUS_FAILED = "failed"
_STATUS_PAUSED = "paused"


@dataclass
class OpenClawTask:
    """Serializable task state for one autonomous OpenClaw run."""

    id: str
    guild_id: int
    channel_id: int | None
    requester_id: int
    prompt: str
    status: str
    steps: int
    max_steps: int
    started_at: str
    finished_at: str | None = None
    last_update: str = "Queued."
    result: str | None = None
    error: str | None = None
    cancelled: bool = False


class OpenClawPlugin(Plugin):
    """Autonomous AI agent integration for EasyCord.

    OpenClaw is intentionally different from ``/ask``: it receives a goal,
    executes through EasyCord's permission-gated orchestrator, and remains
    observable/cancellable while it runs.
    """

    def __init__(
        self,
        orchestrator=None,
        client=None,
        *,
        max_steps: int = 10,
        timeout_seconds: int = 300,
        require_admin: bool = True,
        allowed_tools: list[str] | None = None,
        max_safety: ToolSafety = ToolSafety.SAFE,
        history_limit: int = 20,
        dry_run: bool = False,
        approval_mode: bool = True,
        store_path: str = ".easycord/openclaw",
    ) -> None:
        super().__init__()
        self.orchestrator = orchestrator
        self.client = client
        self.max_steps = max(1, int(max_steps))
        self.timeout_seconds = max(1, int(timeout_seconds))
        self.require_admin = require_admin
        self.allowed_tools = list(allowed_tools or [])
        self.max_safety = max_safety
        self.history_limit = max(1, int(history_limit))
        self.dry_run = dry_run
        self.approval_mode = approval_mode
        self.config = PluginConfigManager(store_path)
        self._active: dict[int, OpenClawTask] = {}
        self._runners: dict[int, asyncio.Task] = {}

    @slash(name="openclaw", description="Show OpenClaw agent status and commands.", guild_only=True)
    async def openclaw(self, ctx: Context) -> None:
        """Show OpenClaw help and current task summary."""
        if not await self._authorize(ctx):
            return
        task = self._active.get(ctx.guild.id)
        if task:
            message = self._format_status(task)
        else:
            message = (
                "OpenClaw is ready. Use `/openclaw-task task:<goal>` to start an autonomous task.\n"
                "Use `/openclaw-status`, `/openclaw-stop`, and `/openclaw-history` to monitor it."
            )
        await ctx.respond(self._truncate(message), ephemeral=True)

    @slash(
        name="openclaw-task",
        description="Run an autonomous OpenClaw agent task.",
        guild_only=True,
    )
    async def openclaw_task(self, ctx: Context, task: str) -> None:
        """Start one autonomous task for the current guild."""
        if not await self._authorize(ctx):
            return
        if not self.orchestrator:
            detail = (
                "External OpenClaw clients are adapter-ready but not implemented in v1."
                if self.client is not None
                else "Provide an EasyCord Orchestrator to OpenClawPlugin."
            )
            await ctx.respond(f"OpenClaw is not configured. {detail}", ephemeral=True)
            return

        guild_id = ctx.guild.id
        existing = self._active.get(guild_id)
        if existing and existing.status == _STATUS_RUNNING:
            await ctx.respond(
                f"OpenClaw task `{existing.id}` is already running. Use `/openclaw-status` or `/openclaw-stop`.",
                ephemeral=True,
            )
            return

        record = OpenClawTask(
            id=uuid.uuid4().hex[:12],
            guild_id=guild_id,
            channel_id=getattr(getattr(ctx, "channel", None), "id", None),
            requester_id=ctx.user.id,
            prompt=task,
            status=_STATUS_RUNNING,
            steps=0,
            max_steps=self.max_steps,
            started_at=self._now(),
            last_update="Task queued.",
        )
        self._active[guild_id] = record
        runner = asyncio.create_task(self._run_task(ctx, record))
        self._runners[guild_id] = runner
        await ctx.respond(
            self._truncate(f"OpenClaw task `{record.id}` started. Use `/openclaw-status` to monitor progress."),
            ephemeral=True,
        )

    @slash(name="openclaw-status", description="Show the current OpenClaw task status.", guild_only=True)
    async def openclaw_status(self, ctx: Context) -> None:
        """Show current task state."""
        if not await self._authorize(ctx):
            return
        task = self._active.get(ctx.guild.id)
        if not task:
            await ctx.respond("No OpenClaw task is running for this server.", ephemeral=True)
            return
        await ctx.respond(self._truncate(self._format_status(task)), ephemeral=True)

    @slash(name="openclaw-stop", description="Cancel the running OpenClaw task.", guild_only=True)
    async def openclaw_stop(self, ctx: Context) -> None:
        """Cancel the running task for this guild."""
        if not await self._authorize(ctx):
            return
        guild_id = ctx.guild.id
        task = self._active.get(guild_id)
        if not task:
            await ctx.respond("No OpenClaw task is running for this server.", ephemeral=True)
            return

        task.cancelled = True
        task.status = _STATUS_CANCELLED
        task.finished_at = self._now()
        task.last_update = "Cancellation requested."
        runner = self._runners.get(guild_id)
        if runner and not runner.done():
            runner.cancel()
        await self._record_history(task)
        self._active.pop(guild_id, None)
        self._runners.pop(guild_id, None)
        await ctx.respond(f"OpenClaw task `{task.id}` cancelled.", ephemeral=True)

    @slash(name="openclaw-history", description="Show recent OpenClaw task history.", guild_only=True)
    async def openclaw_history(self, ctx: Context) -> None:
        """Show recent task history for this guild."""
        if not await self._authorize(ctx):
            return
        history = await self._load_history(ctx.guild.id)
        if not history:
            await ctx.respond("No OpenClaw task history for this server.", ephemeral=True)
            return
        lines = ["Recent OpenClaw tasks:"]
        for item in history[-5:]:
            prompt = item.get("prompt", "")[:80]
            lines.append(
                f"- `{item.get('id')}` {item.get('status')} ({item.get('steps', 0)}/{item.get('max_steps', self.max_steps)}): {prompt}"
            )
        await ctx.respond(self._truncate("\n".join(lines)), ephemeral=True)

    async def _run_task(self, ctx: Context, task: OpenClawTask) -> None:
        try:
            task.last_update = "Preparing tool sandbox."
            registry, blocked = await self._build_sandbox(ctx)
            if blocked:
                task.status = _STATUS_PAUSED
                task.last_update = "Approval required for restricted tool(s): " + ", ".join(blocked)
                task.finished_at = self._now()
                await self._record_history(task)
                return

            task.last_update = "Running agent."
            if self.dry_run:
                task.result = "Dry run complete. No tools were executed."
                task.status = _STATUS_COMPLETED
                task.steps = 0
                task.last_update = task.result
                task.finished_at = self._now()
                await self._record_history(task)
                return

            runner = Orchestrator(strategy=self.orchestrator.strategy, tools=registry)
            result = await asyncio.wait_for(
                runner.run(
                    RunContext(
                        messages=[{"role": "user", "content": task.prompt}],
                        ctx=ctx,
                        max_steps=task.max_steps,
                        timeout_ms=self.timeout_seconds * 1000,
                        system_prompt=self._system_prompt(),
                    )
                ),
                timeout=self.timeout_seconds,
            )
            task.steps = result.steps
            task.result = result.text
            task.status = _STATUS_COMPLETED
            task.last_update = result.text or "Task completed."
            task.finished_at = self._now()
            await self._record_history(task)
        except asyncio.CancelledError:
            task.cancelled = True
            task.status = _STATUS_CANCELLED
            task.finished_at = task.finished_at or self._now()
            task.last_update = "Task cancelled."
            await self._record_history(task)
            raise
        except Exception as exc:
            task.status = _STATUS_FAILED
            task.error = str(exc)
            task.finished_at = self._now()
            task.last_update = f"Task failed: {exc}"
            await self._record_history(task)
        finally:
            current = self._active.get(task.guild_id)
            if current and current.id == task.id and task.status != _STATUS_RUNNING:
                self._active.pop(task.guild_id, None)
                self._runners.pop(task.guild_id, None)

    async def _authorize(self, ctx: Context) -> bool:
        if not ctx.guild:
            await ctx.respond("OpenClaw can only run inside a server.", ephemeral=True)
            return False
        if self.require_admin:
            allowed = bool(getattr(ctx, "is_admin", False))
        else:
            perms = getattr(getattr(ctx, "user", None), "guild_permissions", None)
            allowed = bool(
                getattr(ctx, "is_admin", False)
                or getattr(perms, "manage_messages", False)
                or getattr(perms, "moderate_members", False)
            )
        if not allowed:
            await ctx.respond("OpenClaw requires admin or moderator permission.", ephemeral=True)
            return False
        return True

    async def _build_sandbox(self, ctx: Context) -> tuple[ToolRegistry, list[str]]:
        bot = getattr(self, "_bot", None)
        source = getattr(bot, "tool_registry", None)
        if source is None and self.orchestrator is not None:
            source = self.orchestrator.tools
        sandbox = ToolRegistry()
        blocked: list[str] = []
        allowed_names = set(self.allowed_tools)
        max_rank = self._safety_rank(self.max_safety)

        for name, tool in getattr(source, "_tools", {}).items():
            if allowed_names and name not in allowed_names:
                continue
            if tool.safety is ToolSafety.RESTRICTED:
                if name in allowed_names and self.approval_mode:
                    blocked.append(name)
                continue
            if self._safety_rank(tool.safety) > max_rank:
                continue
            if tool.safety is ToolSafety.CONTROLLED:
                allowed, _ = await source.can_execute(ctx, name)
                if not allowed:
                    continue
            sandbox.register(
                name=name,
                func=tool.func,
                description=tool.description,
                safety=tool.safety,
                parameters=copy.deepcopy(tool.parameters),
                require_guild=tool.require_guild,
                require_admin=tool.require_admin,
                allowed_roles=list(tool.allowed_roles),
                allowed_users=list(tool.allowed_users),
                timeout_ms=tool.timeout_ms,
                rate_limit=tool.rate_limit,
            )
        return sandbox, blocked

    async def _load_history(self, guild_id: int) -> list[dict[str, Any]]:
        cfg = await self.config.get(guild_id, _HISTORY_KEY, {"tasks": []})
        return list(cfg.get("tasks", []))

    async def _record_history(self, task: OpenClawTask) -> None:
        history = await self._load_history(task.guild_id)
        history = [item for item in history if item.get("id") != task.id]
        history.append(asdict(task))
        history = history[-self.history_limit:]
        await self.config.update(task.guild_id, _HISTORY_KEY, tasks=history)

    def _format_status(self, task: OpenClawTask) -> str:
        return (
            f"OpenClaw task `{task.id}`: {task.status}\n"
            f"Steps: {task.steps}/{task.max_steps}\n"
            f"Last update: {task.last_update}"
        )

    def _system_prompt(self) -> str:
        return (
            "You are OpenClaw, an autonomous Discord server agent. Plan briefly, "
            "execute only permitted tools, respect EasyCord ToolSafety boundaries, "
            "and return concise, auditable results. If a requested action requires "
            "approval or is unsafe, explain what approval is needed instead of acting."
        )

    @staticmethod
    def _safety_rank(safety: ToolSafety) -> int:
        ranks = {
            ToolSafety.SAFE: 0,
            ToolSafety.CONTROLLED: 1,
            ToolSafety.RESTRICTED: 2,
        }
        return ranks[safety]

    @staticmethod
    def _truncate(text: str, limit: int = 1900) -> str:
        if len(text) <= limit:
            return text
        return text[: limit - 3] + "..."

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()
