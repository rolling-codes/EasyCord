"""Economy system — earn, spend, and trade in-game currency."""
from __future__ import annotations

import logging
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
        /leaderboard          — Top earners
        /transfer <user> <amount>  — Send currency to user
        /shop                 — View shop items
        /buy <item>           — Purchase item
    """

    def __init__(self):
        super().__init__()
        self.config = PluginConfigManager(".easycord/economy")

    async def on_load(self) -> None:
        """Initialize economy plugin."""
        logger.info("EconomyPlugin loaded")

    async def _get_config(self, guild_id: int) -> dict:
        """Get economy config for guild."""
        return await self.config.get(guild_id, "economy", _DEFAULTS)

    async def _get_balance(self, guild_id: int, user_id: int) -> int:
        """Get user's balance."""
        cfg_obj = await self.config.store.load(guild_id)
        balances = cfg_obj.get_other("balances", {})
        return balances.get(str(user_id), 0)

    async def _set_balance(self, guild_id: int, user_id: int, amount: int) -> None:
        """Set user's balance."""
        cfg_obj = await self.config.store.load(guild_id)
        balances = cfg_obj.get_other("balances", {})
        balances[str(user_id)] = max(0, amount)
        cfg_obj.set_other("balances", balances)
        await self.config.store.save(cfg_obj)

    async def _add_balance(self, guild_id: int, user_id: int, amount: int) -> int:
        """Add to user's balance. Return new balance."""
        current = await self._get_balance(guild_id, user_id)
        new_balance = current + amount
        await self._set_balance(guild_id, user_id, new_balance)
        return new_balance

    async def _get_daily_claimed(self, guild_id: int, user_id: int) -> bool:
        """Check if user claimed today's reward."""
        cfg_obj = await self.config.store.load(guild_id)
        daily_claims = cfg_obj.get_other("daily_claims", {})
        from datetime import datetime, timezone
        today = datetime.now(timezone.utc).date().isoformat()
        claimed_date = daily_claims.get(str(user_id))
        return claimed_date == today

    async def _mark_daily_claimed(self, guild_id: int, user_id: int) -> None:
        """Mark daily reward as claimed."""
        cfg_obj = await self.config.store.load(guild_id)
        daily_claims = cfg_obj.get_other("daily_claims", {})
        from datetime import datetime, timezone
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
        """Claim daily currency reward."""
        if await self._get_daily_claimed(ctx.guild.id, ctx.user.id):
            await ctx.respond("⏰ You already claimed today's reward. Try again tomorrow!", ephemeral=True)
            return

        cfg = await self._get_config(ctx.guild.id)
        reward = cfg.get("daily_reward", 100)
        currency = cfg.get("currency_name", "Credits")
        symbol = cfg.get("currency_symbol", "💰")

        new_balance = await self._add_balance(ctx.guild.id, ctx.user.id, reward)
        await self._mark_daily_claimed(ctx.guild.id, ctx.user.id)
        await ctx.respond(f"{symbol} Claimed **{reward}** {currency}! New balance: **{new_balance}**")

    @slash(description="Top earners leaderboard", guild_only=True)
    async def leaderboard(self, ctx: Context) -> None:
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
        currency = cfg.get("currency_name", "Credits")
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
        await ctx.send_embed_from_dict(embed.to_dict())

    @slash(description="Transfer currency to another user", guild_only=True)
    async def transfer(self, ctx: Context, user: discord.User, amount: int) -> None:
        """Send currency to another user."""
        if amount <= 0:
            await ctx.respond("❌ Amount must be positive", ephemeral=True)
            return

        if user.id == ctx.user.id:
            await ctx.respond("❌ Can't transfer to yourself", ephemeral=True)
            return

        sender_balance = await self._get_balance(ctx.guild.id, ctx.user.id)
        if sender_balance < amount:
            await ctx.respond(f"❌ Insufficient balance (you have {sender_balance})", ephemeral=True)
            return

        await self._add_balance(ctx.guild.id, ctx.user.id, -amount)
        new_recipient = await self._add_balance(ctx.guild.id, user.id, amount)

        cfg = await self._get_config(ctx.guild.id)
        currency = cfg.get("currency_name", "Credits")
        await ctx.respond(f"✅ Transferred **{amount}** {currency} to {user.mention}")
