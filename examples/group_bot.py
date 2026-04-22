"""Example bot that uses grouped slash commands."""
from __future__ import annotations

from easycord import Composer, SlashGroup, slash

from examples._runtime import run_bot


class ModerationGroup(SlashGroup, name="mod", description="Moderation commands"):
    @slash(description="Kick a member", permissions=["kick_members"])
    async def kick(self, ctx, member):
        await member.kick(reason=f"Kicked by {ctx.user}")
        await ctx.respond(f"Kicked {member.display_name}.")

    @slash(description="Ban a member", permissions=["ban_members"])
    async def ban(self, ctx, member, reason: str = ""):
        await member.ban(reason=reason or None)
        await ctx.respond(f"Banned {member.display_name}.")


def build_bot():
    return Composer().add_groups(ModerationGroup()).build()


def main() -> None:
    run_bot(build_bot())


if __name__ == "__main__":
    main()
