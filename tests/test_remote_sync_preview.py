"""Focused coverage for read-only remote command sync previews."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import discord
import pytest

from easycord import Bot, SlashGroup, slash


def remote_command(name: str, command_type: discord.AppCommandType):
    return SimpleNamespace(name=name, type=command_type)


async def test_preview_fetches_global_commands_without_syncing() -> None:
    bot = Bot(auto_sync=False, db_backend="memory")
    try:
        @bot.slash(description="Ping")
        async def ping(ctx):
            await ctx.respond("pong")

        bot.tree.fetch_commands = AsyncMock(
            return_value=[remote_command("old", discord.AppCommandType.chat_input)]
        )
        bot.tree.sync = AsyncMock()
        bot.tree.copy_global_to = Mock()

        plan = await bot.preview_command_sync()

        assert plan == {
            "added": ["ping"],
            "changed": [],
            "removed": ["old"],
            "unchanged": [],
            "warnings": [],
        }
        bot.tree.fetch_commands.assert_awaited_once_with()
        bot.tree.sync.assert_not_awaited()
        bot.tree.copy_global_to.assert_not_called()
    finally:
        await bot.close()


async def test_guild_preview_fetches_target_and_includes_global_commands() -> None:
    bot = Bot(auto_sync=False, db_backend="memory")
    try:
        @bot.slash(description="Global")
        async def global_command(ctx):
            await ctx.respond("global")

        @bot.slash(name="guild-command", description="Guild", guild_id=42)
        async def guild_command(ctx):
            await ctx.respond("guild")

        bot.tree.fetch_commands = AsyncMock(
            return_value=[
                remote_command("global_command", discord.AppCommandType.chat_input),
                remote_command("guild-command", discord.AppCommandType.chat_input),
            ]
        )
        bot.tree.sync = AsyncMock()
        bot.tree.copy_global_to = Mock()

        plan = await bot.preview_command_sync(guild_id=42)

        assert plan["unchanged"] == ["global_command", "guild-command"]
        guild = bot.tree.fetch_commands.await_args.kwargs["guild"]
        assert isinstance(guild, discord.Object)
        assert guild.id == 42
        bot.tree.sync.assert_not_awaited()
        bot.tree.copy_global_to.assert_not_called()
    finally:
        await bot.close()


async def test_preview_compares_command_type_and_name() -> None:
    bot = Bot(auto_sync=False, db_backend="memory")
    try:
        @bot.slash(name="inspect", description="Inspect")
        async def inspect_command(ctx):
            await ctx.respond("inspect")

        bot.tree.fetch_commands = AsyncMock(
            return_value=[remote_command("inspect", discord.AppCommandType.user)]
        )

        plan = await bot.preview_command_sync()

        assert plan["added"] == ["inspect"]
        assert plan["removed"] == ["inspect"]
        assert plan["unchanged"] == []
    finally:
        await bot.close()


async def test_preview_preserves_distinct_context_menu_types() -> None:
    bot = Bot(auto_sync=False, db_backend="memory")
    try:
        @bot.user_command(name="Inspect")
        async def inspect_user(ctx, user):
            return None

        async def inspect_message(
            interaction: discord.Interaction,
            message: discord.Message,
        ) -> None:
            return None

        bot.tree.add_command(
            discord.app_commands.ContextMenu(
                name="Inspect",
                callback=inspect_message,
                type=discord.AppCommandType.message,
            )
        )

        bot.tree.fetch_commands = AsyncMock(
            return_value=[
                remote_command("Inspect", discord.AppCommandType.user),
                remote_command("Inspect", discord.AppCommandType.message),
            ]
        )

        plan = await bot.preview_command_sync()

        assert plan["unchanged"] == ["Inspect", "Inspect"]
        assert plan["added"] == []
        assert plan["removed"] == []
        assert plan["warnings"] == []
    finally:
        await bot.close()


async def test_preview_uses_top_level_group_identity() -> None:
    class UtilityGroup(SlashGroup, name="utility", description="Utilities"):
        @slash(description="Ping")
        async def ping(self, ctx):
            await ctx.respond("pong")

    bot = Bot(auto_sync=False, db_backend="memory")
    try:
        bot.add_group(UtilityGroup())
        bot.tree.fetch_commands = AsyncMock(
            return_value=[remote_command("utility", discord.AppCommandType.chat_input)]
        )

        plan = await bot.preview_command_sync()

        assert plan["unchanged"] == ["utility"]
        assert plan["added"] == []
        assert plan["removed"] == []
    finally:
        await bot.close()


async def test_preview_propagates_fetch_exceptions() -> None:
    bot = Bot(auto_sync=False, db_backend="memory")
    try:
        error = RuntimeError("Discord unavailable")
        bot.tree.fetch_commands = AsyncMock(side_effect=error)

        with pytest.raises(RuntimeError, match="Discord unavailable") as caught:
            await bot.preview_command_sync()

        assert caught.value is error
    finally:
        await bot.close()


def test_existing_string_sync_plan_remains_name_based() -> None:
    bot = Bot(auto_sync=False, db_backend="memory")
    try:
        @bot.slash(name="inspect", description="Inspect")
        async def inspect_command(ctx):
            await ctx.respond("inspect")

        assert bot.plan_command_sync(remote_commands=["inspect"]) == {
            "added": [],
            "changed": [],
            "removed": [],
            "unchanged": ["inspect"],
            "warnings": [],
        }
    finally:
        import asyncio

        asyncio.run(bot.close())
