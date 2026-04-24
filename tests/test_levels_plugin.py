"""Tests for easycord.plugins.levels — LevelsPlugin."""
import asyncio
import json
import time
import discord
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from easycord.plugins.levels import LevelsPlugin
from easycord.plugins._levels_data import (
    xp_for_level as _xp_for_level,
    level_from_xp as _level_from_xp,
    rank_for_level,
    progress_bar,
)


# ── Formula tests ─────────────────────────────────────────────────────────────

def test_xp_for_level_zero():
    assert _xp_for_level(0) == 0


def test_xp_for_level_one():
    assert _xp_for_level(1) == 100


def test_xp_for_level_two():
    assert _xp_for_level(2) == 300


def test_xp_for_level_five():
    assert _xp_for_level(5) == 1500


def test_xp_for_level_ten():
    assert _xp_for_level(10) == 5500


def test_level_from_xp_zero():
    assert _level_from_xp(0) == 0


def test_level_from_xp_exactly_level_one():
    assert _level_from_xp(100) == 1


def test_level_from_xp_just_below_level_two():
    assert _level_from_xp(299) == 1


def test_level_from_xp_exactly_level_two():
    assert _level_from_xp(300) == 2


def test_level_from_xp_level_ten():
    assert _level_from_xp(5500) == 10


def test_xp_level_roundtrip():
    for level in range(1, 20):
        assert _level_from_xp(_xp_for_level(level)) == level


# ── Plugin fixtures ───────────────────────────────────────────────────────────

@pytest.fixture
def plugin(tmp_path):
    """LevelsPlugin backed by a temporary directory."""
    return LevelsPlugin(
        xp_per_message=10,
        cooldown_seconds=60.0,
        data_dir=str(tmp_path / "levels"),
        announce_levelups=True,
    )


def _make_guild(guild_id: int = 1) -> MagicMock:
    guild = MagicMock(spec=discord.Guild)
    guild.id = guild_id
    guild.name = "Test Server"
    return guild


def _make_member(user_id: int = 42, *, bot: bool = False) -> MagicMock:
    member = MagicMock(spec=discord.Member)
    member.id = user_id
    member.bot = bot
    member.display_name = f"User{user_id}"
    member.mention = f"<@{user_id}>"
    member.voice = None
    member.add_roles = AsyncMock()
    return member


def _make_message(
    guild_id: int = 1,
    user_id: int = 42,
    *,
    bot: bool = False,
    guild: bool = True,
) -> MagicMock:
    msg = MagicMock(spec=discord.Message)
    msg.channel = MagicMock()
    msg.channel.send = AsyncMock()
    author = _make_member(user_id, bot=bot)
    msg.author = author
    if guild:
        g = _make_guild(guild_id)
        g.get_role = MagicMock(return_value=None)
        msg.guild = g
        author.guild = g
    else:
        msg.guild = None
    return msg


def _make_ctx(guild_id: int = 1, user_id: int = 42) -> MagicMock:
    ctx = MagicMock()
    ctx.respond = AsyncMock()
    ctx.guild = _make_guild(guild_id)
    member = _make_member(user_id)
    ctx.user = member
    ctx.user.id = user_id
    ctx.user.display_name = f"User{user_id}"
    ctx.guild.get_member = MagicMock(return_value=member)
    ctx.guild.get_role = MagicMock(return_value=None)
    # Mock ctx.t() to return the default value
    def t_mock(key, default=None, **kwargs):
        if default is not None:
            # Simple substitution of kwargs into default
            return default.format(**kwargs) if kwargs else default
        return key
    ctx.t = MagicMock(side_effect=t_mock)
    return ctx


# ── add_xp ────────────────────────────────────────────────────────────────────

async def test_add_xp_returns_total_and_level(plugin):
    xp, level, leveled_up = await plugin.add_xp(1, 42, 50)
    assert xp == 50
    assert level == 0
    assert leveled_up is False


async def test_add_xp_accumulates(plugin):
    await plugin.add_xp(1, 42, 60)
    xp, level, leveled_up = await plugin.add_xp(1, 42, 60)
    assert xp == 120
    assert level == 1
    assert leveled_up is True


async def test_add_xp_persists_to_disk(plugin, tmp_path):
    await plugin.add_xp(1, 42, 200)
    path = tmp_path / "levels" / "1_xp.json"
    assert path.exists()
    data = json.loads(path.read_text())
    assert data["42"]["xp"] == 200


async def test_add_xp_independent_per_guild(plugin):
    await plugin.add_xp(guild_id=1, user_id=42, amount=100)
    await plugin.add_xp(guild_id=2, user_id=42, amount=50)
    xp1, *_ = await plugin.add_xp(guild_id=1, user_id=42, amount=0)
    xp2, *_ = await plugin.add_xp(guild_id=2, user_id=42, amount=0)
    assert xp1 == 100
    assert xp2 == 50


async def test_add_xp_independent_per_user(plugin):
    await plugin.add_xp(guild_id=1, user_id=1, amount=100)
    await plugin.add_xp(guild_id=1, user_id=2, amount=300)
    _, level1, _ = await plugin.add_xp(guild_id=1, user_id=1, amount=0)
    _, level2, _ = await plugin.add_xp(guild_id=1, user_id=2, amount=0)
    assert level1 == 1
    assert level2 == 2


# ── get_entry ─────────────────────────────────────────────────────────────────

async def test_get_entry_returns_zeros_for_new_user(plugin):
    entry = plugin.get_entry(guild_id=1, user_id=99)
    assert entry == {"xp": 0, "level": 0}


async def test_get_entry_reflects_stored_xp(plugin):
    await plugin.add_xp(1, 42, 300)  # _xp_for_level(2) == 300
    entry = plugin.get_entry(1, 42)
    assert entry["xp"] == 300
    assert entry["level"] == 2


# ── _rank_for_level ───────────────────────────────────────────────────────────

def test_rank_for_level_no_ranks():
    assert rank_for_level({}, 5) is None


def test_rank_for_level_exact_match():
    config = {"ranks": {"5": "Veteran"}}
    assert rank_for_level(config, 5) == "Veteran"


def test_rank_for_level_below_lowest_threshold():
    config = {"ranks": {"5": "Veteran"}}
    assert rank_for_level(config, 3) is None


def test_rank_for_level_picks_highest_applicable():
    config = {"ranks": {"1": "Newbie", "5": "Regular", "10": "Veteran"}}
    assert rank_for_level(config, 7) == "Regular"
    assert rank_for_level(config, 10) == "Veteran"
    assert rank_for_level(config, 1) == "Newbie"


# ── _progress_bar ─────────────────────────────────────────────────────────────

def test_progress_bar_empty_at_level_start():
    # At exactly level 1 (100 XP), progress toward level 2 is 0%
    bar = progress_bar(xp=100, level=1, width=10)
    assert bar == "░" * 10


def test_progress_bar_half_full():
    # Level 1→2 costs 200 XP (from 100 to 300). Halfway = 200 XP.
    bar = progress_bar(xp=200, level=1, width=10)
    assert bar == "█" * 5 + "░" * 5


def test_progress_bar_full_at_level_boundary():
    # At exactly level 2 (300 XP), next level floor=300, ceil=600, progress=0.
    bar = progress_bar(xp=300, level=2, width=10)
    assert bar == "░" * 10


# ── _award_xp event handler ───────────────────────────────────────────────────

async def test_award_xp_ignores_bot_messages(plugin):
    msg = _make_message(bot=True)
    await plugin._award_xp(msg)
    assert plugin.get_entry(1, msg.author.id)["xp"] == 0


async def test_award_xp_ignores_dm_messages(plugin):
    msg = _make_message(guild=False)
    await plugin._award_xp(msg)


async def test_award_xp_adds_xp_to_member(plugin):
    msg = _make_message(guild_id=1, user_id=42)
    await plugin._award_xp(msg)
    assert plugin.get_entry(1, 42)["xp"] == 10


async def test_award_xp_respects_cooldown(plugin):
    msg = _make_message(guild_id=1, user_id=42)
    await plugin._award_xp(msg)
    await plugin._award_xp(msg)  # second message within cooldown
    assert plugin.get_entry(1, 42)["xp"] == 10  # only awarded once


async def test_award_xp_independent_users_no_cooldown_sharing(plugin):
    msg1 = _make_message(guild_id=1, user_id=1)
    msg2 = _make_message(guild_id=1, user_id=2)
    await plugin._award_xp(msg1)
    await plugin._award_xp(msg2)
    assert plugin.get_entry(1, 1)["xp"] == 10
    assert plugin.get_entry(1, 2)["xp"] == 10


async def test_award_xp_posts_levelup_embed(plugin):
    # Give enough XP to be one short of level 1 so next message levels up.
    await plugin.add_xp(1, 42, 90)
    msg = _make_message(guild_id=1, user_id=42)
    # Reset cooldown so the message handler fires.
    plugin._cooldowns[1][42] = 0.0
    await plugin._award_xp(msg)
    msg.channel.send.assert_called_once()
    embed = msg.channel.send.call_args.kwargs.get("embed") or msg.channel.send.call_args[1].get("embed")
    assert embed is not None
    assert "Level 1" in embed.description


async def test_award_xp_no_levelup_embed_when_announce_disabled(plugin, tmp_path):
    quiet = LevelsPlugin(
        xp_per_message=10,
        cooldown_seconds=0,
        data_dir=str(tmp_path / "quiet"),
        announce_levelups=False,
    )
    await quiet.add_xp(1, 42, 90)
    msg = _make_message(guild_id=1, user_id=42)
    quiet._cooldowns[1][42] = 0.0
    await quiet._award_xp(msg)
    msg.channel.send.assert_not_called()


async def test_award_xp_assigns_role_reward_on_levelup(plugin, tmp_path):
    await plugin._store.update_config(1, lambda c: c.update({"role_rewards": {str(1): 999}}))
    role = MagicMock(spec=discord.Role)
    role.mention = "@Member"
    msg = _make_message(guild_id=1, user_id=42)
    msg.guild.get_role = MagicMock(return_value=role)
    await plugin.add_xp(1, 42, 90)
    plugin._cooldowns[1][42] = 0.0
    await plugin._award_xp(msg)
    msg.author.add_roles.assert_called_once_with(role, reason="Reached level 1")


# ── /rank slash command ───────────────────────────────────────────────────────

async def test_rank_command_responds_with_embed(plugin):
    ctx = _make_ctx(guild_id=1, user_id=42)
    await plugin.add_xp(1, 42, 350)
    await plugin.rank(ctx)
    ctx.respond.assert_called_once()
    embed = ctx.respond.call_args.kwargs["embed"]
    assert embed is not None
    assert "Level" in [f.name for f in embed.fields]


async def test_rank_command_shows_rank_name(plugin):
    ctx = _make_ctx(guild_id=1, user_id=42)
    await plugin._store.update_config(1, lambda c: c.update({"ranks": {"2": "Regular"}}))
    await plugin.add_xp(1, 42, 350)  # level 2
    await plugin.rank(ctx)
    embed = ctx.respond.call_args.kwargs["embed"]
    field_names = [f.name for f in embed.fields]
    assert "Rank" in field_names


# ── /leaderboard slash command ────────────────────────────────────────────────

async def test_leaderboard_shows_top_members(plugin):
    await plugin.add_xp(1, 1, 500)
    await plugin.add_xp(1, 2, 200)
    ctx = _make_ctx(guild_id=1)
    ctx.guild.get_member = MagicMock(return_value=None)
    await plugin.leaderboard(ctx)
    embed = ctx.respond.call_args.kwargs.get("embed") or ctx.respond.call_args[1].get("embed")
    assert embed is not None
    assert "500" in embed.description


async def test_leaderboard_empty_guild(plugin):
    ctx = _make_ctx(guild_id=99)
    await plugin.leaderboard(ctx)
    ctx.respond.assert_called_once()
    assert ctx.respond.call_args.kwargs.get("ephemeral") is True


# ── /give_xp slash command ────────────────────────────────────────────────────

async def test_give_xp_adds_xp(plugin):
    ctx = _make_ctx(guild_id=1, user_id=1)
    member = _make_member(user_id=2)
    await plugin.give_xp(ctx, member, 200)
    assert plugin.get_entry(1, 2)["xp"] == 200
    ctx.respond.assert_called_once()


async def test_give_xp_rejects_non_positive(plugin):
    ctx = _make_ctx(guild_id=1)
    member = _make_member(user_id=2)
    await plugin.give_xp(ctx, member, 0)
    msg = ctx.respond.call_args[0][0]
    assert "positive" in msg.lower()


async def test_give_xp_announces_levelup(plugin):
    ctx = _make_ctx(guild_id=1)
    member = _make_member(user_id=2)
    await plugin.give_xp(ctx, member, 150)  # triggers level 1
    response = ctx.respond.call_args[0][0]
    assert "Level up" in response


# ── /set_rank and /remove_rank slash commands ─────────────────────────────────

async def test_set_rank_saves_config(plugin, tmp_path):
    ctx = _make_ctx(guild_id=1)
    await plugin.set_rank(ctx, level=5, name="Veteran")
    config = plugin._store.read_config(1)
    assert config["ranks"]["5"] == "Veteran"


async def test_set_rank_rejects_level_zero(plugin):
    ctx = _make_ctx(guild_id=1)
    await plugin.set_rank(ctx, level=0, name="Nobody")
    assert ctx.respond.call_args.kwargs.get("ephemeral") is True


async def test_remove_rank_deletes_entry(plugin):
    ctx = _make_ctx(guild_id=1)
    await plugin.set_rank(ctx, level=5, name="Veteran")
    await plugin.remove_rank(ctx, level=5)
    config = plugin._store.read_config(1)
    assert "5" not in config.get("ranks", {})


async def test_remove_rank_missing_level(plugin):
    ctx = _make_ctx(guild_id=1)
    await plugin.remove_rank(ctx, level=99)
    assert ctx.respond.call_args.kwargs.get("ephemeral") is True
    assert "No rank" in ctx.respond.call_args[0][0]


# ── /set_level_role slash command ─────────────────────────────────────────────

async def test_set_level_role_saves_role_id(plugin):
    ctx = _make_ctx(guild_id=1)
    role = MagicMock(spec=discord.Role)
    role.id = 777
    role.mention = "@Member"
    await plugin.set_level_role(ctx, level=3, role=role)
    config = plugin._store.read_config(1)
    assert config["role_rewards"]["3"] == 777


# ── /ranks slash command ──────────────────────────────────────────────────────

async def test_ranks_shows_configured_ranks(plugin):
    ctx = _make_ctx(guild_id=1)
    await plugin._store.update_config(1, lambda c: c.update({"ranks": {"1": "Newbie", "10": "Veteran"}}))
    await plugin.ranks(ctx)
    embed = ctx.respond.call_args.kwargs.get("embed") or ctx.respond.call_args[1].get("embed")
    assert embed is not None
    assert "Newbie" in embed.description
    assert "Veteran" in embed.description


async def test_ranks_empty_server(plugin):
    ctx = _make_ctx(guild_id=1)
    await plugin.ranks(ctx)
    assert ctx.respond.call_args.kwargs.get("ephemeral") is True
