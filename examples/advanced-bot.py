"""
advanced-bot.py — comprehensive EasyCord bot showing the full feature set together.

Demonstrates:
  - Plugins with per-guild database config via ServerConfigStore
  - Member join events wired to stored welcome messages
  - Background tasks with @task for periodic stat logging
  - Moderation commands (guild-only, admin-only)
  - Function-based custom middleware for request counting
  - SQLite database backend
  - Startup event via @bot.on("ready")

Run:
    DISCORD_TOKEN=... python examples/advanced-bot.py
"""

import logging
import os
from typing import Awaitable, Callable

import discord

from easycord import (
    Bot,
    Plugin,
    ServerConfigStore,
    EasyEmbed,
    on,
    slash,
    task,
)
from easycord.context import Context

logger = logging.getLogger(__name__)


# ── Middleware: request counter ───────────────────────────────────────────────

def request_counter():
    """Middleware that counts every command invocation and logs a running total."""
    total = 0

    async def handler(ctx: Context, proceed: Callable[[], Awaitable[None]]) -> None:
        nonlocal total
        total += 1
        logger.info("[request_counter] total invocations: %d", total)
        await proceed()

    return handler


# ── Plugin: per-guild welcome messages ────────────────────────────────────────

class WelcomePlugin(Plugin):
    """Stores and delivers per-guild welcome messages."""

    async def on_load(self):
        self._store = ServerConfigStore()

    @slash(description="Set the welcome message (use {user} for a mention)", guild_only=True)
    async def set_welcome(self, ctx, message: str):
        config = await self._store.load(ctx.guild.id)
        config.set_other("welcome_msg", message)
        await self._store.save(config)
        await ctx.respond(
            embed=EasyEmbed.success("Welcome message saved."),
            ephemeral=True,
        )

    @on("member_join")
    async def greet_member(self, member: discord.Member):
        config = await self._store.load(member.guild.id)
        msg = config.get_other("welcome_msg")
        if msg and member.guild.system_channel:
            text = msg.replace("{user}", member.mention)
            await member.guild.system_channel.send(text)


# ── Plugin: invocation stats + background reporting ───────────────────────────

class StatsPlugin(Plugin):
    """Tracks per-command invocation counts and logs them every 60 seconds."""

    def __init__(self):
        super().__init__()
        self._counts: dict[str, int] = {}

    @slash(description="Show current command invocation stats")
    async def stats(self, ctx):
        if not self._counts:
            await ctx.respond(embed=EasyEmbed.info("No commands recorded yet."))
            return
        lines = "\n".join(f"`{cmd}` — {n}" for cmd, n in sorted(self._counts.items()))
        await ctx.respond(embed=EasyEmbed.info(f"**Invocation stats**\n{lines}"))
        self._counts["stats"] = self._counts.get("stats", 0) + 1

    @task(seconds=60)
    async def log_stats(self):
        if self._counts:
            summary = ", ".join(f"{k}={v}" for k, v in self._counts.items())
            logger.info("[StatsPlugin] periodic stats: %s", summary)


# ── Plugin: moderation ────────────────────────────────────────────────────────

class ModPlugin(Plugin):
    """Thin wrappers around common moderation actions."""

    @slash(description="Kick a member", guild_only=True, require_admin=True)
    async def kick(self, ctx, member: discord.Member, reason: str = "No reason given"):
        await member.kick(reason=reason)
        logger.info("Kicked %s (ID: %d) — %s", member.display_name, member.id, reason)
        await ctx.respond(
            embed=EasyEmbed.success(f"Kicked {member.display_name}. Reason: {reason}"),
            ephemeral=True,
        )

    @slash(description="Ban a member", guild_only=True, require_admin=True)
    async def ban(self, ctx, member: discord.Member, reason: str = "No reason given"):
        await member.ban(reason=reason)
        logger.info("Banned %s (ID: %d) — %s", member.display_name, member.id, reason)
        await ctx.respond(
            embed=EasyEmbed.success(f"Banned {member.display_name}. Reason: {reason}"),
            ephemeral=True,
        )


# ── Bot setup ─────────────────────────────────────────────────────────────────

bot = Bot(
    intents=discord.Intents.default(),
    auto_sync=True,
    db_backend="sqlite",
    db_path="advanced_bot.db",
)

bot.use(request_counter())

bot.add_plugins(
    WelcomePlugin(),
    StatsPlugin(),
    ModPlugin(),
)


@bot.on("ready")
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    print(f"Connected to {len(bot.guilds)} guild(s)")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    token = os.environ.get("DISCORD_TOKEN")
    if not token:
        raise SystemExit("Set DISCORD_TOKEN environment variable before running.")
    bot.run(token)
