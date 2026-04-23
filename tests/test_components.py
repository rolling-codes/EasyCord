"""Tests for @bot.component persistent component routing."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import discord

from easycord import Bot
from discord import app_commands


@pytest.fixture
def bot():
    mock_tree = MagicMock()
    mock_tree.add_command = MagicMock()
    mock_tree.remove_command = MagicMock()
    mock_tree.sync = AsyncMock()

    with patch("discord.Client.__init__", return_value=None), \
         patch("easycord.bot.app_commands.CommandTree", return_value=mock_tree):
        b = Bot(intents=MagicMock(), auto_sync=False, db_backend="memory")
        b.is_ready = MagicMock(return_value=False)
        return b


def _make_component_interaction(custom_id: str):
    interaction = MagicMock()
    interaction.type = discord.InteractionType.component
    interaction.data = {"custom_id": custom_id}
    interaction.response.send_message = AsyncMock()
    interaction.followup.send = AsyncMock()
    interaction.guild = MagicMock()
    interaction.user = MagicMock()
    interaction.command = None
    return interaction


# ── decorator API ─────────────────────────────────────────────────────────────

def test_component_registers_with_explicit_id(bot):
    @bot.component("my_button")
    async def handler(ctx):
        pass
    assert "my_button" in bot.registry.components


def test_component_defaults_id_to_function_name(bot):
    @bot.component
    async def confirm_action(ctx):
        pass
    assert "confirm_action" in bot.registry.components


def test_component_returns_original_function(bot):
    async def handler(ctx):
        pass
    result = bot.component("btn")(handler)
    assert result is handler


# ── exact match routing ───────────────────────────────────────────────────────

async def test_component_exact_match_invokes_handler(bot):
    called = []

    @bot.component("yes_btn")
    async def yes_handler(ctx):
        called.append(True)

    interaction = _make_component_interaction("yes_btn")
    with patch.object(discord.Client, "dispatch"):
        await bot.on_interaction(interaction)

    assert called == [True]


async def test_component_unmatched_is_silently_ignored(bot):
    called = []

    @bot.component("yes_btn")
    async def yes_handler(ctx):
        called.append(True)

    interaction = _make_component_interaction("no_btn")
    with patch.object(discord.Client, "dispatch"):
        await bot.on_interaction(interaction)

    assert called == []


async def test_component_non_component_interaction_is_ignored(bot):
    called = []

    @bot.component("yes_btn")
    async def yes_handler(ctx):
        called.append(True)

    interaction = _make_component_interaction("yes_btn")
    interaction.type = discord.InteractionType.application_command
    with patch.object(discord.Client, "dispatch"):
        await bot.on_interaction(interaction)

    assert called == []


# ── prefix routing ────────────────────────────────────────────────────────────

async def test_component_prefix_match_invokes_handler_with_suffix(bot):
    received = []

    @bot.component("ban_")
    async def ban_handler(ctx, suffix: str):
        received.append(suffix)

    interaction = _make_component_interaction("ban_12345")
    with patch.object(discord.Client, "dispatch"):
        await bot.on_interaction(interaction)

    assert received == ["12345"]


async def test_component_exact_wins_over_prefix(bot):
    order = []

    @bot.component("ban_exact")
    async def exact_handler(ctx):
        order.append("exact")

    @bot.component("ban_")
    async def prefix_handler(ctx, suffix: str):
        order.append(f"prefix:{suffix}")

    interaction = _make_component_interaction("ban_exact")
    with patch.object(discord.Client, "dispatch"):
        await bot.on_interaction(interaction)

    assert order == ["exact"]


async def test_component_prefix_no_match_is_ignored(bot):
    called = []

    @bot.component("ban_")
    async def handler(ctx, suffix: str):
        called.append(suffix)

    interaction = _make_component_interaction("kick_99")
    with patch.object(discord.Client, "dispatch"):
        await bot.on_interaction(interaction)

    assert called == []


# ── middleware ────────────────────────────────────────────────────────────────

async def test_component_runs_middleware(bot):
    order = []

    async def mw(ctx, proceed):
        order.append("before")
        await proceed()
        order.append("after")

    bot.use(mw)

    @bot.component("the_btn")
    async def handler(ctx):
        order.append("handler")

    interaction = _make_component_interaction("the_btn")
    with patch.object(discord.Client, "dispatch"):
        await bot.on_interaction(interaction)

    assert order == ["before", "handler", "after"]
