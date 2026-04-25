"""Complete example bot using all v3.7.0 features and helpers."""
import os
import discord
from easycord import Bot, Plugin, slash, on
from easycord.plugins import (
    ModerationPlugin,
    ReactionRolesPlugin,
    AutoResponderPlugin,
    StarboardPlugin,
    MemberLoggingPlugin,
)
from easycord.helpers import (
    EmbedBuilder,
    ContextHelpers,
    ConfigHelpers,
    RateLimitHelpers,
)
from easycord.tool_limits import RateLimit


class ExamplePlugin(Plugin):
    """Showcase decorator enhancements and helper usage."""

    async def on_load(self):
        """Setup when plugin loads."""
        print(f"ExamplePlugin loaded")

    async def on_ready(self):
        """Called every time bot becomes ready."""
        print(f"ExamplePlugin ready (bot: {self.bot.user})")

    async def on_unload(self):
        """Cleanup when plugin unloads."""
        print("ExamplePlugin unloading")

    # Decorator with rate limit (new in v3.7.0)
    @slash(
        description="Get server stats",
        ephemeral=True,
        rate_limit=(5, 60),  # Max 5 calls per minute
    )
    async def stats(self, ctx):
        """Show server statistics."""
        members = ContextHelpers.list_members(ctx)
        embed = (
            EmbedBuilder("Server Stats")
            .add_field("Total Members", str(len(members)))
            .add_field("Server Created", ctx.guild.created_at.strftime("%Y-%m-%d"))
            .set_color(discord.Color.blue())
            .build()
        )
        await ctx.respond(embed=embed)

    @slash(
        description="Send a welcome message",
        permissions=["manage_messages"],
    )
    async def welcome_setup(self, ctx):
        """Setup welcome responses."""
        await ContextHelpers.respond_success(
            ctx,
            "Welcome Setup",
            "Auto-responses configured. Users will see help text on join.",
        )

    # Event handler with cleanup callback (new in v3.7.0)
    async def cleanup_on_message(self):
        """Cleanup for message handler (would close connections, etc.)."""
        print("Message handler cleanup")

    @on("message", on_cleanup=cleanup_on_message)
    async def on_message(self, message):
        """Handle messages - echo 'ping' with a pong."""
        if message.author == self.bot.user:
            return
        if message.content.lower() == "ping":
            await message.reply("pong!")

    @slash(description="Paginate through members", guild_only=True)
    async def members(self, ctx):
        """Show paginated member list."""
        members = ContextHelpers.list_members(ctx)
        member_names = [m.display_name for m in members]

        pages = ContextHelpers.paginate_list(member_names, per_page=10)
        await ContextHelpers.send_paginated(
            ctx,
            pages,
            template="Members",
            item_format="• {}",
        )


def main():
    """Run the example bot."""
    # Create bot
    bot = Bot()

    # Add plugins with chaining (new in v3.7.0 - add_plugin returns bot for chaining)
    (
        bot
        .add_plugin(ModerationPlugin())
        .add_plugin(ReactionRolesPlugin())
        .add_plugin(AutoResponderPlugin())
        .add_plugin(StarboardPlugin())
        .add_plugin(MemberLoggingPlugin())
        .add_plugin(ExamplePlugin())
    )

    # Start bot
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise ValueError("DISCORD_TOKEN not set in environment")
    bot.run(token)


if __name__ == "__main__":
    main()
