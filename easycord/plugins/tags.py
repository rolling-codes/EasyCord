"""Per-guild text snippet storage and slash commands."""
from __future__ import annotations

import asyncio
from pathlib import Path

from easycord.decorators import slash
from easycord.plugin import Plugin
from ._shared import read_json_file, write_json_file


class TagsStore:
    """Handles atomic per-guild tag JSON storage with concurrent write safety."""

    def __init__(self, data_dir: str) -> None:
        self._data_dir = Path(data_dir)
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._locks: dict[int, asyncio.Lock] = {}

    def _get_lock(self, guild_id: int) -> asyncio.Lock:
        """Get or create asyncio.Lock for this guild (thread-safe in single-threaded asyncio)."""
        if guild_id not in self._locks:
            self._locks[guild_id] = asyncio.Lock()
        return self._locks[guild_id]

    def _path(self, guild_id: int) -> Path:
        return self._data_dir / f"tags_{guild_id}.json"

    def _load(self, guild_id: int) -> dict[str, dict]:
        return read_json_file(self._path(guild_id))

    def _save(self, guild_id: int, data: dict[str, dict]) -> None:
        write_json_file(self._path(guild_id), data)

    def get(self, guild_id: int, name: str) -> dict | None:
        return self._load(guild_id).get(name)

    async def set(self, guild_id: int, name: str, text: str, *, author_id: int) -> None:
        async with self._get_lock(guild_id):
            data = self._load(guild_id)
            data[name] = {"text": text, "author_id": author_id}
            self._save(guild_id, data)

    async def delete(self, guild_id: int, name: str) -> None:
        async with self._get_lock(guild_id):
            data = self._load(guild_id)
            if name in data:
                del data[name]
                self._save(guild_id, data)

    async def delete_if_authorized(self, guild_id: int, name: str, user_id: int, is_admin: bool) -> tuple[bool, str]:
        """Delete tag if user is owner or admin. Return (success, reason). Atomic under lock."""
        async with self._get_lock(guild_id):
            data = self._load(guild_id)
            entry = data.get(name)
            if entry is None:
                return False, "not_found"
            if user_id != entry["author_id"] and not is_admin:
                return False, "unauthorized"
            del data[name]
            self._save(guild_id, data)
            return True, "deleted"

    def list_names(self, guild_id: int) -> list[str]:
        return sorted(self._load(guild_id).keys())


class TagsPlugin(Plugin):
    """Slash-command tag store. Adds ``/tag get``, ``/tag set``, ``/tag delete``, ``/tag list``."""

    def __init__(self, *, data_dir: str = "tags_data") -> None:
        super().__init__()
        self._store = TagsStore(data_dir)

    @slash(description="Retrieve a tag by name.", guild_only=True)
    async def get(self, ctx, name: str) -> None:
        entry = self._store.get(ctx.guild_id, name)
        if entry is None:
            await ctx.respond(ctx.t("tags.not_found", default="Tag `{name}` not found.", name=name), ephemeral=True)
            return
        await ctx.respond(entry["text"])

    @slash(description="Create or update a tag.", guild_only=True)
    async def set(self, ctx, name: str, text: str) -> None:
        await self._store.set(ctx.guild_id, name, text, author_id=ctx.user.id)
        await ctx.respond(ctx.t("tags.saved", default="Tag `{name}` saved.", name=name), ephemeral=True)

    @slash(description="Delete a tag (admin or creator only).", guild_only=True)
    async def delete(self, ctx, name: str) -> None:
        success, reason = await self._store.delete_if_authorized(ctx.guild_id, name, ctx.user.id, ctx.is_admin)
        if not success:
            if reason == "not_found":
                msg = ctx.t("tags.not_found", default="Tag `{name}` not found.", name=name)
            else:  # unauthorized
                msg = ctx.t("tags.cannot_delete", default="You can only delete your own tags (or be an admin).")
            await ctx.respond(msg, ephemeral=True)
        else:
            await ctx.respond(ctx.t("tags.deleted", default="Tag `{name}` deleted.", name=name), ephemeral=True)

    @slash(description="List all tags in this server.", guild_only=True)
    async def list(self, ctx) -> None:
        names = self._store.list_names(ctx.guild_id)
        if not names:
            await ctx.respond(ctx.t("tags.empty", default="No tags yet."), ephemeral=True)
            return
        
        header = ctx.t("tags.header", default="**Tags in this server:**")
        await ctx.paginate([f"{header}\n" + "\n".join(names[i:i+20]) for i in range(0, len(names), 20)], ephemeral=True)
