"""Economy system — earn, spend, and trade in-game currency."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

import discord

from easycord import Plugin, slash, on
from easycord.plugins._config_manager import PluginConfigManager

if TYPE_CHECKING:
    from easycord import Context

logger = logging.getLogger(__name__)

_DEFAULTS = {
    "enabled": True,
    "currency_name": "Credits",
    "currency_symbol": "💰",
    "daily_reward": 100,
    "message_reward": 1,
}

# Maximum guild locks to track before cleanup (prevents unbounded memory growth)
MAX_TRACKED_GUILDS = 5000


class EconomyPlugin(Plugin):
    """In-game economy with currency, rewards, and shop.

    Members earn currency through messages, daily rewards, and special events.
    Shop system allows spending currency on roles or items.

    Quick start::

        from easycord.plugins.economy import EconomyPlugin

        bot.add_plugin(EconomyPlugin())

    Commands::

        /balance              — Check your balance
        /daily                — Claim daily reward
        /economy_leaderboard  — Top earners
        /transfer <user> <amount>  — Send currency to user
        /shop                 — View shop items
        /buy <item>           — Purchase item
    """

    def __init__(self):
        super().__init__()
        self.config = PluginConfigManager(".easycord/economy")
        self._balance_locks: dict[int, asyncio.Lock] = {}
        self._lock_created: dict[int, datetime] = {}  # Track creation time for cleanup

    def _balance_lock(self, guild_id: int) -> asyncio.Lock:
        """Per-guild lock serializing all economy state mutations.

        All economy operations that call ``store.save()`` for a guild must run
        under this lock. Because ``ServerConfigStore.save()`` writes the full
        config object, an unlocked save based on a stale load can silently
        overwrite balances or claim state written by a concurrent locked path.
        """
        if guild_id not in self._balance_locks:
            self._balance_locks[guild_id] = asyncio.Lock()
            self._lock_created[guild_id] = datetime.now(timezone.utc)
            self._cleanup_old_locks()
        return self._balance_locks[guild_id]

    def _cleanup_old_locks(self) -> None:
        """Remove old, unused locks to prevent unbounded memory growth.
        
        Cleans up locks older than 7 days and enforces a maximum number of
        tracked guilds. This prevents memory leaks in large/busy bots with
        many transient guilds.
        """
        now = datetime.now(timezone.utc)
        max_age = timedelta(days=7)
        
        # Remove locks older than 7 days
        keys_to_remove = [
            guild_id
            for guild_id, created_at in self._lock_created.items()
            if now - created_at > max_age
        ]
        for guild_id in keys_to_remove:
            del self._balance_locks[guild_id]
            del self._lock_created[guild_id]
        
        # If still over limit, remove oldest locks
        if len(self._balance_locks) > MAX_TRACKED_GUILDS:
            sorted_guilds = sorted(
                self._lock_created.items(),
                key=lambda x: x[1],
            )
            # Remove oldest 25% to make room
            remove_count = len(sorted_guilds) // 4
            for guild_id, _ in sorted_guilds[:remove_count]:
                del self._balance_locks[guild_id]
                del self._lock_created[guild_id]

    async def on_load(self) -> None:
        """Initialize economy plugin."""
        logger.info("EconomyPlugin loaded")

    async def _get_config(self, guild_id: int) -> dict:
        """Get economy config for guild."""
        return await self.config.get(guild_id, "economy", _DEFAULTS)

    async def _get_balance(self, guild_id: int, user_id: int) -> int:
        """Get user's balance (read-only; does not require the lock)."""
        cfg_obj = await self.config.store.load(guild_id)
        balances = cfg_obj.get_other("balances", {})
        return balances.get(str(user_id), 0)

    async def _set_balance(self, guild_id: int, user_id: int, amount: int) -> None:
        """Set user's balance.

        Must only be called while the caller holds ``_balance_lock(guild_id)``.
        """
        cfg_obj = await self.config.store.load(guild_id)
        balances = cfg_obj.get_other("balances", {})
        balances[str(user_id)] = max(0, amount)
        cfg_obj.set_other("balances", balances)
        await self.config.store.save(cfg_obj)

    async def _add_balance(self, guild_id: int, user_id: int, amount: int) -> int:
        """Add *amount* to user's balance under the per-guild lock.

        Returns the new balance. The operation is atomic: balance is read,
        modified, and saved under a single lock acquisition.
        """
        async with self._balance_lock(guild_id):
            current = await self._get_balance(guild_id, user_id)
            new_balance = current + amount
            await self._set_balance(guild_id, user_id, new_balance)
            return new_balance

    async def _transfer(
        self,
        guild_id: int,
        sender_id: int,
        receiver_id: int,
        amount: int,
    ) -> tuple[bool, int]:
        """Atomically transfer *amount* from sender to receiver.

        Reads the config once, computes both new balances in memory, and
        persists them in a single save under the per-guild lock.  No
        half-applied state is possible on disk: if the save raises, neither
        balance has changed.

        Returns ``(success, sender_balance_after)``.
        """
        async with self._balance_lock(guild_id):
            cfg_obj = await self.config.store.load(guild_id)
            balances = cfg_obj.get_other("balances", {})

            sender_balance = balances.get(str(sender_id), 0)
            if sender_balance < amount:
                return False, sender_balance

            receiver_balance = balances.get(str(receiver_id), 0)
            balances[str(sender_id)] = max(0, sender_balance - amount)
            balances[str(receiver_id)] = max(0, receiver_balance + amount)
            cfg_obj.set_other("balances", balances)
            await self.config.store.save(cfg_obj)

            return True, sender_balance - amount

    async def _get_daily_claimed(self, guild_id: int, user_id: int) -> bool:
        """Check if user claimed today's reward (read-only; no lock needed)."""
        cfg_obj = await self.config.store.load(guild_id)
        daily_claims = cfg_obj.get_other("daily_claims", {})
        today = datetime.now(timezone.utc).date().isoformat()
        claimed_date = daily_claims.get(str(user_id))
        return claimed_date == today

    async def _mark_daily_claimed(self, guild_id: int, user_id: int) -> None:
        """Mark daily reward as claimed.

        Must only be called while the caller holds ``_balance_lock(guild_id)``.
        """
        cfg_obj = await self.config.store.load(guild_id)
        daily_claims = cfg_obj.get_other("daily_claims", {})
        today = datetime.now(timezone.utc).date().isoformat()
        daily_claims[str(user_id)] = today
        cfg_obj.set_other("daily_claims", daily_claims)
        await self.config.store.save(cfg_obj)

    @on("message")
    async def _on_message(self, message: discord.Message) -> None:
        """Award currency for messages."""
        if not message.guild or message.author.bot or not message.content:
            return

        cfg = await self._get_config(message.guild.id)
        if not cfg.get("enabled"):
            return

        reward = cfg.get("message_reward", 1)
        if reward > 0:
            await self._add_balance(message.guild.id, message.author.id, reward)

    @slash(description="Check your balance", guild_only=True)
    async def balance(self, ctx: Context) -> None:
        """Show user's balance."""
        cfg = await self._get_config(ctx.guild.id)
        balance = await self._get_balance(ctx.guild.id, ctx.user.id)
        currency = cfg.get("currency_name", "Credits")
        symbol = cfg.get("currency_symbol", "💰")
        await ctx.respond(f"{symbol} {ctx.user.mention} has **{balance}** {currency}")

    @slash(description="Claim daily reward", guild_only=True)
    async def daily(self, ctx: Context) -> None:
        """Claim daily currency reward.

        The claimed-check, balance award, and claim-mark all happen under a
        single lock and a single config save operation to prevent partial persistence.
        All I/O to Discord (ctx.respond) happens after releasing the lock.
        """
        already_claimed = False
        reward = symbol = currency = new_balance = None

        async with self._balance_lock(ctx.guild.id):
            cfg_obj = await self.config.store.load(ctx.guild.id)

            daily_claims = cfg_obj.get_other("daily_claims", {})
            today = datetime.now(timezone.utc).date().isoformat()

            if daily_claims.get(str(ctx.user.id)) == today:
                already_claimed = True
            else:
                cfg = cfg_obj.get_other("economy") or _DEFAULTS
                reward = cfg.get("daily_reward", 100)
                currency = cfg.get("currency_name", "Credits")
                symbol = cfg.get("currency_symbol", "💰")

                balances = cfg_obj.get_other("balances", {})
                current = balances.get(str(ctx.user.id), 0)
                new_balance = current + reward
                balances[str(ctx.user.id)] = new_balance

                daily_claims[str(ctx.user.id)] = today

                cfg_obj.set_other("balances", balances)
                cfg_obj.set_other("daily_claims", daily_claims)
                await self.config.store.save(cfg_obj)

        if already_claimed:
            await ctx.respond(
                "⏰ You already claimed today's reward. Try again tomorrow!",
                ephemeral=True,
            )
            return

        await ctx.respond(f"{symbol} Claimed **{reward}** {currency}! New balance: **{new_balance}**")

    @slash(description="Top earners leaderboard", guild_only=True)
    async def economy_leaderboard(self, ctx: Context) -> None:
        """Show top 10 richest members."""
        cfg_obj = await self.config.store.load(ctx.guild.id)
        balances = cfg_obj.get_other("balances", {})

        if not balances:
            await ctx.respond("No one has currency yet!")
            return

        sorted_balances = sorted(
            [(int(uid), balance) for uid, balance in balances.items()],
            key=lambda x: x[1],
            reverse=True
        )[:10]

        cfg = await self._get_config(ctx.guild.id)
        symbol = cfg.get("currency_symbol", "💰")

        lines = []
        medals = ["🥇", "🥈", "🥉"]
        for i, (user_id, balance) in enumerate(sorted_balances):
            member = ctx.guild.get_member(user_id)
            name = member.display_name if member else f"User {user_id}"
            prefix = medals[i] if i < 3 else f"`{i+1}.`"
            lines.append(f"{prefix} **{name}** — {balance} {symbol}")

        embed = discord.Embed(
            title=f"💰 {ctx.guild.name} Leaderboard",
            description="\n".join(lines),
            color=discord.Color.gold(),
        )
        await ctx.respond(embed=embed)

    @slash(description="Transfer currency to another user", guild_only=True)
    async def transfer(self, ctx: Context, user: discord.User, amount: int) -> None:
        """Send currency to another user."""
        if amount <= 0:
            await ctx.respond("❌ Amount must be positive", ephemeral=True)
            return

        if user.id == ctx.user.id:
            await ctx.respond("❌ Can't transfer to yourself", ephemeral=True)
            return

        ok, sender_balance_after = await self._transfer(
            ctx.guild.id, ctx.user.id, user.id, amount
        )
        if not ok:
            await ctx.respond(
                f"❌ Insufficient balance (you have {sender_balance_after})",
                ephemeral=True,
            )
            return

        cfg = await self._get_config(ctx.guild.id)
        currency = cfg.get("currency_name", "Credits")
        await ctx.respond(f"✅ Transferred **{amount}** {currency} to {user.mention}")
