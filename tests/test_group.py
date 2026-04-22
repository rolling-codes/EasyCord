import discord
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from easycord import Bot, SlashGroup
from easycord.decorators import slash


@pytest.fixture
def bot():
    mock_tree = MagicMock()
    mock_tree.add_command = MagicMock()
    mock_tree.remove_command = MagicMock()
    mock_tree.sync = AsyncMock()

    with patch("discord.Client.__init__", return_value=None), \
         patch("easycord.bot.app_commands.CommandTree", return_value=mock_tree):
        b = Bot(intents=MagicMock(), auto_sync=False)
        b.is_ready = MagicMock(return_value=False)
        return b


def test_add_group_registers_group_command(bot):
    class TestGroup(SlashGroup, name="test", description="Test group"):
        @slash(description="Sub A")
        async def sub_a(self, ctx):
            pass

    bot.add_group(TestGroup())
    bot.tree.add_command.assert_called_once()


def test_add_group_group_name(bot):
    class TestGroup(SlashGroup, name="mygroup", description="desc"):
        @slash(description="cmd")
        async def cmd(self, ctx):
            pass

    bot.add_group(TestGroup())
    group_arg = bot.tree.add_command.call_args[0][0]
    assert group_arg.name == "mygroup"


def test_add_group_subcommand_count(bot):
    class Multi(SlashGroup, name="multi", description="multiple subcommands"):
        @slash(description="One")
        async def one(self, ctx):
            pass

        @slash(description="Two")
        async def two(self, ctx):
            pass

    bot.add_group(Multi())
    group_arg = bot.tree.add_command.call_args[0][0]
    assert len(group_arg.commands) == 2


def test_add_group_sets_bot_reference(bot):
    class G(SlashGroup, name="g", description="g"):
        @slash(description="x")
        async def x(self, ctx):
            pass

    g = G()
    bot.add_group(g)
    assert g._bot is bot


def test_add_group_duplicate_raises(bot):
    class G(SlashGroup, name="g", description="g"):
        @slash(description="x")
        async def x(self, ctx):
            pass

    g = G()
    bot.add_group(g)
    with pytest.raises(ValueError):
        bot.add_group(g)


def test_slash_group_name_defaults_to_class_name(bot):
    class MyGroup(SlashGroup, description="desc"):
        @slash(description="cmd")
        async def cmd(self, ctx):
            pass

    bot.add_group(MyGroup())
    group_arg = bot.tree.add_command.call_args[0][0]
    assert group_arg.name == "mygroup"


def test_slash_group_guild_scoped(bot):
    class G(SlashGroup, name="g", description="g", guild_id=99999):
        @slash(description="x")
        async def x(self, ctx):
            pass

    bot.add_group(G())
    _, kwargs = bot.tree.add_command.call_args
    assert kwargs.get("guild") is not None
    assert kwargs["guild"].id == 99999


def test_slash_group_nsfw_and_guild_only_forwarded(bot):
    class G(SlashGroup, name="g", description="g", guild_only=True, nsfw=True):
        @slash(description="x")
        async def x(self, ctx):
            pass

    bot.add_group(G())
    group_arg = bot.tree.add_command.call_args[0][0]
    assert getattr(group_arg, "nsfw", False) is True
    assert getattr(group_arg, "guild_only", False) is True


def test_add_groups_registers_multiple_groups(bot):
    class A(SlashGroup, name="a", description="A"):
        pass

    class B(SlashGroup, name="b", description="B"):
        pass

    bot.add_groups(A(), B())
    assert bot.tree.add_command.call_count == 2
