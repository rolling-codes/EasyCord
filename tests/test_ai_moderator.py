"""Tests for AIModeratorPlugin — governance of the live moderation event path.

These pin the two verified defects in the `_on_message` → action pipeline:

1. The ``auto_delete`` branch performs an unguarded ``message.delete()`` — a
   failed delete (race / missing perms) must not escape the event handler.
2. The destructive actions bypass the per-user rate limiters held by the
   plugin (`warn_limiter` / `timeout_limiter`); a flagged action must be routed
   through the governed path so the limiter is actually consulted.
"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from easycord import ConversationMemory, RateLimit, ToolLimiter
from easycord.plugin import Plugin
from easycord.plugins._config_manager import PluginConfigManager
from easycord.plugins.ai_moderator import AIModeratorPlugin

GUILD = 100
AUTHOR = 1


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _orchestrator(action: str, confidence: float, reason: str = "spam") -> MagicMock:
    """Fake Orchestrator whose run() returns a canned JSON verdict."""
    payload = json.dumps({"action": action, "confidence": confidence, "reason": reason})
    orch = MagicMock()
    orch.run = AsyncMock(return_value=MagicMock(text=payload))
    return orch


def _orchestrator_text(text: str) -> MagicMock:
    """Fake Orchestrator returning arbitrary (possibly non-JSON) text."""
    orch = MagicMock()
    orch.run = AsyncMock(return_value=MagicMock(text=text))
    return orch


def _make_plugin(tmp_path, orchestrator: MagicMock) -> AIModeratorPlugin:
    """Construct an AIModeratorPlugin with a temp config store (no real I/O)."""
    p = AIModeratorPlugin.__new__(AIModeratorPlugin)
    Plugin.__init__(p)
    p.orchestrator = orchestrator
    p.config = PluginConfigManager(str(tmp_path / "moderation"))
    p.conversation_memory = ConversationMemory()
    p.warn_limiter = ToolLimiter()
    p.timeout_limiter = ToolLimiter()
    return p


def _make_message(*, guild_id: int = GUILD, author_id: int = AUTHOR) -> MagicMock:
    msg = MagicMock(spec=discord.Message)
    msg.content = "a flagged message"
    msg.author = MagicMock()
    msg.author.id = author_id
    msg.author.bot = False
    msg.author.mention = f"<@{author_id}>"
    msg.author.send = AsyncMock()
    guild = MagicMock()
    guild.id = guild_id
    msg.guild = guild
    channel = MagicMock(spec=discord.TextChannel)
    channel.send = AsyncMock()
    msg.channel = channel
    msg.delete = AsyncMock()
    return msg


# ---------------------------------------------------------------------------
# Defect 1 — unguarded destructive delete
# ---------------------------------------------------------------------------

class TestAutoDeleteIsGuarded:
    @pytest.mark.asyncio
    async def test_failed_delete_does_not_escape_handler(self, tmp_path) -> None:
        plugin = _make_plugin(tmp_path, _orchestrator("delete", 0.99))
        await plugin._update_config(GUILD, enabled=True, action_level="auto_delete")
        msg = _make_message()
        msg.delete = AsyncMock(
            side_effect=discord.HTTPException(MagicMock(), "deletion failed")
        )

        try:
            await plugin._on_message(msg)
        except discord.HTTPException:
            pytest.fail("a failed delete escaped _on_message (delete is unguarded)")


# ---------------------------------------------------------------------------
# Defect 2 — destructive actions bypass the rate limiter
# ---------------------------------------------------------------------------

class TestWarnIsRateLimited:
    @pytest.mark.asyncio
    async def test_warn_blocked_when_limiter_exhausted(self, tmp_path) -> None:
        plugin = _make_plugin(tmp_path, _orchestrator("warn", 0.9))
        await plugin._update_config(GUILD, enabled=True, action_level="warn")
        msg = _make_message()

        # Exhaust this user's warn budget before the flagged message arrives.
        limit = RateLimit(max_calls=10, window_minutes=60)
        for _ in range(10):
            await plugin.warn_limiter.check_limit(AUTHOR, "warn", limit)

        await plugin._on_message(msg)

        # No warn should be delivered through any channel once the budget is spent.
        assert msg.author.send.call_count == 0
        assert msg.channel.send.call_count == 0

    @pytest.mark.asyncio
    async def test_warn_delivered_when_under_limit(self, tmp_path) -> None:
        plugin = _make_plugin(tmp_path, _orchestrator("warn", 0.9))
        await plugin._update_config(GUILD, enabled=True, action_level="warn")
        msg = _make_message()

        await plugin._on_message(msg)

        total_warns = msg.author.send.call_count + msg.channel.send.call_count
        assert total_warns == 1


# ---------------------------------------------------------------------------
# Governed destructive path — timeout (rate-limited + guarded)
# ---------------------------------------------------------------------------

class TestTimeoutIsGoverned:
    @pytest.mark.asyncio
    async def test_timeout_applied_when_under_limit(self, tmp_path) -> None:
        plugin = _make_plugin(tmp_path, _orchestrator("timeout", 0.99))
        msg = _make_message()
        member = MagicMock()
        member.timeout = AsyncMock()
        msg.guild.get_member = MagicMock(return_value=member)

        result = await plugin._execute_action(msg, "timeout", "spam")

        assert result is True
        member.timeout.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_timeout_blocked_when_limiter_exhausted(self, tmp_path) -> None:
        plugin = _make_plugin(tmp_path, _orchestrator("timeout", 0.99))
        msg = _make_message()
        member = MagicMock()
        member.timeout = AsyncMock()
        msg.guild.get_member = MagicMock(return_value=member)

        limit = RateLimit(max_calls=5, window_minutes=60)
        for _ in range(5):
            await plugin.timeout_limiter.check_limit(AUTHOR, "timeout", limit)

        result = await plugin._execute_action(msg, "timeout", "spam")

        assert result is False
        member.timeout.assert_not_called()

    @pytest.mark.asyncio
    async def test_forbidden_timeout_does_not_escape(self, tmp_path) -> None:
        plugin = _make_plugin(tmp_path, _orchestrator("timeout", 0.99))
        msg = _make_message()
        member = MagicMock()
        member.timeout = AsyncMock(
            side_effect=discord.Forbidden(MagicMock(), "missing permissions")
        )
        msg.guild.get_member = MagicMock(return_value=member)

        result = await plugin._execute_action(msg, "timeout", "spam")

        assert result is False  # swallowed, not raised


# ---------------------------------------------------------------------------
# Analysis robustness — malformed model output
# ---------------------------------------------------------------------------

class TestAnalyzeRobustness:
    @pytest.mark.asyncio
    async def test_non_json_verdict_yields_no_action(self, tmp_path) -> None:
        plugin = _make_plugin(tmp_path, _orchestrator_text("I cannot help with that."))
        msg = _make_message()

        action, confidence, _ = await plugin._analyze_message(GUILD, msg)

        assert action is None
        assert confidence == 0.0
