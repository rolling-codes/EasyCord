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

    @pytest.mark.asyncio
    async def test_forbidden_delete_does_not_escape_handler(self, tmp_path) -> None:
        plugin = _make_plugin(tmp_path, _orchestrator("delete", 0.99))
        await plugin._update_config(GUILD, enabled=True, action_level="auto_delete")
        msg = _make_message()
        msg.delete = AsyncMock(
            side_effect=discord.Forbidden(MagicMock(), "missing permissions")
        )

        try:
            await plugin._on_message(msg)
        except discord.Forbidden:
            pytest.fail("a Forbidden delete escaped _on_message")

    @pytest.mark.asyncio
    async def test_successful_auto_delete_removes_message(self, tmp_path) -> None:
        plugin = _make_plugin(tmp_path, _orchestrator("delete", 0.99))
        await plugin._update_config(GUILD, enabled=True, action_level="auto_delete")
        msg = _make_message()

        await plugin._on_message(msg)

        msg.delete.assert_awaited_once()


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
# notify_only — non-destructive review embed
# ---------------------------------------------------------------------------

class TestNotifyOnly:
    @pytest.mark.asyncio
    async def test_flagged_message_posts_review_embed(self, tmp_path) -> None:
        plugin = _make_plugin(tmp_path, _orchestrator("warn", 0.9))
        await plugin._update_config(
            GUILD, enabled=True, action_level="notify_only", mod_review_channel=555
        )
        msg = _make_message()
        review_channel = MagicMock(spec=discord.TextChannel)
        review_channel.send = AsyncMock()
        msg.guild.get_channel = MagicMock(return_value=review_channel)

        await plugin._on_message(msg)

        review_channel.send.assert_called_once()
        assert "embed" in review_channel.send.call_args.kwargs


# ---------------------------------------------------------------------------
# Dispatch guards — messages that must produce no action
# ---------------------------------------------------------------------------

class TestNoActionPaths:
    @pytest.mark.asyncio
    async def test_bot_authored_message_is_ignored(self, tmp_path) -> None:
        plugin = _make_plugin(tmp_path, _orchestrator("delete", 0.99))
        await plugin._update_config(GUILD, enabled=True, action_level="auto_delete")
        msg = _make_message()
        msg.author.bot = True

        await plugin._on_message(msg)

        msg.delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_disabled_guild_takes_no_action(self, tmp_path) -> None:
        orch = _orchestrator("delete", 0.99)
        plugin = _make_plugin(tmp_path, orch)
        await plugin._update_config(GUILD, enabled=False, action_level="auto_delete")
        msg = _make_message()

        await plugin._on_message(msg)

        orch.run.assert_not_called()
        msg.delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_below_threshold_takes_no_action(self, tmp_path) -> None:
        plugin = _make_plugin(tmp_path, _orchestrator("warn", 0.1))
        await plugin._update_config(
            GUILD, enabled=True, action_level="warn", confidence_threshold=0.85
        )
        msg = _make_message()

        await plugin._on_message(msg)

        assert msg.channel.send.call_count == 0
        assert msg.author.send.call_count == 0

    @pytest.mark.asyncio
    async def test_execute_action_without_guild_is_noop(self, tmp_path) -> None:
        plugin = _make_plugin(tmp_path, _orchestrator("delete", 0.99))
        msg = _make_message()
        msg.guild = None

        result = await plugin._execute_action(msg, "delete", "spam")

        assert result is False


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

    @pytest.mark.asyncio
    async def test_invalid_action_is_clamped_to_none(self, tmp_path) -> None:
        plugin = _make_plugin(tmp_path, _orchestrator("banana", 0.9))
        msg = _make_message()

        action, _, _ = await plugin._analyze_message(GUILD, msg)

        assert action is None


# ---------------------------------------------------------------------------
# Config mutators must be admin-gated — any member flipping action_level to
# auto_delete (or disabling moderation) is a privilege-escalation surface.
# ---------------------------------------------------------------------------

class TestConfigMutatorsRequireManageGuild:
    @pytest.mark.parametrize(
        "command",
        ["mod_enable", "mod_threshold", "mod_action_level", "mod_add_rule", "mod_remove_rule"],
    )
    def test_mutator_requires_manage_guild(self, command: str) -> None:
        func = getattr(AIModeratorPlugin, command)
        assert func._slash_permissions == ["manage_guild"], (
            f"/{command} mutates moderation config and must require manage_guild"
        )


# ---------------------------------------------------------------------------
# Coverage Gaps / Gated paths coverage
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_on_load_with_and_without_orchestrator(tmp_path) -> None:
    # Without orchestrator
    p1 = _make_plugin(tmp_path, None)
    await p1.on_load()
    
    # With orchestrator
    p2 = _make_plugin(tmp_path, MagicMock())
    await p2.on_load()


@pytest.mark.asyncio
async def test_analyze_message_no_orchestrator(tmp_path) -> None:
    p = _make_plugin(tmp_path, None)
    msg = _make_message()
    action, confidence, reason = await p._analyze_message(GUILD, msg)
    assert action is None
    assert confidence == 0.0
    assert reason == "Orchestrator not configured"


@pytest.mark.asyncio
async def test_analyze_message_exception(tmp_path) -> None:
    orch = MagicMock()
    orch.run = AsyncMock(side_effect=ValueError("fail"))
    p = _make_plugin(tmp_path, orch)
    msg = _make_message()
    action, confidence, reason = await p._analyze_message(GUILD, msg)
    assert action is None
    assert confidence == 0.0
    assert reason == "Analysis failed"


class TestAIModeratorSlashCommands:
    @pytest.mark.asyncio
    async def test_mod_enable(self, tmp_path) -> None:
        p = _make_plugin(tmp_path, None)
        ctx = MagicMock()
        ctx.guild.id = GUILD
        ctx.send = AsyncMock()
        
        await p.mod_enable(ctx, enabled=True)
        ctx.send.assert_called_once_with("✅ Moderation enabled")
        cfg = await p._get_config(GUILD)
        assert cfg["enabled"] is True

    @pytest.mark.asyncio
    async def test_mod_config(self, tmp_path) -> None:
        p = _make_plugin(tmp_path, None)
        ctx = MagicMock()
        ctx.guild.id = GUILD
        ctx.respond = AsyncMock()
        
        await p.mod_config(ctx)
        ctx.respond.assert_called_once()
        embed = ctx.respond.call_args.kwargs.get("embed")
        assert embed is not None
        assert embed.title == "Moderation Config"

    @pytest.mark.asyncio
    async def test_mod_threshold(self, tmp_path) -> None:
        p = _make_plugin(tmp_path, None)
        ctx = MagicMock()
        ctx.guild.id = GUILD
        ctx.send = AsyncMock()
        
        await p.mod_threshold(ctx, threshold=0.75)
        ctx.send.assert_called_once_with("✅ Threshold set to 75%")
        cfg = await p._get_config(GUILD)
        assert cfg["confidence_threshold"] == 0.75

    @pytest.mark.asyncio
    async def test_mod_action_level(self, tmp_path) -> None:
        p = _make_plugin(tmp_path, None)
        ctx = MagicMock()
        ctx.guild.id = GUILD
        ctx.send = AsyncMock()
        
        await p.mod_action_level(ctx, level="warn")
        ctx.send.assert_called_once_with("✅ Action level set to warn")
        cfg = await p._get_config(GUILD)
        assert cfg["action_level"] == "warn"

        ctx.send.reset_mock()
        await p.mod_action_level(ctx, level="invalid")
        ctx.send.assert_called_once_with("❌ Invalid level. Use: notify_only, warn, auto_delete")

    @pytest.mark.asyncio
    async def test_mod_add_remove_rule(self, tmp_path) -> None:
        p = _make_plugin(tmp_path, None)
        ctx = MagicMock()
        ctx.guild.id = GUILD
        ctx.send = AsyncMock()
        
        # Add valid rule
        await p.mod_add_rule(ctx, rule="spam")
        ctx.send.assert_called_once_with("✅ Added rule: spam")
        cfg = await p._get_config(GUILD)
        assert "spam" in cfg["rules"]

        # Add invalid rule
        ctx.send.reset_mock()
        await p.mod_add_rule(ctx, rule="invalid_rule")
        ctx.send.assert_called_once_with("❌ Invalid rule. Use: spam, abuse, nsfw")

        # Remove rule
        ctx.send.reset_mock()
        await p.mod_remove_rule(ctx, rule="spam")
        ctx.send.assert_called_once_with("✅ Removed rule: spam")
        cfg = await p._get_config(GUILD)
        assert "spam" not in cfg["rules"]

