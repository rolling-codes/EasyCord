"""Per-guild XP leveling and named rank system for EasyCord bots."""
from __future__ import annotations

import time
from collections import defaultdict

import discord

from easycord import Plugin, slash, on
from ._levels_data import (
    LevelsStore,
    level_from_xp,
    progress_bar,
    rank_for_level,
    xp_for_level,
)


def _positive_level(level: int) -> bool:
    return level >= 1


class LevelsPlugin(Plugin):
    """Per-guild XP, leveling, and customisable named ranks.

    Members earn XP for sending messages (one award per cooldown window).
    Reaching a new level posts a congratulation embed and optionally assigns
    a configured role reward.  Admins manage ranks and role rewards through
    slash commands.

    Quick start::

        from easycord.plugins.levels import LevelsPlugin

        bot.add_plugin(LevelsPlugin())

    Advanced::

        bot.add_plugin(LevelsPlugin(
            xp_per_message=15,
            cooldown_seconds=45,
            announce_levelups=True,
        ))

    Slash commands registered
    -------------------------
    ``/rank``            — Show your level, XP, and rank.
    ``/leaderboard``     — Top-10 XP leaderboard for the server.
    ``/give_xp``         — (manage_guild) Award XP to a member.
    ``/set_rank``        — (manage_guild) Attach a rank name to a level.
    ``/remove_rank``     — (manage_guild) Delete a rank name.
    ``/set_level_role``  — (manage_guild) Assign a role reward to a level.
    ``/ranks``           — List all configured ranks and role rewards.
    """

    def __init__(
        self,
        *,
        xp_per_message: int = 10,
        cooldown_seconds: float = 60.0,
        data_dir: str = ".easycord/levels",
        announce_levelups: bool = True,
    ) -> None:
        self._store = LevelsStore(data_dir)
        self._xp_per_message = xp_per_message
        self._cooldown = cooldown_seconds
        self._announce = announce_levelups
        self._cooldowns: dict[int, dict[int, float]] = defaultdict(dict)

    # ── Public store delegation ───────────────────────────────

    async def add_xp(
        self, guild_id: int, user_id: int, amount: int
    ) -> tuple[int, int, bool]:
        """Add *amount* XP and return ``(total_xp, level, leveled_up)``."""
        return await self._store.add_xp(guild_id, user_id, amount)

    def get_entry(self, guild_id: int, user_id: int) -> dict:
        """Return a read-only XP/level snapshot for a user."""
        return self._store.get_entry(guild_id, user_id)

    def _build_rank_embed(self, ctx, entry: dict, config: dict) -> discord.Embed:
        level = entry["level"]
        xp = entry["xp"]
        next_xp = xp_for_level(level + 1)
        current_floor = xp_for_level(level)
        embed = discord.Embed(
            title=f"{ctx.user.display_name}'s Rank",
            color=discord.Color.blue(),
        )
        embed.add_field(name="Level", value=str(level), inline=True)
        embed.add_field(name="XP", value=f"{xp:,}", inline=True)
        rank_name = rank_for_level(config, level)
        if rank_name:
            embed.add_field(name="Rank", value=rank_name, inline=True)
        bar = progress_bar(xp, level)
        embed.add_field(
            name=f"Progress to Level {level + 1}",
            value=f"`{bar}` {xp - current_floor:,} / {next_xp - current_floor:,} XP",
            inline=False,
        )
        return embed

    def _build_leaderboard_embed(self, ctx, data: dict, config: dict) -> discord.Embed:
        top = sorted(data.items(), key=lambda kv: kv[1]["xp"], reverse=True)[:10]
        medals = ["🥇", "🥈", "🥉"]
        lines = []
        for i, (uid, entry) in enumerate(top):
            prefix = medals[i] if i < 3 else f"`{i + 1}.`"
            member = ctx.guild.get_member(int(uid))
            name = member.display_name if member else f"User {uid}"
            rank_name = rank_for_level(config, entry["level"])
            rank_text = f" · *{rank_name}*" if rank_name else ""
            lines.append(
                f"{prefix} **{name}** — Level {entry['level']}{rank_text} ({entry['xp']:,} XP)"
            )
        return discord.Embed(
            title=f"🏆 {ctx.guild.name} Leaderboard",
            description="\n".join(lines),
            color=discord.Color.gold(),
        )

    def _build_ranks_embed(self, ctx, config: dict) -> discord.Embed:
        rank_map: dict[str, str] = config.get("ranks", {})
        role_map: dict[str, int] = config.get("role_rewards", {})
        all_levels = sorted(set(rank_map) | set(role_map), key=int)
        lines = []
        for lvl_str in all_levels:
            parts = [f"**Level {lvl_str}**"]
            if lvl_str in rank_map:
                parts.append(f"*{rank_map[lvl_str]}*")
            if lvl_str in role_map:
                role = ctx.guild.get_role(role_map[lvl_str])
                parts.append(role.mention if role else f"Role {role_map[lvl_str]}")
            lines.append(" — ".join(parts))
        return discord.Embed(
            title=f"📊 {ctx.guild.name} Ranks",
            description="\n".join(lines),
            color=discord.Color.blurple(),
        )

    async def _set_config_value(self, guild_id: int, section: str, key: int, value) -> None:
        def updater(config: dict) -> None:
            config.setdefault(section, {})[str(key)] = value

        await self._store.update_config(guild_id, updater)

    async def _remove_config_value(self, guild_id: int, section: str, key: int):
        def updater(config: dict):
            return config.get(section, {}).pop(str(key), None)

        return await self._store.update_config(guild_id, updater)

    # ── Event: award XP on message ────────────────────────────

    @on("message")
    async def _award_xp(self, message: discord.Message) -> None:
        if message.author.bot or not message.guild:
            return

        guild_id = message.guild.id
        user_id = message.author.id
        now = time.monotonic()

        if now - self._cooldowns[guild_id].get(user_id, 0.0) < self._cooldown:
            return
        self._cooldowns[guild_id][user_id] = now

        xp, level, leveled_up = await self._store.add_xp(
            guild_id, user_id, self._xp_per_message
        )

        if not leveled_up or not self._announce:
            return

        config = self._store.read_config(guild_id)
        rank = rank_for_level(config, level)
        rank_text = f" — **{rank}**" if rank else ""

        embed = discord.Embed(
            description=f"{message.author.mention} reached **Level {level}**{rank_text}! 🎉",
            color=discord.Color.gold(),
        )
        embed.set_footer(text=f"Total XP: {xp}")

        role_rewards: dict[str, int] = config.get("role_rewards", {})
        role_id = role_rewards.get(str(level))
        if role_id and isinstance(message.author, discord.Member):
            role = message.guild.get_role(role_id)
            if role:
                try:
                    await message.author.add_roles(role, reason=f"Reached level {level}")
                    embed.add_field(name="Role awarded", value=role.mention, inline=False)
                except discord.HTTPException:
                    pass

        await message.channel.send(embed=embed)

    # ── Slash commands ────────────────────────────────────────

    @slash(description="Show your current level, XP, and rank.", guild_only=True)
    async def rank(self, ctx) -> None:
        entry = self._store.get_entry(ctx.guild.id, ctx.user.id)
        config = self._store.read_config(ctx.guild.id)
        await ctx.respond(embed=self._build_rank_embed(ctx, entry, config), ephemeral=True)

    @slash(description="Show the server's top-10 XP leaderboard.", guild_only=True)
    async def leaderboard(self, ctx) -> None:
        data = self._store.read_xp(ctx.guild.id)
        if not data:
            await ctx.respond("No one has earned XP yet!", ephemeral=True)
            return

        config = self._store.read_config(ctx.guild.id)
        await ctx.respond(embed=self._build_leaderboard_embed(ctx, data, config))

    @slash(description="Award XP to a member.", permissions=["manage_guild"], guild_only=True)
    async def give_xp(self, ctx, member: discord.Member, amount: int) -> None:
        if amount <= 0:
            await ctx.respond("Amount must be a positive number.", ephemeral=True)
            return
        xp, level, leveled_up = await self._store.add_xp(ctx.guild.id, member.id, amount)
        msg = f"Gave **{amount:,} XP** to {member.mention}. They now have **{xp:,} XP** (Level {level})."
        if leveled_up:
            msg += " 🎉 Level up!"
        await ctx.respond(msg)

    @slash(description="Name a rank for a specific level.", permissions=["manage_guild"], guild_only=True)
    async def set_rank(self, ctx, level: int, name: str) -> None:
        if not _positive_level(level):
            await ctx.respond("Level must be at least 1.", ephemeral=True)
            return

        await self._set_config_value(ctx.guild.id, "ranks", level, name)
        await ctx.respond(f"Rank **{name}** set for Level {level}.", ephemeral=True)

    @slash(description="Remove the rank name for a specific level.", permissions=["manage_guild"], guild_only=True)
    async def remove_rank(self, ctx, level: int) -> None:
        removed = await self._remove_config_value(ctx.guild.id, "ranks", level)
        if removed is None:
            await ctx.respond(f"No rank is configured at level {level}.", ephemeral=True)
            return
        await ctx.respond(f"Removed rank **{removed}** from Level {level}.", ephemeral=True)

    @slash(description="Assign a role reward when a member reaches a level.", permissions=["manage_guild"], guild_only=True)
    async def set_level_role(self, ctx, level: int, role: discord.Role) -> None:
        if not _positive_level(level):
            await ctx.respond("Level must be at least 1.", ephemeral=True)
            return

        await self._set_config_value(ctx.guild.id, "role_rewards", level, role.id)
        await ctx.respond(
            f"Members who reach **Level {level}** will receive {role.mention}.",
            ephemeral=True,
        )

    @slash(description="List all configured ranks and role rewards.", guild_only=True)
    async def ranks(self, ctx) -> None:
        config = self._store.read_config(ctx.guild.id)
        if not (config.get("ranks") or config.get("role_rewards")):
            await ctx.respond(
                "No ranks or role rewards configured yet.\n"
                "Use `/set_rank` or `/set_level_role` to add some.",
                ephemeral=True,
            )
            return
        await ctx.respond(embed=self._build_ranks_embed(ctx, config))
