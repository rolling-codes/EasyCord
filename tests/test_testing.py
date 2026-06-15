"""Tests for the easycord.testing helpers."""
from __future__ import annotations

from easycord import Bot, Plugin, message_command, slash, user_command
from easycord.testing import (
    FakeContext,
    FakeContextBuilder,
    invoke,
    invoke_component,
    invoke_message_command,
    invoke_modal,
    invoke_user_command,
)


def test_fake_context_captures_responses() -> None:
    ctx = FakeContext.make(user_id=42, guild_id=None)
    assert ctx.user.id == 42
    assert ctx.guild is None
    assert ctx.responses == []

    guild_ctx = FakeContext.make(guild_id=123)
    assert guild_ctx.guild is not None
    assert guild_ctx.guild.id == 123


def test_fake_context_builder_configures_context() -> None:
    entitlement = object()
    ctx = (
        FakeContextBuilder()
        .with_user(42, name="ada", display_name="Ada")
        .in_guild(987, name="Builders")
        .as_admin()
        .with_permissions(manage_messages=True)
        .with_roles(10, 20)
        .with_entitlements(entitlement)
        .with_locale("en-US", guild_locale="en-GB")
        .with_data(custom_id="button:1")
        .build()
    )

    assert ctx.user.id == 42
    assert ctx.user.name == "ada"
    assert ctx.user.display_name == "Ada"
    assert ctx.guild is not None
    assert ctx.guild.id == 987
    assert ctx.guild.name == "Builders"
    assert ctx.is_admin is True
    assert ctx.member is not None
    assert ctx.member is ctx.user
    assert ctx.member.guild_permissions.manage_messages is True
    assert [role.id for role in ctx.member.roles] == [10, 20]
    assert [role.id for role in ctx.guild.roles] == [10, 20]
    assert ctx.entitlements == [entitlement]
    assert ctx.locale == "en-US"
    assert ctx.guild_locale == "en-GB"
    assert ctx.data == {"custom_id": "button:1"}


def test_fake_context_builder_supports_dm_context() -> None:
    ctx = FakeContextBuilder().with_user(5).in_dm().build()

    assert ctx.user.id == 5
    assert ctx.guild is None
    assert ctx.member is None
    assert ctx.is_admin is False


async def test_fake_context_assertions() -> None:
    ctx = FakeContext.make()
    await ctx.respond("hello", ephemeral=True)
    ctx.assert_content("hello")
    ctx.assert_contains("ell")
    assert ctx.was_ephemeral is True
    assert ctx.response_count == 1


async def test_invoke_runs_registered_bot_command() -> None:
    bot = Bot(auto_sync=False, db_backend="memory")
    try:
        @bot.slash(description="Ping")
        async def ping(ctx):
            await ctx.respond("Pong!")

        ctx = await invoke(bot, "ping")
        assert ctx.last_response == "Pong!"
    finally:
        await bot.close()


async def test_invoke_runs_registered_plugin_command() -> None:
    class MathPlugin(Plugin):
        @slash(description="Add")
        async def add(self, ctx, a: int, b: int):
            await ctx.respond(str(a + b))

    bot = Bot(auto_sync=False, db_backend="memory")
    try:
        bot.add_plugin(MathPlugin())
        ctx = await invoke(bot, "add", a=2, b=5)
        assert ctx.last_response == "7"
    finally:
        await bot.close()


async def test_invoke_component_and_modal_helpers() -> None:
    bot = Bot(auto_sync=False, db_backend="memory")
    try:
        @bot.component("confirm:{item_id:int}")
        async def confirm(ctx, item_id: int):
            await ctx.respond(str(item_id))

        @bot.modal("feedback")
        async def feedback(ctx, data):
            await ctx.respond(data["message"])

        component_ctx = await invoke_component(bot, "confirm:7")
        modal_ctx = await invoke_modal(bot, "feedback", message="great")

        assert component_ctx.last_response == "7"
        assert modal_ctx.last_response == "great"
    finally:
        await bot.close()


async def test_invoke_context_menu_helpers() -> None:
    bot = Bot(auto_sync=False, db_backend="memory")
    seen: list[object] = []
    try:
        @bot.user_command(name="Profile")
        async def profile(ctx, member):
            seen.append(member.display_name)
            await ctx.respond(f"profile {member.id}")

        @bot.message_command(name="Quote")
        async def quote(ctx, message):
            seen.append(message.content)
            await ctx.respond(message.content)

        user_ctx = await invoke_user_command(bot, "Profile", target_id=99)
        message_ctx = await invoke_message_command(bot, "Quote", content="ship it")

        assert user_ctx.last_response == "profile 99"
        assert message_ctx.last_response == "ship it"
        assert seen == ["Target 99", "ship it"]
    finally:
        await bot.close()


async def test_invoke_context_menu_helpers_run_plugin_commands() -> None:
    class MenuPlugin(Plugin):
        @user_command(name="Inspect User")
        async def inspect_user(self, ctx, member):
            await ctx.respond(member.display_name)

        @message_command(name="Inspect Message")
        async def inspect_message(self, ctx, message):
            await ctx.respond(message.content.upper())

    bot = Bot(auto_sync=False, db_backend="memory")
    try:
        bot.add_plugin(MenuPlugin())

        user_ctx = await invoke_user_command(bot, "Inspect User", target_id=7)
        message_ctx = await invoke_message_command(
            bot,
            "Inspect Message",
            content="hello",
        )

        assert user_ctx.last_response == "Target 7"
        assert message_ctx.last_response == "HELLO"
    finally:
        await bot.close()
