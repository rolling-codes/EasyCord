import discord

from easycord import Plugin, slash


def _channel_fields(channel: discord.TextChannel) -> list[tuple[str, str]]:
    fields = [
        ("ID", str(channel.id)),
        ("Category", channel.category.name if channel.category else "None"),
        ("Slowmode", f"{channel.slowmode_delay}s"),
        ("NSFW", "Yes" if channel.is_nsfw() else "No"),
    ]
    if channel.topic:
        fields.append(("Topic", channel.topic))
    return fields


def _role_fields(role: discord.Role) -> list[tuple[str, str]]:
    return [
        ("ID", str(role.id)),
        ("Color", str(role.color)),
        ("Hoisted", "Yes" if role.hoist else "No"),
        ("Mentionable", "Yes" if role.mentionable else "No"),
        ("Members", str(len(role.members))),
        ("Position", str(role.position)),
    ]


class InfoPlugin(Plugin):
    """Informational commands."""

    @slash(description="Display server information.", guild_only=True)
    async def serverinfo(self, ctx):
        guild = ctx.guild
        await ctx.send_embed(
            f"ℹ️ {guild.name}",
            color=discord.Color.blurple(),
            fields=[
                ("Members", guild.member_count),
                ("Owner", str(guild.owner)),
                ("Created", guild.created_at.strftime("%Y-%m-%d")),
            ],
        )

    @slash(description="Show your profile info.")
    async def me(self, ctx):
        user = ctx.user
        await ctx.send_embed(
            title=f"👤 {user.display_name}",
            description=f"**ID:** `{user.id}`\n**Bot:** {user.bot}",
        )

    @slash(description="Show information about a specific role.", guild_only=True)
    async def roleinfo(self, ctx, role: discord.Role):
        await ctx.send_embed(
            f"🏷️ Role: {role.name}",
            color=role.color,
            fields=_role_fields(role),
        )

    @slash(description="Show information about this channel.")
    async def channelinfo(self, ctx):
        channel = ctx.channel
        if not isinstance(channel, discord.TextChannel):
            await ctx.respond("This command only works in a text channel.", ephemeral=True)
            return
        await ctx.send_embed(f"#️⃣ #{channel.name}", color=discord.Color.blurple(), fields=_channel_fields(channel))

    @slash(description="Show the bot's latency.")
    async def ping(self, ctx):
        latency_ms = round(self.bot.latency * 1000)
        await ctx.respond(f"🏓 Pong! Latency: **{latency_ms}ms**")

    @slash(description="Show the top roles in this server.", guild_only=True)
    async def roles(self, ctx):
        sorted_roles = sorted(ctx.guild.roles[1:], key=lambda role: role.position, reverse=True)[:15]
        lines = [
            f"{role.mention} — {len(role.members)} member{'s' if len(role.members) != 1 else ''}"
            for role in sorted_roles
        ]
        await ctx.send_embed(
            f"🏅 Roles in {ctx.guild.name}",
            "\n".join(lines) or "No roles.",
            color=discord.Color.blurple(),
        )
