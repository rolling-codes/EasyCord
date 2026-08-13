"""
with-builtin-plugins.py — EasyCord bot showcasing the built-in plugin ecosystem.

Demonstrates:
  - Loading default plugins (tags, levels, polls, welcome) with load_builtin_plugins=True
  - Adding opt-in plugins (moderation, economy, reminders)
  - Per-guild database persistence with SQLite
  - A custom plugin alongside built-ins
  - How to compose a feature-rich bot in under 50 lines

Run:
    DISCORD_TOKEN=... python examples/with-builtin-plugins.py

Available commands (from built-in plugins):
  - /tag set|get|delete|list — per-guild text snippets
  - /rank / /leaderboard — member levels and XP
  - /poll — emoji-based voting
  - /welcome — configurable member join message
  - /kick|ban|unban|timeout|warn — moderation tools
  - /balance|daily|transfer — virtual economy
  - /remind me in 2h do thing — user reminders
"""

import os
import logging

import discord

from easycord import (
    Bot,
    Plugin,
    slash,
    SQLiteDatabase,
)
from easycord.plugins import (
    ModerationPlugin,
    EconomyPlugin,
    ReminderPlugin,
    StarboardPlugin,
)

logger = logging.getLogger(__name__)


# Custom plugin: admin info dashboard

class AdminPlugin(Plugin):
    """Quick admin dashboard for server insights."""

    @slash(description="Show admin dashboard", guild_only=True, require_admin=True)
    async def admin_dashboard(self, ctx):
        """Display a quick overview of bot status and server stats."""
        guild = ctx.guild
        embed = discord.Embed(
            title=f"Admin Dashboard — {guild.name}",
            color=discord.Color.gold(),
        )
        embed.add_field(name="Members", value=str(guild.member_count), inline=True)
        embed.add_field(name="Channels", value=str(len(guild.channels)), inline=True)
        embed.add_field(name="Roles", value=str(len(guild.roles)), inline=True)
        embed.add_field(
            name="Bot Permissions",
            value=", ".join(
                perm.replace("_", " ").title()
                for perm, has_it in ctx.bot_permissions._values.items()
                if has_it
            )[:100] or "None",
            inline=False,
        )
        embed.set_footer(text=f"Guild ID: {guild.id} | Bot prefix: /")
        await ctx.respond(embed=embed, ephemeral=True)


# Bot setup: defaults + opt-ins

bot = Bot(
    intents=discord.Intents.default(),
    auto_sync=True,
    # Load the four default plugins: WelcomePlugin, TagsPlugin, PollsPlugin, LevelsPlugin
    load_builtin_plugins=True,
    # Use SQLite for persistent storage (tags, economy, levels, etc.)
    database=SQLiteDatabase("builtin_plugins_bot.db"),
)

# Add opt-in plugins
bot.add_plugins(
    AdminPlugin(),          # Custom plugin showing how to layer with built-ins
    ModerationPlugin(),     # /kick, /ban, /timeout, /warn
    EconomyPlugin(),        # /balance, /daily, /transfer
    ReminderPlugin(),       # /remind me in X do Y
    StarboardPlugin(),      # React with ⭐ to pin messages
)


@bot.on("ready")
async def on_ready():
    print(f"✓ Logged in as {bot.user}")
    print(f"✓ Connected to {len(bot.guilds)} guild(s)")
    print(f"✓ Loaded built-in plugins: welcome, tags, polls, levels")
    print(f"✓ Loaded opt-in plugins: moderation, economy, reminders, starboard, admin")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    token = os.environ.get("DISCORD_TOKEN")
    if not token:
        raise SystemExit("Set DISCORD_TOKEN environment variable before running.")
    bot.run(token)
