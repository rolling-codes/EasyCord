from easycord import Plugin, on, slash


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
            footer=f"Posted by {ctx.user.display_name}",
        )

    @on("member_join")
    async def greet_member(self, member):
        """DM new members a welcome message."""
        try:
            await member.send(
                f"👋 Welcome to **{member.guild.name}**, {member.name}!\n"
                "Feel free to introduce yourself."
            )
        except Exception:
            pass  # DMs may be disabled
