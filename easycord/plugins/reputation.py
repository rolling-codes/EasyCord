"""Per-guild reputation (rep) system plugin."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

import discord

from easycord import Plugin, slash
from easycord.server_config import ServerConfigStore
from ._shared import respond_error

if TYPE_CHECKING:
    from easycord import Context

logger = logging.getLogger(__name__)

_COOLDOWN_HOURS = 24


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------

def _is_on_cooldown(last_given_iso: str | None, now: datetime) -> bool:
    """Return True if last_given was less than 24 hours ago."""
    if last_given_iso is None:
        return False
    last_given = datetime.fromisoformat(last_given_iso)
    return (now - last_given) < timedelta(hours=_COOLDOWN_HOURS)


def _top_entries(scores: dict, limit: int = 10) -> list[tuple[int, int]]:
    """Return [(user_id, score), ...] sorted descending by score, up to limit."""
    return sorted(
        ((int(uid), score) for uid, score in scores.items()),
        key=lambda x: x[1],
        reverse=True,
    )[:limit]


def _rep_embed(username: str, score: int) -> discord.Embed:
    """Build a rep score embed."""
    embed = discord.Embed(
        title=f"Rep: {username}",
        description=f"**{score}** reputation point{'s' if score != 1 else ''}",
        color=discord.Color.green(),
    )
    return embed


# ---------------------------------------------------------------------------
# Plugin
# ---------------------------------------------------------------------------

class ReputationPlugin(Plugin):
    """Track and display per-user reputation within a guild.

    Quick start::

        from easycord.plugins.reputation import ReputationPlugin
        bot.add_plugin(ReputationPlugin())

    Slash commands registered
    -------------------------
    ``/rep <user>``           — Give a rep point to another member (1/24h cooldown).
    ``/rep_check [user]``     — Show rep score (defaults to self if no user given).
    ``/rep_top``              — Leaderboard of top 10 by rep.
    ``/rep_reset <user>``     — Admin: reset a user's rep to 0.
    """

    def __init__(self, *, store_path: str = ".easycord/reputation") -> None:
        super().__init__()
        self._store = ServerConfigStore(store_path)
        self._locks: dict[int, asyncio.Lock] = {}

    def _guild_lock(self, guild_id: int) -> asyncio.Lock:
        if guild_id not in self._locks:
            self._locks[guild_id] = asyncio.Lock()
        return self._locks[guild_id]

    # ------------------------------------------------------------------ #
    # Commands                                                             #
    # ------------------------------------------------------------------ #

    @slash(description="Give a reputation point to another member.", guild_only=True)
    async def rep(self, ctx: "Context", user: discord.User) -> None:
        """Give one rep point to *user*.

        Parameters
        ----------
        user:
            The member to give rep to. Cannot be yourself or a bot.
        """
        if ctx.guild is None:
            return

        giver_id = ctx.user.id
        target_id = user.id

        if target_id == giver_id:
            await respond_error(ctx, "You cannot give rep to yourself.")
            return

        if user.bot:
            await respond_error(ctx, "You cannot give rep to a bot.")
            return

        guild_id = ctx.guild.id
        now = datetime.now(timezone.utc)

        async with self._guild_lock(guild_id):
            cfg = await self._store.load(guild_id)
            data = cfg.get_other("reputation", {})
            cooldowns: dict = data.get("cooldowns", {})

            if _is_on_cooldown(cooldowns.get(str(giver_id)), now):
                await respond_error(ctx, "You already gave rep in the last 24 hours. Try again later.")
                return

            scores: dict = data.get("scores", {})
            scores[str(target_id)] = scores.get(str(target_id), 0) + 1
            cooldowns[str(giver_id)] = now.isoformat()
            data["scores"] = scores
            data["cooldowns"] = cooldowns
            cfg.set_other("reputation", data)
            await self._store.save(cfg)
            new_score = scores[str(target_id)]

        await ctx.respond(
            f"Gave rep to {user.mention}! They now have {new_score} rep."
        )

    @slash(
        description="Check a member's rep score (defaults to yourself).",
        guild_only=True,
    )
    async def rep_check(
        self, ctx: "Context", user: discord.User | None = None
    ) -> None:
        """Show the rep score for *user*, or yourself if omitted.

        Parameters
        ----------
        user:
            The member whose rep to display (optional).
        """
        if ctx.guild is None:
            return

        target = user or ctx.user
        cfg = await self._store.load(ctx.guild.id)
        data = cfg.get_other("reputation", {})
        score = data.get("scores", {}).get(str(target.id), 0)
        embed = _rep_embed(getattr(target, "display_name", str(target)), score)
        await ctx.respond(embed=embed)

    @slash(description="Show the rep leaderboard (top 10).", guild_only=True)
    async def rep_top(self, ctx: "Context") -> None:
        """Display the top 10 members by reputation score."""
        if ctx.guild is None:
            return

        cfg = await self._store.load(ctx.guild.id)
        data = cfg.get_other("reputation", {})
        scores: dict = data.get("scores", {})

        if not scores:
            await respond_error(ctx, "No rep has been given yet.")
            return

        entries = _top_entries(scores)
        lines: list[str] = []
        medals = ["🥇", "🥈", "🥉"]
        for i, (user_id, score) in enumerate(entries):
            member = ctx.guild.get_member(user_id)
            name = member.display_name if member else f"User {user_id}"
            prefix = medals[i] if i < 3 else f"`{i + 1}.`"
            lines.append(f"{prefix} **{name}** — {score} rep")

        embed = discord.Embed(
            title=f"Rep Leaderboard — {ctx.guild.name}",
            description="\n".join(lines),
            color=discord.Color.gold(),
        )
        await ctx.respond(embed=embed)

    @slash(
        description="Reset a member's rep score to 0 (admin only).",
        guild_only=True,
    )
    async def rep_reset(self, ctx: "Context", user: discord.User) -> None:
        """Reset *user*'s reputation to zero.

        Parameters
        ----------
        user:
            The member whose rep to reset.
        """
        if not getattr(ctx, "is_admin", False) and not (
            ctx.member and ctx.member.guild_permissions.manage_guild
        ):
            await respond_error(ctx, "You need the **Manage Guild** permission to reset rep.")
            return

        if ctx.guild is None:
            return

        guild_id = ctx.guild.id

        async with self._guild_lock(guild_id):
            cfg = await self._store.load(guild_id)
            data = cfg.get_other("reputation", {})
            scores: dict = data.get("scores", {})
            scores[str(user.id)] = 0
            data["scores"] = scores
            cfg.set_other("reputation", data)
            await self._store.save(cfg)

        await ctx.respond(
            f"Reset rep for {user.mention} to 0.", ephemeral=True
        )
