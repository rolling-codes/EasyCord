"""Tests for the EasyCord v5.2 interaction architecture helpers."""
from __future__ import annotations

import asyncio

import pytest

import discord
from discord import app_commands

from easycord import Bot, Plugin, SlashGroup, autocomplete, component, slash, slash_command, task
from easycord.registry import InteractionRegistry
from easycord.testing import FakeInteraction, invoke_autocomplete
from easycord.validators import ChoiceSet, Duration, Range, Regex, Snowflake, URL, ValidationError


def test_slash_command_alias_is_public_alias() -> None:
    assert slash_command is slash


async def test_registry_tracks_slash_and_context_menu_inventory() -> None:
    bot = Bot(auto_sync=False, db_backend="memory")
    try:
        @bot.slash(description="Ping")
        async def ping(ctx):
            await ctx.respond("pong")

        @bot.user_command(name="Profile")
        async def profile(ctx, member):
            await ctx.respond(str(member.id))

        grouped = bot.inspect_interactions()
        assert [entry["name"] for entry in grouped["slash"]] == ["ping"]
        assert [entry["name"] for entry in grouped["context_menu"]] == ["Profile"]
        assert grouped["slash"][0]["sync_state"] == "local"
    finally:
        await bot.close()


async def test_discord_271_metadata_reaches_slash_context_menu_and_group() -> None:
    contexts = app_commands.AppCommandContext(
        guild=True,
        dm_channel=True,
        private_channel=True,
    )
    installs = app_commands.AppInstallationType(guild=True, user=True)

    class UtilityGroup(
        SlashGroup,
        name="utility",
        description="Utility commands",
        allowed_contexts=contexts,
        allowed_installs=installs,
    ):
        @slash(description="Group ping")
        async def ping(self, ctx):
            await ctx.respond("pong")

    bot = Bot(auto_sync=False, db_backend="memory")
    try:
        @bot.slash(
            description="Info",
            allowed_contexts=contexts,
            allowed_installs=installs,
        )
        async def info(ctx):
            await ctx.respond("info")

        @bot.user_command(
            name="Profile",
            allowed_contexts=contexts,
            allowed_installs=installs,
        )
        async def profile(ctx, member):
            await ctx.respond(str(member.id))

        bot.add_group(UtilityGroup())

        slash_cmd = bot.tree.get_command("info")
        menu_cmd = bot.tree.get_command("Profile", type=discord.AppCommandType.user)
        group_cmd = bot.tree.get_command("utility")

        assert slash_cmd is not None
        assert menu_cmd is not None
        assert group_cmd is not None
        assert slash_cmd.allowed_contexts is contexts
        assert slash_cmd.allowed_installs is installs
        assert menu_cmd.allowed_contexts is contexts
        assert menu_cmd.allowed_installs is installs
        assert group_cmd.allowed_contexts is contexts
        assert group_cmd.allowed_installs is installs
    finally:
        await bot.close()


def test_registry_detects_dynamic_static_component_collision() -> None:
    registry = InteractionRegistry()
    registry.register_component("ticket:close:{ticket_id:int}", lambda: None)
    with pytest.raises(ValueError, match="collides"):
        registry.register_component("ticket:close:123", lambda: None)


async def test_dynamic_component_route_parses_typed_variables() -> None:
    bot = Bot(auto_sync=False, db_backend="memory")
    seen = []
    try:
        @bot.component("poll:vote:{poll_id:int}:{choice_id:int}")
        async def vote(ctx, poll_id: int, choice_id: int):
            seen.append((poll_id, choice_id))
            await ctx.respond("voted")

        interaction = FakeInteraction(client=bot)
        interaction.data = {"custom_id": "poll:vote:42:7"}
        await bot._dispatch_component(interaction)  # type: ignore[arg-type]

        assert seen == [(42, 7)]
        assert interaction._responses[-1].content == "voted"
    finally:
        await bot.close()


async def test_component_ttl_expiration_is_safe_noop() -> None:
    bot = Bot(auto_sync=False, db_backend="memory")
    called = False
    try:
        @bot.component("expired:{item:int}", ttl=0.001)
        async def expired(ctx, item: int):
            nonlocal called
            called = True

        await asyncio.sleep(0.01)
        interaction = FakeInteraction(client=bot)
        interaction.data = {"custom_id": "expired:1"}
        await bot._dispatch_component(interaction)  # type: ignore[arg-type]

        assert called is False
        assert interaction._responses == []
    finally:
        await bot.close()


async def test_plugin_unload_unregisters_owned_registry_entries() -> None:
    class TicketPlugin(Plugin):
        @slash(description="Ticket")
        async def ticket(self, ctx):
            await ctx.respond("ticket")

        @component("ticket:close:{ticket_id:int}")
        async def close_ticket(self, ctx, ticket_id: int):
            await ctx.respond(str(ticket_id))

    bot = Bot(auto_sync=False, db_backend="memory")
    plugin = TicketPlugin()
    try:
        bot.add_plugin(plugin)
        assert bot.inspect_interactions()["slash"]
        assert bot.inspect_interactions()["component"]

        await bot.remove_plugin(plugin)

        assert bot.inspect_interactions()["slash"] == []
        assert bot.inspect_interactions()["component"] == []
    finally:
        await bot.close()


async def test_autocomplete_decorator_and_testing_helper() -> None:
    class FruitPlugin(Plugin):
        @autocomplete("fruit", command="pick")
        async def fruit_autocomplete(self, ctx, current: str, options: dict):
            return [name for name in ["apple", "banana"] if current in name]

        @slash(description="Pick")
        async def pick(self, ctx, fruit: str):
            await ctx.respond(fruit)

    bot = Bot(auto_sync=False, db_backend="memory")
    try:
        bot.add_plugin(FruitPlugin())
        results = await invoke_autocomplete(bot, "pick", "fruit", "app")
        assert results == ["apple"]
        assert bot.inspect_interactions()["autocomplete"][0]["metadata"]["option_name"] == "fruit"
    finally:
        await bot.close()


async def test_command_sync_plan_and_dry_run_detects_diff() -> None:
    bot = Bot(auto_sync=False, db_backend="memory")
    try:
        @bot.slash(description="Ping")
        async def ping(ctx):
            await ctx.respond("pong")

        plan = bot.plan_command_sync(remote_commands=["old"])
        dry = await bot.sync_commands(dry_run=True, remote_commands=["old"])

        assert plan["added"] == ["ping"]
        assert plan["removed"] == ["old"]
        assert dry == plan
    finally:
        await bot.close()


def test_sync_plan_duplicate_command_warning() -> None:
    registry = InteractionRegistry()
    registry.register_slash_command("same", lambda: None)
    registry.slash_commands["global:same-copy"] = registry.slash_commands["global:same"]
    bot = Bot(auto_sync=False, db_backend="memory")
    try:
        bot.registry = registry
        assert "Duplicate local command name: same" in bot.plan_command_sync()["warnings"]
    finally:
        asyncio.run(bot.close())


async def test_task_status_tracks_failure() -> None:
    class TaskPlugin(Plugin):
        @task(seconds=0.001)
        async def doomed(self):
            raise RuntimeError("boom")

    bot = Bot(auto_sync=False, db_backend="memory")
    try:
        plugin = TaskPlugin()
        bot.add_plugin(plugin)
        bot._start_plugin_tasks(plugin)
        await asyncio.sleep(0.02)

        status = bot.task_statuses()[f"{plugin._instance_id}.doomed"]
        assert status["state"] == "failed"
        assert "boom" in status["last_error"]  # type: ignore[operator]
    finally:
        await bot.close()


def test_option_validators() -> None:
    assert Duration()("2m") == 120
    assert URL()("https://example.com") == "https://example.com"
    assert Snowflake()("123456789012345678") == 123456789012345678
    assert Range(min=1, max=3)(2) == 2
    assert Regex(r"[a-z]+", min_length=2)("abc") == "abc"
    assert ChoiceSet("red", "blue")("red") == "red"
    with pytest.raises(ValidationError):
        URL()("not a url")
