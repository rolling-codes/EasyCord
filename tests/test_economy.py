"""Tests for EconomyPlugin — store logic, cooldowns, and command flows."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

import discord

from easycord.plugins.economy import EconomyPlugin, _DEFAULTS
from easycord.server_config import ServerConfigStore
from plugin_test_helpers import make_ctx, make_discord_user


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _plugin(tmp_path) -> EconomyPlugin:
    """Construct an EconomyPlugin wired to a tmp_path store (no Discord needed)."""
    p = EconomyPlugin.__new__(EconomyPlugin)
    EconomyPlugin.__init__(p)
    # Redirect config store to tmp_path so tests are fully offline and isolated.
    p.config.store = ServerConfigStore(str(tmp_path / "economy"))
    return p


def _ctx(guild_id: int = 100, user_id: int = 1, is_admin: bool = False) -> MagicMock:
    return make_ctx(guild_id=guild_id, user_id=user_id, is_admin=is_admin)


def _discord_user(user_id: int) -> MagicMock:
    return make_discord_user(user_id)


# ---------------------------------------------------------------------------
# Layer 1 — Internal store helpers
# ---------------------------------------------------------------------------

class TestEconomyStore:
    async def test_get_balance_default_zero(self, tmp_path) -> None:
        p = _plugin(tmp_path)
        bal = await p._get_balance(100, 42)
        assert bal == 0

    async def test_set_and_get_balance(self, tmp_path) -> None:
        p = _plugin(tmp_path)
        async with p._balance_lock(100):
            await p._set_balance(100, 42, 500)
        bal = await p._get_balance(100, 42)
        assert bal == 500

    async def test_set_balance_clamps_to_zero(self, tmp_path) -> None:
        """Negative amounts are stored as 0."""
        p = _plugin(tmp_path)
        async with p._balance_lock(100):
            await p._set_balance(100, 42, -100)
        assert await p._get_balance(100, 42) == 0

    async def test_add_balance_accumulates(self, tmp_path) -> None:
        p = _plugin(tmp_path)
        new_bal = await p._add_balance(100, 1, 200)
        assert new_bal == 200
        new_bal2 = await p._add_balance(100, 1, 50)
        assert new_bal2 == 250

    async def test_guild_isolation(self, tmp_path) -> None:
        """Balances in guild A must not affect guild B."""
        p = _plugin(tmp_path)
        await p._add_balance(100, 1, 999)
        bal_b = await p._get_balance(200, 1)
        assert bal_b == 0

    async def test_user_isolation_within_guild(self, tmp_path) -> None:
        p = _plugin(tmp_path)
        await p._add_balance(100, 1, 100)
        await p._add_balance(100, 2, 200)
        assert await p._get_balance(100, 1) == 100
        assert await p._get_balance(100, 2) == 200

    async def test_transfer_success(self, tmp_path) -> None:
        p = _plugin(tmp_path)
        await p._add_balance(100, 1, 300)
        ok, remaining = await p._transfer(100, sender_id=1, receiver_id=2, amount=100)
        assert ok is True
        assert remaining == 200
        assert await p._get_balance(100, 1) == 200
        assert await p._get_balance(100, 2) == 100

    async def test_transfer_insufficient_funds(self, tmp_path) -> None:
        p = _plugin(tmp_path)
        await p._add_balance(100, 1, 50)
        ok, remaining = await p._transfer(100, sender_id=1, receiver_id=2, amount=100)
        assert ok is False
        assert remaining == 50
        # Neither balance changes
        assert await p._get_balance(100, 1) == 50
        assert await p._get_balance(100, 2) == 0

    async def test_transfer_exact_balance_succeeds(self, tmp_path) -> None:
        p = _plugin(tmp_path)
        await p._add_balance(100, 1, 100)
        ok, remaining = await p._transfer(100, sender_id=1, receiver_id=2, amount=100)
        assert ok is True
        assert remaining == 0

    async def test_transfer_atomicity_no_currency_created(self, tmp_path) -> None:
        """Total supply is conserved across a successful transfer."""
        p = _plugin(tmp_path)
        await p._add_balance(100, 1, 500)
        await p._add_balance(100, 2, 100)
        await p._transfer(100, sender_id=1, receiver_id=2, amount=200)
        total = await p._get_balance(100, 1) + await p._get_balance(100, 2)
        assert total == 600

    async def test_daily_claimed_false_by_default(self, tmp_path) -> None:
        p = _plugin(tmp_path)
        assert await p._get_daily_claimed(100, 1) is False

    async def test_daily_mark_claimed_sets_flag(self, tmp_path) -> None:
        p = _plugin(tmp_path)
        await p._mark_daily_claimed(100, 1)
        assert await p._get_daily_claimed(100, 1) is True

    async def test_daily_claimed_isolated_per_guild(self, tmp_path) -> None:
        p = _plugin(tmp_path)
        await p._mark_daily_claimed(100, 1)
        assert await p._get_daily_claimed(200, 1) is False

    async def test_get_config_returns_defaults_when_unset(self, tmp_path) -> None:
        p = _plugin(tmp_path)
        cfg = await p._get_config(100)
        assert cfg["currency_name"] == _DEFAULTS["currency_name"]
        assert cfg["daily_reward"] == _DEFAULTS["daily_reward"]

    async def test_concurrent_add_balance_is_atomic(self, tmp_path) -> None:
        """Concurrent adds under _add_balance must not drop writes."""
        p = _plugin(tmp_path)
        tasks = [p._add_balance(100, 1, 10) for _ in range(20)]
        await asyncio.gather(*tasks)
        assert await p._get_balance(100, 1) == 200

    async def test_lock_cleanup_does_not_remove_active_locks(self, tmp_path) -> None:
        p = _plugin(tmp_path)
        # Access lock so it is created
        lock = p._balance_lock(100)
        async with lock:
            # Cleanup while the lock is acquired should NOT remove it
            p._cleanup_old_locks()
            assert 100 in p._balance_locks


# ---------------------------------------------------------------------------
# Layer 2 — /balance command
# ---------------------------------------------------------------------------

class TestBalanceCommand:
    async def test_balance_shows_zero_for_new_user(self, tmp_path) -> None:
        p = _plugin(tmp_path)
        ctx = _ctx(guild_id=100, user_id=1)
        await p.balance(ctx)
        ctx.respond.assert_called_once()
        response = ctx.respond.call_args[0][0]
        assert "0" in response

    async def test_balance_shows_correct_amount(self, tmp_path) -> None:
        p = _plugin(tmp_path)
        await p._add_balance(100, 1, 750)
        ctx = _ctx(guild_id=100, user_id=1)
        await p.balance(ctx)
        response = ctx.respond.call_args[0][0]
        assert "750" in response

    async def test_balance_includes_currency_name(self, tmp_path) -> None:
        p = _plugin(tmp_path)
        ctx = _ctx(guild_id=100, user_id=1)
        await p.balance(ctx)
        response = ctx.respond.call_args[0][0]
        assert "Credits" in response

    async def test_balance_includes_user_mention(self, tmp_path) -> None:
        p = _plugin(tmp_path)
        ctx = _ctx(guild_id=100, user_id=42)
        ctx.user.mention = "<@42>"
        await p.balance(ctx)
        response = ctx.respond.call_args[0][0]
        assert "<@42>" in response

    async def test_balance_isolated_per_guild(self, tmp_path) -> None:
        p = _plugin(tmp_path)
        await p._add_balance(100, 1, 500)
        ctx = _ctx(guild_id=200, user_id=1)
        await p.balance(ctx)
        response = ctx.respond.call_args[0][0]
        assert "500" not in response
        assert "0" in response


# ---------------------------------------------------------------------------
# Layer 3 — /daily command
# ---------------------------------------------------------------------------

class TestDailyCommand:
    async def test_daily_first_claim_succeeds(self, tmp_path) -> None:
        p = _plugin(tmp_path)
        ctx = _ctx(guild_id=100, user_id=1)
        await p.daily(ctx)
        ctx.respond.assert_called_once()
        response = ctx.respond.call_args[0][0]
        assert "100" in response  # default daily_reward

    async def test_daily_increases_balance(self, tmp_path) -> None:
        p = _plugin(tmp_path)
        ctx = _ctx(guild_id=100, user_id=1)
        await p.daily(ctx)
        bal = await p._get_balance(100, 1)
        assert bal == 100

    async def test_daily_second_claim_same_day_rejected(self, tmp_path) -> None:
        p = _plugin(tmp_path)
        ctx = _ctx(guild_id=100, user_id=1)
        await p.daily(ctx)
        ctx.respond.reset_mock()
        await p.daily(ctx)
        args, kwargs = ctx.respond.call_args
        assert kwargs.get("ephemeral") is True
        assert "already" in (args[0] if args else "").lower()

    async def test_daily_second_claim_does_not_change_balance(self, tmp_path) -> None:
        p = _plugin(tmp_path)
        ctx = _ctx(guild_id=100, user_id=1)
        await p.daily(ctx)
        bal_after_first = await p._get_balance(100, 1)
        await p.daily(ctx)
        assert await p._get_balance(100, 1) == bal_after_first

    async def test_daily_cooldown_resets_after_date_changes(self, tmp_path) -> None:
        """Claiming on a different date should succeed even if already claimed today."""
        p = _plugin(tmp_path)
        guild_id, user_id = 100, 1

        # Manually write yesterday's date as the claim date
        cfg_obj = await p.config.store.load(guild_id)
        daily_claims = cfg_obj.get_other("daily_claims", {})
        daily_claims[str(user_id)] = "2000-01-01"  # far in the past
        cfg_obj.set_other("daily_claims", daily_claims)
        await p.config.store.save(cfg_obj)

        ctx = _ctx(guild_id=guild_id, user_id=user_id)
        await p.daily(ctx)
        # Should succeed — stale claim date treated as unclaimed
        args, kwargs = ctx.respond.call_args
        assert kwargs.get("ephemeral") is not True

    async def test_daily_response_contains_new_balance(self, tmp_path) -> None:
        p = _plugin(tmp_path)
        await p._add_balance(100, 1, 50)
        ctx = _ctx(guild_id=100, user_id=1)
        await p.daily(ctx)
        response = ctx.respond.call_args[0][0]
        # 50 existing + 100 daily reward = 150
        assert "150" in response

    async def test_daily_independent_per_user(self, tmp_path) -> None:
        p = _plugin(tmp_path)
        ctx1 = _ctx(guild_id=100, user_id=1)
        ctx2 = _ctx(guild_id=100, user_id=2)
        await p.daily(ctx1)
        # User 2 should be able to claim even after user 1 claimed
        await p.daily(ctx2)
        args, kwargs = ctx2.respond.call_args
        assert kwargs.get("ephemeral") is not True


# ---------------------------------------------------------------------------
# Layer 4 — /transfer command
# ---------------------------------------------------------------------------

class TestTransferCommand:
    async def test_transfer_success_message(self, tmp_path) -> None:
        p = _plugin(tmp_path)
        await p._add_balance(100, 1, 500)
        ctx = _ctx(guild_id=100, user_id=1)
        target = _discord_user(2)
        await p.transfer(ctx, user=target, amount=200)
        response = ctx.respond.call_args[0][0]
        assert "200" in response
        assert "Credits" in response

    async def test_transfer_updates_balances(self, tmp_path) -> None:
        p = _plugin(tmp_path)
        await p._add_balance(100, 1, 500)
        ctx = _ctx(guild_id=100, user_id=1)
        target = _discord_user(2)
        await p.transfer(ctx, user=target, amount=200)
        assert await p._get_balance(100, 1) == 300
        assert await p._get_balance(100, 2) == 200

    async def test_transfer_insufficient_funds_error(self, tmp_path) -> None:
        p = _plugin(tmp_path)
        await p._add_balance(100, 1, 50)
        ctx = _ctx(guild_id=100, user_id=1)
        target = _discord_user(2)
        await p.transfer(ctx, user=target, amount=100)
        args, kwargs = ctx.respond.call_args
        assert kwargs.get("ephemeral") is True
        assert "Insufficient" in (args[0] if args else "")

    async def test_transfer_negative_amount_rejected(self, tmp_path) -> None:
        p = _plugin(tmp_path)
        await p._add_balance(100, 1, 500)
        ctx = _ctx(guild_id=100, user_id=1)
        target = _discord_user(2)
        await p.transfer(ctx, user=target, amount=-10)
        args, kwargs = ctx.respond.call_args
        assert kwargs.get("ephemeral") is True
        assert "positive" in (args[0] if args else "").lower()

    async def test_transfer_zero_amount_rejected(self, tmp_path) -> None:
        p = _plugin(tmp_path)
        await p._add_balance(100, 1, 500)
        ctx = _ctx(guild_id=100, user_id=1)
        target = _discord_user(2)
        await p.transfer(ctx, user=target, amount=0)
        args, kwargs = ctx.respond.call_args
        assert kwargs.get("ephemeral") is True

    async def test_transfer_self_transfer_rejected(self, tmp_path) -> None:
        p = _plugin(tmp_path)
        await p._add_balance(100, 1, 500)
        ctx = _ctx(guild_id=100, user_id=1)
        target = _discord_user(1)  # Same user id as ctx.user.id
        await p.transfer(ctx, user=target, amount=100)
        args, kwargs = ctx.respond.call_args
        assert kwargs.get("ephemeral") is True
        assert "yourself" in (args[0] if args else "").lower()

    async def test_transfer_does_not_change_balances_on_failure(self, tmp_path) -> None:
        p = _plugin(tmp_path)
        await p._add_balance(100, 1, 50)
        await p._add_balance(100, 2, 100)
        ctx = _ctx(guild_id=100, user_id=1)
        target = _discord_user(2)
        await p.transfer(ctx, user=target, amount=200)
        assert await p._get_balance(100, 1) == 50
        assert await p._get_balance(100, 2) == 100

    async def test_transfer_recipient_mention_in_response(self, tmp_path) -> None:
        p = _plugin(tmp_path)
        await p._add_balance(100, 1, 300)
        ctx = _ctx(guild_id=100, user_id=1)
        target = _discord_user(7)
        await p.transfer(ctx, user=target, amount=50)
        response = ctx.respond.call_args[0][0]
        assert "<@7>" in response


# ---------------------------------------------------------------------------
# Layer 5 — /economy_leaderboard command
# ---------------------------------------------------------------------------

class TestLeaderboardCommand:
    async def test_leaderboard_empty_guild(self, tmp_path) -> None:
        p = _plugin(tmp_path)
        ctx = _ctx(guild_id=100)
        await p.economy_leaderboard(ctx)
        ctx.respond.assert_called_once()
        response = ctx.respond.call_args[0][0]
        assert "No one" in response or "no" in response.lower()

    async def test_leaderboard_shows_embed_when_balances_exist(self, tmp_path) -> None:
        p = _plugin(tmp_path)
        await p._add_balance(100, 1, 500)
        await p._add_balance(100, 2, 300)
        ctx = _ctx(guild_id=100)
        await p.economy_leaderboard(ctx)
        _, kwargs = ctx.respond.call_args
        assert "embed" in kwargs
        embed = kwargs["embed"]
        assert isinstance(embed, discord.Embed)

    async def test_leaderboard_top_earner_first(self, tmp_path) -> None:
        p = _plugin(tmp_path)
        await p._add_balance(100, 1, 100)
        await p._add_balance(100, 2, 999)
        await p._add_balance(100, 3, 500)
        ctx = _ctx(guild_id=100)
        await p.economy_leaderboard(ctx)
        _, kwargs = ctx.respond.call_args
        embed = kwargs["embed"]
        # User 2 has the most — should appear first in description
        lines = embed.description.split("\n")
        first_line = lines[0]
        assert "999" in first_line or "User 2" in first_line

    async def test_leaderboard_max_ten_entries(self, tmp_path) -> None:
        p = _plugin(tmp_path)
        for uid in range(1, 16):
            await p._add_balance(100, uid, uid * 10)
        ctx = _ctx(guild_id=100)
        await p.economy_leaderboard(ctx)
        _, kwargs = ctx.respond.call_args
        embed = kwargs["embed"]
        lines = [l for l in embed.description.split("\n") if l.strip()]
        assert len(lines) <= 10

    async def test_leaderboard_isolated_per_guild(self, tmp_path) -> None:
        p = _plugin(tmp_path)
        await p._add_balance(100, 1, 1000)
        ctx = _ctx(guild_id=200)  # different guild
        await p.economy_leaderboard(ctx)
        response = ctx.respond.call_args[0][0]
        # Guild 200 has no balances — should get empty message, not guild 100's data
        assert "No one" in response or "no" in response.lower()


# ---------------------------------------------------------------------------
# Layer 6 — on_message event (message reward)
# ---------------------------------------------------------------------------

class TestMessageReward:
    async def test_message_reward_adds_balance(self, tmp_path) -> None:
        p = _plugin(tmp_path)
        message = MagicMock()
        message.guild = MagicMock()
        message.guild.id = 100
        message.author = MagicMock()
        message.author.id = 1
        message.author.bot = False
        message.content = "hello"

        await p._on_message(message)
        bal = await p._get_balance(100, 1)
        assert bal == 1  # default message_reward

    async def test_message_reward_skips_bot_messages(self, tmp_path) -> None:
        p = _plugin(tmp_path)
        message = MagicMock()
        message.guild = MagicMock()
        message.guild.id = 100
        message.author = MagicMock()
        message.author.id = 99
        message.author.bot = True
        message.content = "bot says hi"

        await p._on_message(message)
        assert await p._get_balance(100, 99) == 0

    async def test_message_reward_skips_empty_content(self, tmp_path) -> None:
        p = _plugin(tmp_path)
        message = MagicMock()
        message.guild = MagicMock()
        message.guild.id = 100
        message.author = MagicMock()
        message.author.id = 5
        message.author.bot = False
        message.content = ""

        await p._on_message(message)
        assert await p._get_balance(100, 5) == 0

    async def test_message_reward_skips_dm_messages(self, tmp_path) -> None:
        p = _plugin(tmp_path)
        message = MagicMock()
        message.guild = None  # DM
        message.author = MagicMock()
        message.author.id = 5
        message.author.bot = False
        message.content = "hi"

        await p._on_message(message)
        # No guild — no balance should be written anywhere
        assert await p._get_balance(100, 5) == 0
