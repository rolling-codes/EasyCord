"""
core-bot.py — production EasyCord bot with no AI dependencies.

Demonstrates:
  - Slash commands with EasyEmbed helpers
  - Event handlers
  - A Plugin with per-guild config via ServerConfigStore
  - A SlashGroup (subcommand namespace)
  - Bot startup hook

Run:
    DISCORD_TOKEN=... python examples/core-bot.py
"""

import os
import discord
from easycord import (
    Bot,
    Plugin,
    SlashGroup,
    slash,
    on,
    EasyEmbed,
    ServerConfigStore,
)


# ── Plugin: general commands ──────────────────────────────────────────────────

class GeneralPlugin(Plugin):
    """Basic utility commands available in every guild."""

    @slash(description="Check bot latency")
    async def ping(self, ctx):
        ms = round(ctx._bot.latency * 1000)
        await ctx.respond(embed=EasyEmbed.info(f"Pong! `{ms} ms`"))

    @slash(description="Show server info", guild_only=True)
    async def serverinfo(self, ctx):
        guild = ctx.guild
        embed = discord.Embed(
            title=guild.name,
            color=discord.Color.blurple(),
        )
        embed.add_field(name="Members", value=str(guild.member_count), inline=True)
        embed.add_field(name="Channels", value=str(len(guild.channels)), inline=True)
        embed.add_field(name="Roles", value=str(len(guild.roles)), inline=True)
        embed.set_footer(text=f"ID: {guild.id}")
        await ctx.respond(embed=embed)


# ── Plugin: per-guild welcome config ─────────────────────────────────────────

class SettingsGroup(SlashGroup, name="settings", description="Server configuration"):
    """Subcommands for configuring the bot on this server."""

    def __init__(self):
        self._store = ServerConfigStore()

    @slash(description="Set a welcome message (use {user} for a mention)")
    async def set_welcome(self, ctx, message: str):
        config = await self._store.load(ctx.guild.id)
        config.set_other("welcome_msg", message)
        await self._store.save(config)
        await ctx.respond(
            embed=EasyEmbed.success("Welcome message saved."),
            ephemeral=True,
        )

    @slash(description="Show the current welcome message")
    async def show_welcome(self, ctx):
        config = await self._store.load(ctx.guild.id)
        msg = config.get_other("welcome_msg")
        if msg:
            await ctx.respond(embed=EasyEmbed.info(f"Current welcome: {msg}"))
        else:
            await ctx.respond(
                embed=EasyEmbed.warning("No welcome message set yet."),
                ephemeral=True,
            )

    @on("member_join")
    async def greet_member(self, member: discord.Member):
        config = await self._store.load(member.guild.id)
        msg = config.get_other("welcome_msg")
        if msg and member.guild.system_channel:
            text = msg.replace("{user}", member.mention)
            await member.guild.system_channel.send(text)


# ── Plugin: moderation shortcuts ─────────────────────────────────────────────

class ModPlugin(Plugin):
    """Thin wrappers around common moderation actions."""

    @slash(description="Kick a member", guild_only=True, require_admin=True)
    async def kick(self, ctx, member: discord.Member, reason: str = "No reason given"):
        await member.kick(reason=reason)
        await ctx.respond(
            embed=EasyEmbed.success(f"Kicked {member.display_name}. Reason: {reason}"),
            ephemeral=True,
        )

    @slash(description="Ban a member", guild_only=True, require_admin=True)
    async def ban(self, ctx, member: discord.Member, reason: str = "No reason given"):
        await member.ban(reason=reason)
        await ctx.respond(
            embed=EasyEmbed.success(f"Banned {member.display_name}. Reason: {reason}"),
            ephemeral=True,
        )


# ── Bot setup ─────────────────────────────────────────────────────────────────

bot = Bot(
    intents=discord.Intents.default(),
    auto_sync=True,
)

bot.add_plugins(
    GeneralPlugin(),
    SettingsGroup(),
    ModPlugin(),
)


@bot.on("ready")
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    print(f"Connected to {len(bot.guilds)} guild(s)")


if __name__ == "__main__":
    token = os.environ.get("DISCORD_TOKEN")
    if not token:
        raise SystemExit("Set DISCORD_TOKEN environment variable before running.")
    bot.run(token)
