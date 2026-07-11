"""Member verification plugin — role-grant flow with optional challenge question."""
from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

import discord

from easycord import Plugin, slash
from easycord.helpers.channel import SENDABLE_CHANNEL_TYPES, send_safe
from easycord.server_config import ServerConfigStore

if TYPE_CHECKING:
    from easycord import Context

logger = logging.getLogger(__name__)


def _build_panel_embed(question: str | None) -> discord.Embed:
    """Build the verification panel embed. Include question if set."""
    description = (
        "Click the button below to verify your membership and gain access to the server."
    )
    if question:
        description += f"\n\n**You will be asked:** {question}"
    embed = discord.Embed(
        title="✅ Server Verification",
        description=description,
        color=discord.Color.green(),
    )
    embed.set_footer(text="Click the button to begin verification.")
    return embed


class _VerifyModal(discord.ui.Modal, title="Server Verification"):
    """Modal shown when the guild has a challenge question configured."""

    answer = discord.ui.TextInput(
        label="Your answer",
        min_length=1,
        max_length=500,
        placeholder="Type your answer here…",
    )

    def __init__(
        self,
        plugin: VerificationPlugin,
        guild_id: int,
        role_id: int,
    ) -> None:
        super().__init__()
        self._plugin = plugin
        self._guild_id = guild_id
        self._role_id = role_id

    async def on_submit(self, interaction: discord.Interaction) -> None:
        """Any non-empty answer grants the role."""
        guild = interaction.client.get_guild(self._guild_id)
        if guild is None:
            await interaction.response.send_message(
                "Server not found. Please contact an admin.", ephemeral=True
            )
            return

        role = guild.get_role(self._role_id)
        if role is None:
            await interaction.response.send_message(
                "Verification role not found. Please contact an admin.", ephemeral=True
            )
            return

        member = guild.get_member(interaction.user.id)
        if member is None:
            await interaction.response.send_message(
                "Could not find your membership. Please contact an admin.", ephemeral=True
            )
            return

        try:
            await member.add_roles(role, reason="VerificationPlugin: modal answer")
        except discord.Forbidden:
            logger.error("Missing permission to add verification role %s", role.id)
            await interaction.response.send_message(
                "Bot lacks permission to assign the role. Contact an admin.", ephemeral=True
            )
            return
        except discord.HTTPException as exc:
            logger.error("Failed to add verification role: %s", exc)
            await interaction.response.send_message(
                "An error occurred. Please try again.", ephemeral=True
            )
            return

        await interaction.response.send_message("✅ Verified!", ephemeral=True)


class _VerifyView(discord.ui.View):
    """Persistent verification panel view with a single Verify button."""

    def __init__(self, plugin: VerificationPlugin, guild_id: int) -> None:
        super().__init__(timeout=None)
        self._plugin = plugin
        self._guild_id = guild_id

        btn = discord.ui.Button(
            label="✅ Verify",
            style=discord.ButtonStyle.green,
            custom_id=f"verify:click:{guild_id}",
        )
        btn.callback = self._on_verify
        self.add_item(btn)

    async def _on_verify(self, interaction: discord.Interaction) -> None:
        """Handle verify button click."""
        cfg = await self._plugin._store.load(self._guild_id)
        data: dict = cfg.get_other("verification", {})
        role_id: int | None = data.get("role_id")
        question: str | None = data.get("question")

        if not role_id:
            await interaction.response.send_message(
                "Verification is not fully configured. Contact an admin.", ephemeral=True
            )
            return

        if question:
            modal = _VerifyModal(self._plugin, self._guild_id, role_id)
            await interaction.response.send_modal(modal)
            return

        # No question — grant role immediately
        guild = interaction.client.get_guild(self._guild_id)
        if guild is None:
            await interaction.response.send_message(
                "Server not found. Please contact an admin.", ephemeral=True
            )
            return

        role = guild.get_role(role_id)
        if role is None:
            await interaction.response.send_message(
                "Verification role not found. Please contact an admin.", ephemeral=True
            )
            return

        member = guild.get_member(interaction.user.id)
        if member is None:
            await interaction.response.send_message(
                "Could not find your membership. Please contact an admin.", ephemeral=True
            )
            return

        try:
            await member.add_roles(role, reason="VerificationPlugin: button click")
        except discord.Forbidden:
            logger.error("Missing permission to add verification role %s", role.id)
            await interaction.response.send_message(
                "Bot lacks permission to assign the role. Contact an admin.", ephemeral=True
            )
            return
        except discord.HTTPException as exc:
            logger.error("Failed to add verification role: %s", exc)
            await interaction.response.send_message(
                "An error occurred. Please try again.", ephemeral=True
            )
            return

        await interaction.response.send_message("✅ Verified!", ephemeral=True)


class VerificationPlugin(Plugin):
    """Gate server access behind a one-click (or one-question) verify flow.

    Admins configure a role and channel via ``/verification_setup``, then post
    a persistent panel with ``/verification_panel``. Optionally add a challenge
    question with ``/verification_question``. When a member clicks Verify they
    either receive the role immediately or are prompted to answer the question
    first; any non-empty answer is accepted.

    Quick start::

        from easycord.plugins.verification import VerificationPlugin
        bot.add_plugin(VerificationPlugin())

    Slash commands registered
    -------------------------
    ``/verification_setup``    — Set role + channel (manage_guild).
    ``/verification_panel``    — Post the panel in the configured channel.
    ``/verification_question`` — Set or clear an optional challenge question.
    """

    def __init__(self, *, store_path: str = ".easycord/verification") -> None:
        super().__init__()
        self._store = ServerConfigStore(store_path)
        self._locks: dict[int, asyncio.Lock] = {}

    def _guild_lock(self, guild_id: int) -> asyncio.Lock:
        if guild_id not in self._locks:
            self._locks[guild_id] = asyncio.Lock()
        return self._locks[guild_id]

    async def on_ready(self) -> None:
        """Re-register persistent verify views for all configured guilds."""
        store_base = self._store._base
        if not store_base.exists():
            return
        for path in store_base.glob("*.json"):
            try:
                guild_id = int(path.stem)
            except ValueError:
                continue
            cfg = await self._store.load(guild_id)
            data: dict = cfg.get_other("verification", {})
            panel_message_id: int | None = data.get("panel_message_id")
            if panel_message_id is None:
                continue
            view = _VerifyView(self, guild_id)
            try:
                self.bot.add_view(view, message_id=panel_message_id)
            except Exception:
                logger.warning(
                    "Failed to re-register verify view for guild %s / message %s",
                    guild_id,
                    panel_message_id,
                )

    @slash(description="Set the verified role and channel for the verification panel.", guild_only=True)
    async def verification_setup(
        self,
        ctx: Context,
        role: discord.Role,
        channel: discord.TextChannel,
    ) -> None:
        """Configure role to grant and channel to post the panel in.

        Parameters
        ----------
        role:
            The role members receive after verifying.
        channel:
            The channel where the verification panel will be posted.
        """
        if ctx.guild is None:
            await ctx.respond("This command can only be used in a server.", ephemeral=True)
            return
        if not ctx.is_admin:
            await ctx.respond("You need the Administrator permission to use this command.", ephemeral=True)
            return

        guild_id = ctx.guild.id
        async with self._guild_lock(guild_id):
            cfg = await self._store.load(guild_id)
            data: dict = cfg.get_other("verification", {})
            data["role_id"] = role.id
            data["channel_id"] = channel.id
            cfg.set_other("verification", data)
            await self._store.save(cfg)

        await ctx.respond(
            f"✅ Verification configured: role **{role.name}**, channel {channel.mention}.",
            ephemeral=True,
        )

    @slash(description="Post the verification panel in the configured channel.", guild_only=True)
    async def verification_panel(self, ctx: Context) -> None:
        """Post a persistent embed with a Verify button in the configured channel."""
        if ctx.guild is None:
            await ctx.respond("This command can only be used in a server.", ephemeral=True)
            return
        if not ctx.is_admin:
            await ctx.respond("You need the Administrator permission to use this command.", ephemeral=True)
            return

        guild_id = ctx.guild.id
        cfg = await self._store.load(guild_id)
        data: dict = cfg.get_other("verification", {})
        role_id: int | None = data.get("role_id")
        channel_id: int | None = data.get("channel_id")

        if not role_id or not channel_id:
            await ctx.respond(
                "Verification is not configured. Run `/verification_setup` first.",
                ephemeral=True,
            )
            return

        channel = ctx.guild.get_channel(channel_id)
        if not isinstance(channel, SENDABLE_CHANNEL_TYPES):
            await ctx.respond(
                "The configured channel was not found. Run `/verification_setup` again.",
                ephemeral=True,
            )
            return

        question: str | None = data.get("question")
        embed = _build_panel_embed(question)
        view = _VerifyView(self, guild_id)
        # The panel goes to the *configured* channel, not the invocation
        # channel, so a decorator-level bot_permissions preflight can't cover
        # it — the send itself must be guarded.
        message = await send_safe(
            channel, log=logger, what="verification panel", embed=embed, view=view
        )
        if message is None:
            await ctx.respond(
                f"❌ I couldn't post the panel in {channel.mention}. "
                "Check my permissions there and try again.",
                ephemeral=True,
            )
            return
        self.bot.add_view(view, message_id=message.id)

        async with self._guild_lock(guild_id):
            cfg = await self._store.load(guild_id)
            data = cfg.get_other("verification", {})
            data["panel_message_id"] = message.id
            cfg.set_other("verification", data)
            await self._store.save(cfg)

        await ctx.respond(
            f"✅ Verification panel posted in {channel.mention}.", ephemeral=True
        )

    @slash(description="Set an optional challenge question for the verification flow.", guild_only=True)
    async def verification_question(self, ctx: Context, text: str) -> None:
        """Set a challenge question members must answer before receiving the role.

        Parameters
        ----------
        text:
            The question text. Pass an empty string to clear the question.
        """
        if ctx.guild is None:
            await ctx.respond("This command can only be used in a server.", ephemeral=True)
            return
        if not ctx.is_admin:
            await ctx.respond("You need the Administrator permission to use this command.", ephemeral=True)
            return

        guild_id = ctx.guild.id
        question: str | None = text.strip() or None

        async with self._guild_lock(guild_id):
            cfg = await self._store.load(guild_id)
            data: dict = cfg.get_other("verification", {})
            data["question"] = question
            cfg.set_other("verification", data)
            await self._store.save(cfg)

        if question:
            await ctx.respond(f"✅ Verification question set: *{question}*", ephemeral=True)
        else:
            await ctx.respond("✅ Verification question cleared.", ephemeral=True)
