"""Tests covering zero-test core modules: embed_cards, formatters,
context_builder, group, managers, and audit."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from easycord import (
    AuditLog,
    ContextBuilder,
    EmbedCard,
    ErrorEmbed,
    FrameworkManager,
    InfoEmbed,
    SecurityManager,
    SlashGroup,
    SuccessEmbed,
    WarningEmbed,
)
from easycord.composer import Composer
from easycord.bot import Bot
from easycord.formatters import (
    format_doctor_report,
    format_interaction_inventory,
    format_sync_plan,
    format_tool_audit,
)
from easycord.server_config import ServerConfig


# ---------------------------------------------------------------------------
# TestEmbedCard
# ---------------------------------------------------------------------------


class TestEmbedCard:
    def test_empty_card_to_kwargs_has_no_view(self):
        card = EmbedCard()
        kwargs = card.to_kwargs()
        assert "embed" in kwargs
        assert "view" not in kwargs

    def test_button_primary_style(self):
        card = EmbedCard().button("Click me", custom_id="btn1", style="primary")
        kwargs = card.to_kwargs()
        assert "view" in kwargs

    def test_button_link_requires_url(self):
        with pytest.raises(ValueError, match="URL"):
            EmbedCard().button("Visit", style="link")

    def test_non_link_button_with_url_raises(self):
        with pytest.raises(ValueError):
            EmbedCard().button("Click", style="primary", url="https://example.com")

    def test_select_no_options_raises(self):
        with pytest.raises(ValueError, match="option"):
            EmbedCard().select("my_select", options=[])

    def test_select_with_options_builds_view(self):
        card = EmbedCard().select(
            "my_select",
            options=[("Label A", "value_a"), ("Label B", "value_b")],
        )
        kwargs = card.to_kwargs()
        assert "view" in kwargs

    def test_chained_title_description_field(self):
        card = (
            EmbedCard()
            .title("Hello")
            .description("World")
            .field("Field Name", "Field Value")
        )
        embed, _ = card.build()
        assert embed.title == "Hello"
        assert embed.description == "World"
        assert len(embed.fields) == 1
        assert embed.fields[0].name == "Field Name"

    def test_build_returns_embed_and_none_view(self):
        card = EmbedCard()
        embed, view = card.build()
        assert isinstance(embed, discord.Embed)
        assert view is None

    def test_info_embed_color(self):
        card = InfoEmbed()
        embed, _ = card.build()
        assert embed.color == discord.Color.blurple()

    def test_success_embed_color(self):
        card = SuccessEmbed()
        embed, _ = card.build()
        assert embed.color == discord.Color.green()

    def test_error_embed_color(self):
        card = ErrorEmbed()
        embed, _ = card.build()
        assert embed.color == discord.Color.red()

    def test_link_button_url(self):
        card = EmbedCard().button("Visit", style="link", url="https://example.com")
        kwargs = card.to_kwargs()
        assert "view" in kwargs


# ---------------------------------------------------------------------------
# TestFormatters
# ---------------------------------------------------------------------------


class TestFormatters:
    def test_format_interaction_inventory_empty(self):
        result = format_interaction_inventory({})
        assert "EasyCord" in result

    def test_format_interaction_inventory_with_slash(self):
        inventory = {
            "slash": [{"name": "ping", "source": "Bot", "enabled": True}]
        }
        result = format_interaction_inventory(inventory)
        assert "ping" in result

    def test_format_sync_plan_all_missing_keys(self):
        result = format_sync_plan({})
        assert "EasyCord" in result

    def test_format_sync_plan_with_entries(self):
        plan = {"added": ["ping", "pong"], "changed": [], "removed": []}
        result = format_sync_plan(plan)
        assert "ping" in result
        assert "pong" in result

    def test_format_doctor_report_empty(self):
        result = format_doctor_report({})
        assert isinstance(result, str)

    def test_format_doctor_report_with_errors(self):
        report = {
            "checks": [
                {"name": "token_check", "ok": False, "detail": "missing token"}
            ]
        }
        result = format_doctor_report(report)
        assert "error" in result.lower()

    def test_format_tool_audit_empty_tools(self):
        result = format_tool_audit({"tools": [], "counts": {}})
        assert isinstance(result, str)

    def test_format_tool_audit_with_tool(self):
        report = {
            "tools": [
                {
                    "name": "ban_user",
                    "safety": "controlled",
                    "enabled": True,
                    "warnings": [],
                }
            ],
            "counts": {"total": 1, "enabled": 1, "disabled": 0},
        }
        result = format_tool_audit(report)
        assert "ban_user" in result


# ---------------------------------------------------------------------------
# TestContextBuilder
# ---------------------------------------------------------------------------


class TestContextBuilder:
    def test_format_state_dm(self):
        ctx = MagicMock()
        ctx.guild = None
        result = ContextBuilder._format_state(ctx)
        assert "Direct message" in result

    def test_format_state_guild(self):
        ctx = MagicMock()
        guild = MagicMock()
        guild.name = "MyServer"
        guild.id = 999
        guild.members = []
        guild.roles = []
        guild.channels = []
        ctx.guild = guild
        ctx.member = None
        ctx.is_admin = False
        result = ContextBuilder._format_state(ctx)
        assert "MyServer" in result

    def test_build_bot_state_summary_dm(self):
        ctx = MagicMock()
        ctx.guild = None
        result = ContextBuilder.build_bot_state_summary(ctx)
        assert result.get("type") == "dm"

    def test_build_bot_state_summary_guild(self):
        ctx = MagicMock()
        guild = MagicMock()
        guild.name = "TestGuild"
        guild.id = 123
        guild.members = []
        guild.roles = []
        guild.channels = []
        ctx.guild = guild
        ctx.user = MagicMock()
        ctx.user.name = "Alice"
        ctx.user.id = 1
        ctx.member = None
        ctx.is_admin = False
        result = ContextBuilder.build_bot_state_summary(ctx)
        assert "guild" in result
        assert result["guild"]["name"] == "TestGuild"

    def test_build_system_prompt_returns_nonempty_string(self):
        bot = MagicMock()
        bot.tree.get_commands.return_value = []

        registry = MagicMock()
        registry.list_available.return_value = []

        ctx = MagicMock()
        ctx.guild = MagicMock()
        ctx.guild.name = "PromptServer"
        ctx.guild.id = 42
        ctx.guild.members = []
        ctx.guild.roles = []
        ctx.guild.channels = []
        ctx.member = None
        ctx.is_admin = False

        result = ContextBuilder.build_system_prompt(bot, ctx, registry)
        assert isinstance(result, str)
        assert len(result) > 0


# ---------------------------------------------------------------------------
# TestSlashGroup
# ---------------------------------------------------------------------------


class TestSlashGroup:
    def test_default_attributes(self):
        class MyGroup(SlashGroup):
            pass

        assert MyGroup._group_name == "mygroup"

    def test_custom_name_and_description(self):
        class FooGroup(SlashGroup, name="foo", description="bar"):
            pass

        assert FooGroup._group_name == "foo"
        assert FooGroup._group_description == "bar"

    def test_guild_only_attribute(self):
        class GuildGroup(SlashGroup, guild_only=True):
            pass

        assert GuildGroup._group_guild_only is True


# ---------------------------------------------------------------------------
# TestSecurityManager
# ---------------------------------------------------------------------------


class TestSecurityManager:
    def test_build_returns_three_middleware(self):
        sm = SecurityManager()
        chain = sm.build()
        assert len(chain) == 3

    def test_apply_to_composer(self):
        sm = SecurityManager()
        composer = Composer()
        result = sm.apply_to_composer(composer)
        assert result is composer

    def test_custom_rate_limit_propagated(self):
        sm = SecurityManager(rate_limit=2, rate_window=5.0)
        chain = sm.build()
        # Still produces 3 middleware even with custom rate params
        assert len(chain) == 3


# ---------------------------------------------------------------------------
# TestFrameworkManager
# ---------------------------------------------------------------------------


class TestFrameworkManager:
    def test_bootstrap_returns_composer(self):
        composer = FrameworkManager.bootstrap(secure=False)
        assert isinstance(composer, Composer)

    def test_build_bot_returns_bot(self):
        bot = FrameworkManager.build_bot(secure=False)
        assert isinstance(bot, Bot)


# ---------------------------------------------------------------------------
# TestAuditLog
# ---------------------------------------------------------------------------


class TestAuditLog:
    @pytest.mark.asyncio
    async def test_log_no_op_without_guild(self):
        store = AsyncMock()
        audit = AuditLog(store, channel_key="audit_log")
        ctx = MagicMock()
        ctx.guild = None
        await audit.log(ctx, action="ban")
        store.load.assert_not_called()

    @pytest.mark.asyncio
    async def test_log_no_op_without_channel_configured(self):
        store = MagicMock()
        cfg = ServerConfig(guild_id=100)  # no channel set
        store.load = AsyncMock(return_value=cfg)

        audit = AuditLog(store, channel_key="audit_log")
        ctx = MagicMock()
        ctx.guild = MagicMock()
        ctx.guild.id = 100

        await audit.log(ctx, action="kick")

        store.load.assert_called_once_with(100)
        # channel.send should never have been reached

    @pytest.mark.asyncio
    async def test_log_posts_embed_when_configured(self):
        store = MagicMock()
        cfg = ServerConfig(guild_id=200)
        cfg.set_channel("audit_log", 555)
        store.load = AsyncMock(return_value=cfg)

        channel = MagicMock()
        channel.send = AsyncMock()

        client = MagicMock()
        client.get_channel.return_value = channel

        ctx = MagicMock()
        ctx.guild = MagicMock()
        ctx.guild.id = 200
        ctx.user = MagicMock()
        ctx.user.__str__ = lambda self: "TestUser#0001"
        ctx.interaction = MagicMock()
        ctx.interaction.client = client

        audit = AuditLog(store, channel_key="audit_log")
        await audit.log(ctx, action="mute", reason="test reason")

        channel.send.assert_called_once()
        call_kwargs = channel.send.call_args.kwargs
        assert "embed" in call_kwargs
        embed = call_kwargs["embed"]
        assert isinstance(embed, discord.Embed)
        assert "mute" in embed.title.lower()
