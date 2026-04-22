from easycord import Plugin, on, slash


def _announcement_footer(user) -> str:
    return f"Posted by {user.display_name}"


def _welcome_message(member) -> str:
    return (
        f"👋 Welcome to **{member.guild.name}**, {member.name}!\n"
        "Feel free to introduce yourself."
    )


class ModerationPlugin(Plugin):
    """Server moderation helpers."""

    async def on_load(self):
        print(f"[ModerationPlugin] Loaded — connected to {self.bot.user}")

    @slash(description="Announce a message to this channel.", guild_only=True)
    async def announce(self, ctx, message: str):
        import discord
        await ctx.send_embed(
            "📢 Announcement",
            message,
            color=discord.Color.gold(),
            footer=_announcement_footer(ctx.user),
        )

    @on("member_join")
    async def greet_member(self, member):
        """DM new members a welcome message."""
        try:
            await member.send(_welcome_message(member))
        except Exception:
            pass
