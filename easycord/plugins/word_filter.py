"""Word filter plugin — block messages containing configured words/phrases."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord

from easycord import Plugin, on, slash
from easycord.helpers.channel import send_safe
from easycord.server_config import ServerConfigStore
from ._shared import GuildLockManager, respond_error

if TYPE_CHECKING:
    from easycord import Context

logger = logging.getLogger(__name__)


def _matches(content: str, words: list[str]) -> bool:
    """Return True if content (case-insensitive) contains any word from the list as a substring."""
    lower = content.lower()
    return any(w.lower() in lower for w in words)


def _is_exempt(member: discord.Member, exempt_role_id: int | None) -> bool:
    """Return True if member has the exempt role OR has manage_messages permission."""
    if member.guild_permissions.manage_messages:
        return True
    if exempt_role_id is None:
        return False
    return any(r.id == exempt_role_id for r in member.roles)


class WordFilterPlugin(Plugin):
    """Filter messages containing blocked words or phrases.

    Per-guild blocklists with configurable actions (delete, warn, or both).
    Moderators and a designated exempt role bypass filtering.

    Quick start::

        from easycord.plugins.word_filter import WordFilterPlugin
        bot.add_plugin(WordFilterPlugin())

    Commands registered::

        /filter_add    — Add a word/phrase to the guild blocklist
        /filter_remove — Remove a word/phrase from the blocklist
        /filter_list   — Show all blocked words
        /filter_action — Set action: "delete", "warn", or "both"
        /filter_exempt — Exempt a role from filtering
    """

    def __init__(self, *, store_path: str = ".easycord/word_filter") -> None:
        super().__init__()
        self._store = ServerConfigStore(store_path)
        self._locks = GuildLockManager()

    # ── Event handler ─────────────────────────────────────────

    @on("message")
    async def _on_message(self, message: discord.Message) -> None:
        if message.author.bot or message.guild is None:
            return
        cfg = await self._store.load(message.guild.id)
        data = cfg.get_other("word_filter", {})
        words = data.get("words", [])
        if not words:
            return
        exempt_role_id = data.get("exempt_role_id")
        if isinstance(message.author, discord.Member) and _is_exempt(message.author, exempt_role_id):
            return
        if not _matches(message.content, words):
            return
        action = data.get("action", "both")
        if action in ("delete", "both"):
            try:
                await message.delete()
            except discord.HTTPException:
                pass  # Message already deleted or insufficient permissions
        if action in ("warn", "both"):
            await send_safe(
                message.author,
                log=logger,
                what="word filter DM warning",
                content=f"⚠️ Your message in **{message.guild.name}** was removed for containing blocked content.",
            )

    # ── Slash commands ────────────────────────────────────────

    @slash(description="Add a word or phrase to the guild blocklist.", permissions=["manage_guild"])
    async def filter_add(self, ctx: "Context", word: str) -> None:
        if ctx.guild is None:
            await respond_error(ctx, "This command only works in a server.")
            return
        async with self._locks.lock(ctx.guild.id):
            cfg = await self._store.load(ctx.guild.id)
            data = cfg.get_other("word_filter", {})
            words: list[str] = data.get("words", [])
            if word.lower() not in [w.lower() for w in words]:
                words = [*words, word]
            data = {**data, "words": words}
            cfg.set_other("word_filter", data)
            await self._store.save(cfg)
        await ctx.respond(f"Added **{word}** to the blocklist.", ephemeral=True)

    @slash(description="Remove a word or phrase from the blocklist.", permissions=["manage_guild"])
    async def filter_remove(self, ctx: "Context", word: str) -> None:
        if ctx.guild is None:
            await respond_error(ctx, "This command only works in a server.")
            return
        removed = False
        async with self._locks.lock(ctx.guild.id):
            cfg = await self._store.load(ctx.guild.id)
            data = cfg.get_other("word_filter", {})
            words: list[str] = data.get("words", [])
            new_words = [w for w in words if w.lower() != word.lower()]
            removed = len(new_words) < len(words)
            data = {**data, "words": new_words}
            cfg.set_other("word_filter", data)
            await self._store.save(cfg)
        if not removed:
            await respond_error(ctx, f"**{word}** was not in the blocklist.")
        else:
            await ctx.respond(f"Removed **{word}** from the blocklist.", ephemeral=True)

    @slash(description="Show all blocked words for this server.", permissions=["manage_guild"])
    async def filter_list(self, ctx: "Context") -> None:
        if ctx.guild is None:
            await respond_error(ctx, "This command only works in a server.")
            return
        cfg = await self._store.load(ctx.guild.id)
        data = cfg.get_other("word_filter", {})
        words: list[str] = data.get("words", [])
        if not words:
            await respond_error(ctx, "No blocked words configured.")
            return
        word_list = "\n".join(f"• {w}" for w in words)
        await ctx.respond(f"**Blocked words:**\n{word_list}", ephemeral=True)

    @slash(description="Set the filter action: 'delete', 'warn', or 'both'.", permissions=["manage_guild"], bot_permissions=["manage_messages"])
    async def filter_action(self, ctx: "Context", action: str) -> None:
        if action not in ("delete", "warn", "both"):
            await respond_error(ctx, "Action must be 'delete', 'warn', or 'both'.")
            return
        if ctx.guild is None:
            await respond_error(ctx, "This command only works in a server.")
            return
        async with self._locks.lock(ctx.guild.id):
            cfg = await self._store.load(ctx.guild.id)
            data = cfg.get_other("word_filter", {})
            data = {**data, "action": action}
            cfg.set_other("word_filter", data)
            await self._store.save(cfg)
        await ctx.respond(f"Filter action set to **{action}**.", ephemeral=True)

    @slash(description="Exempt a role from word filtering.", permissions=["manage_guild"])
    async def filter_exempt(self, ctx: "Context", role: discord.Role) -> None:
        if ctx.guild is None:
            await respond_error(ctx, "This command only works in a server.")
            return
        async with self._locks.lock(ctx.guild.id):
            cfg = await self._store.load(ctx.guild.id)
            data = cfg.get_other("word_filter", {})
            data = {**data, "exempt_role_id": role.id}
            cfg.set_other("word_filter", data)
            await self._store.save(cfg)
        await ctx.respond(f"{role.mention} is now exempt from word filtering.", ephemeral=True)
