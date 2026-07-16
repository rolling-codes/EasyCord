"""Juice WRLD song metadata finder plugin for EasyCord.

Provides slash commands, AI tools, and per-guild configuration for the
Juice WRLD song catalog stored in a SQLite or PostgreSQL database.

Quick start::

    from easycord.plugins.juicewrld import JuiceWRLDPlugin
    bot.add_plugin(JuiceWRLDPlugin(database_url="sqlite:///./juice_wrld.db"))

Commands registered::

    /jw_search  — Search songs by title or alias
    /jw_song    — Full details for a song by ID
    /jw_era     — List songs from a specific era
    /jw_random  — Get a random song from the catalog
    /jw_add_song  — (Admin) Add a new song
    /jw_reindex   — (Admin) Reindex MEGA folders

AI tools registered::

    search_juicewrld  — AI-callable catalog search
    get_song_details  — AI-callable song lookup by ID
"""
from __future__ import annotations

import asyncio
import logging
from contextlib import contextmanager
from typing import TYPE_CHECKING, Generator

import discord
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from easycord import Plugin, on, slash, task
from easycord.decorators import ai_tool, describe, subscribe
from easycord.server_config import ServerConfigStore

# Juice WRLD finder service layer — install the juice-wrld-finder package alongside EasyCord.
# None of these modules import app.core.config.settings at import time.
from app.core.security import redact_private_urls
from app.models.song import Era, Song
from app.repositories.song_repo import SongRepository
from app.services.search_service import SearchService
from app.services.song_service import SongService

if TYPE_CHECKING:
    from easycord import Context

logger = logging.getLogger(__name__)


class JuiceWRLDPlugin(Plugin):
    """Juice WRLD song metadata finder.

    Integrates the full juice-wrld-finder service layer into EasyCord as a
    first-class plugin.  All slash commands, AI tools, and per-guild config
    are wired through the standard EasyCord plugin lifecycle.

    Parameters
    ----------
    database_url:
        SQLAlchemy database URL — e.g. ``"sqlite:///./juice_wrld.db"`` or a
        ``postgresql://`` URL.  The plugin creates its own engine so it does
        not depend on the juice-wrld-finder environment variables.
    expose_api_download_links:
        When ``True``, ``/jw_song`` shows the ``api_download_url`` field.
        Defaults to ``False``.
    expose_mega_links:
        When ``True``, MEGA links are not redacted from embed fields.
        Defaults to ``False``.
    api_base_url:
        Base URL for the Juice WRLD external API.  When supplied, the plugin
        runs a background sync every 6 hours.  Omit to disable background sync.
    store_path:
        Directory for per-guild ServerConfigStore JSON files.
        Defaults to ``".easycord/juicewrld"``.
    """

    name = "juicewrld"
    version = "1.3.0"
    author = "rolling-codes"
    description = "Juice WRLD song catalog — search, lookup, and admin management."

    def __init__(
        self,
        *,
        database_url: str,
        expose_api_download_links: bool = False,
        expose_mega_links: bool = False,
        api_base_url: str = "",
        store_path: str = ".easycord/juicewrld",
    ) -> None:
        super().__init__()

        connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
        engine = create_engine(database_url, connect_args=connect_args)
        self._SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

        self._expose_api_download_links = expose_api_download_links
        self._expose_mega_links = expose_mega_links
        self._api_base_url = api_base_url

        self._store = ServerConfigStore(store_path)
        self._locks: dict[int, asyncio.Lock] = {}

    # ── Internal helpers ───────────────────────────────────────

    def _guild_lock(self, guild_id: int) -> asyncio.Lock:
        if guild_id not in self._locks:
            self._locks[guild_id] = asyncio.Lock()
        return self._locks[guild_id]

    @contextmanager
    def _db(self) -> Generator[Session, None, None]:
        """Yield a database session with automatic rollback on error."""
        session = self._SessionLocal()
        try:
            yield session
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def _redact_embed(self, embed: discord.Embed) -> discord.Embed:
        """Redact MEGA / private-file URLs from every field of an embed."""
        if self._expose_mega_links:
            return embed
        if embed.title:
            embed.title = redact_private_urls(embed.title)
        if embed.description:
            embed.description = redact_private_urls(embed.description)
        for i, field in enumerate(embed.fields):
            embed.set_field_at(
                i,
                name=redact_private_urls(field.name),
                value=redact_private_urls(field.value),
                inline=field.inline,
            )
        return embed

    @staticmethod
    def _safe_url(url: str | None) -> str | None:
        """Return url only if it starts with http:// or https://, else None."""
        if url and url.lower().startswith(("http://", "https://")):
            return url
        return None

    # ── Lifecycle ──────────────────────────────────────────────

    @on("ready")
    async def _on_ready(self) -> None:
        try:
            with self._db() as db:
                count = db.query(Song).count()
            logger.info("JuiceWRLDPlugin ready — %d songs in catalog", count)
        except Exception as exc:
            logger.error("JuiceWRLDPlugin: database check failed on ready: %s", exc)

    # ── Event bus subscriptions ────────────────────────────────

    @subscribe("juicewrld.song_added")
    async def _on_song_added(
        self,
        song_id: int,
        title: str,
        era: str | None,
        guild_id: int | None,
        user_id: int,
    ) -> None:
        """React to a new song being added — MEGA index is now stale."""
        logger.info(
            "Catalog updated: [%d] %s (era=%s, guild=%s, added_by=%s) — MEGA index may be stale",
            song_id, title, era, guild_id, user_id,
        )

    @subscribe("juicewrld.api_synced")
    async def _on_api_synced(self, added: int) -> None:
        """Log catalog size after a background API sync."""
        try:
            with self._db() as db:
                total = db.query(Song).count()
            logger.info("API sync: +%d song(s), catalog now at %d total", added, total)
        except Exception as exc:
            logger.error("_on_api_synced: %s", exc)

    @subscribe("juicewrld.reindexed")
    async def _on_reindexed(
        self,
        stats: dict,
        guild_id: int | None,
        user_id: int,
    ) -> None:
        """Log MEGA reindex completion stats."""
        logger.info(
            "MEGA reindex complete (guild=%s, triggered_by=%s): indexed=%s matched=%s errors=%s",
            guild_id, user_id, stats.get("indexed"), stats.get("matched"), stats.get("errors"),
        )

    # ── Background task (optional API sync) ───────────────────

    @task(hours=6)
    async def _api_sync(self) -> None:
        """Sync new song metadata from the Juice WRLD API every 6 hours."""
        if not self._api_base_url:
            return
        try:
            from app.integrations.juicewrld_api import JuicewrldAPIClient  # lazy — needs httpx
            async with JuicewrldAPIClient(base_url=self._api_base_url) as client:
                remote_songs = await client.get_songs()
            with self._db() as db:
                repo = SongRepository(db)
                service = SongService(db)
                existing_titles = {s.title.lower() for s in db.query(Song.title).all()}
                added = 0
                for s in remote_songs:
                    if s.get("title", "").lower() not in existing_titles:
                        service.create_song(
                            title=s["title"],
                            release_status=s.get("release_status", "unknown"),
                        )
                        added += 1
            if added:
                logger.info("JuiceWRLDPlugin: synced %d new song(s) from API", added)
                await self.bot.event_bus.publish("juicewrld.api_synced", added=added)
        except Exception as exc:
            logger.error("JuiceWRLDPlugin: API sync failed: %s", exc)

    # ── Search commands ────────────────────────────────────────

    @slash(description="Search for a Juice WRLD song by title or alias.", cooldown=3)
    @describe(query="Song title, alias, or partial name")
    async def jw_search(self, ctx: "Context", query: str) -> None:
        """Full-text + fuzzy search across the catalog."""
        try:
            with self._db() as db:
                service = SearchService(db)
                results = service.search(query, limit=10)
        except Exception as exc:
            logger.error("jw_search: %s", exc)
            await ctx.respond("Search failed — please try again.", ephemeral=True)
            return

        if not results:
            await ctx.respond(f"No songs found matching `{query}`.", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"Results for `{query}`",
            description=f"{len(results)} match(es) — use `/jw_song <id>` for full details",
            color=discord.Color.green(),
        )
        for r in results:
            song = r.song
            embed.add_field(
                name=f"{song.title}  ({r.confidence:.0f}%)",
                value=f"{song.release_status}  •  ID `{song.id}`",
                inline=False,
            )
        await ctx.respond(embed=self._redact_embed(embed))
        await self.bot.event_bus.publish(
            "juicewrld.searched",
            query=query,
            result_count=len(results),
            guild_id=ctx.guild.id if ctx.guild else None,
            user_id=ctx.user.id,
        )

    @slash(description="Get full details for a Juice WRLD song by ID.", cooldown=3)
    @describe(song_id="Numeric song ID — find it with /jw_search")
    async def jw_song(self, ctx: "Context", song_id: int) -> None:
        """Retrieve every stored field for a single song."""
        try:
            with self._db() as db:
                repo = SongRepository(db)
                song = repo.get_by_id(song_id)
                versions = repo.get_versions(song_id) if song else []
                refs = repo.get_references(song_id) if song else []
        except Exception as exc:
            logger.error("jw_song: %s", exc)
            await ctx.respond("Failed to fetch song details.", ephemeral=True)
            return

        if not song:
            await ctx.respond(f"No song found with ID `{song_id}`.", ephemeral=True)
            return

        embed = discord.Embed(title=song.title, color=discord.Color.blue())
        embed.add_field(name="Status", value=song.release_status or "—", inline=True)
        embed.add_field(name="Download", value=song.download_status or "—", inline=True)
        if song.era:
            embed.add_field(name="Era", value=song.era.name, inline=True)
        safe_official = self._safe_url(song.official_url)
        if safe_official:
            embed.add_field(name="Official Link", value=f"[Listen]({safe_official})", inline=False)
        safe_api = self._safe_url(getattr(song, "api_download_url", None))
        if self._expose_api_download_links and safe_api:
            embed.add_field(name="API Download", value=f"[Available]({safe_api})", inline=False)
        if song.aliases:
            embed.add_field(name="Aliases", value=", ".join(a.alias for a in song.aliases), inline=False)
        if versions:
            v_lines = "\n".join(f"• {v.title} ({v.version_type})" for v in versions[:5])
            embed.add_field(name=f"Versions ({len(versions)})", value=v_lines, inline=False)
        if refs:
            r_lines = "\n".join(
                f"• [{r.source_name}]({self._safe_url(r.source_url)})"
                if self._safe_url(r.source_url) else f"• {r.source_name}"
                for r in refs[:5]
            )
            embed.add_field(name=f"References ({len(refs)})", value=r_lines, inline=False)
        if song.notes:
            embed.add_field(name="Notes", value=redact_private_urls(song.notes)[:1024], inline=False)

        await ctx.respond(embed=self._redact_embed(embed))
        await self.bot.event_bus.publish(
            "juicewrld.song_viewed",
            song_id=song.id,
            title=song.title,
            guild_id=ctx.guild.id if ctx.guild else None,
            user_id=ctx.user.id,
        )

    @slash(description="List songs from a Juice WRLD era.", cooldown=3)
    @describe(era_name="Era name — partial match is fine")
    async def jw_era(self, ctx: "Context", era_name: str) -> None:
        """Return up to 20 songs from the named era."""
        try:
            with self._db() as db:
                era = db.query(Era).filter(Era.name.ilike(f"%{era_name}%")).first()
                if not era:
                    await ctx.respond(f"Era `{era_name}` not found.", ephemeral=True)
                    return
                repo = SongRepository(db)
                songs = repo.get_by_era_id(era.id, limit=20)
        except Exception as exc:
            logger.error("jw_era: %s", exc)
            await ctx.respond("Era lookup failed.", ephemeral=True)
            return

        if not songs:
            await ctx.respond(f"No songs in era `{era.name}`.", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"{era.name} Era",
            description=f"{len(songs)} song(s) — use `/jw_song <id>` for details",
            color=discord.Color.purple(),
        )
        for song in songs:
            embed.add_field(name=song.title, value=song.release_status or "—", inline=True)
        await ctx.respond(embed=self._redact_embed(embed))
        await self.bot.event_bus.publish(
            "juicewrld.era_browsed",
            era_name=era.name,
            result_count=len(songs),
            guild_id=ctx.guild.id if ctx.guild else None,
            user_id=ctx.user.id,
        )

    @slash(description="Get a random Juice WRLD song from the catalog.", cooldown=3)
    async def jw_random(self, ctx: "Context") -> None:
        """Pick a random song using DB-level RANDOM()."""
        try:
            with self._db() as db:
                service = SearchService(db)
                song = service.get_random_song()
        except Exception as exc:
            logger.error("jw_random: %s", exc)
            await ctx.respond("Failed to get a random song.", ephemeral=True)
            return

        if not song:
            await ctx.respond("No songs in the catalog yet.", ephemeral=True)
            return

        embed = discord.Embed(title=f"🎲 {song.title}", color=discord.Color.gold())
        embed.add_field(name="Status", value=song.release_status or "—", inline=True)
        embed.add_field(name="Download", value=song.download_status or "—", inline=True)
        if song.era:
            embed.add_field(name="Era", value=song.era.name, inline=True)
        embed.set_footer(text=f"ID {song.id}  •  /jw_song {song.id} for full details")
        await ctx.respond(embed=self._redact_embed(embed))
        await self.bot.event_bus.publish(
            "juicewrld.random_played",
            song_id=song.id,
            title=song.title,
            guild_id=ctx.guild.id if ctx.guild else None,
            user_id=ctx.user.id,
        )

    # ── Admin commands ─────────────────────────────────────────

    @slash(description="Add a new song to the catalog. (Admin only)", require_admin=True, ephemeral=True)
    @describe(
        title="Song title",
        era="Era name — created automatically if it does not exist",
        release_status="released / unreleased / unknown",
    )
    async def jw_add_song(
        self,
        ctx: "Context",
        title: str,
        era: str = "",
        release_status: str = "unknown",
    ) -> None:
        """Create a song record, optionally linking it to an era."""
        try:
            with self._db() as db:
                service = SongService(db)
                song = service.create_song(
                    title=title,
                    era_name=era or None,
                    release_status=release_status,
                )
        except Exception as exc:
            logger.error("jw_add_song: %s", exc)
            await ctx.respond("Failed to add song — check logs for details.", ephemeral=True)
            return

        await ctx.respond(
            f"✓ Added **{song.title}** (ID `{song.id}`, slug `{song.slug}`)",
            ephemeral=True,
        )
        await self.bot.event_bus.publish(
            "juicewrld.song_added",
            song_id=song.id,
            title=song.title,
            era=era or None,
            guild_id=ctx.guild.id if ctx.guild else None,
            user_id=ctx.user.id,
        )

    @slash(description="Reindex MEGA folders against the song catalog. (Admin only)", require_admin=True, ephemeral=True)
    async def jw_reindex(self, ctx: "Context") -> None:
        """Run the MEGA indexer — links MEGA files to existing song records."""
        try:
            from app.integrations.mega_indexer import MEGAIndexer  # lazy: needs mega.py + credentials
            with self._db() as db:
                indexer = MEGAIndexer(db)
                stats = indexer.index_folders()
        except ImportError:
            await ctx.respond(
                "MEGA indexer unavailable — install `mega.py` and set MEGA credentials.",
                ephemeral=True,
            )
            return
        except Exception as exc:
            logger.error("jw_reindex: %s", exc)
            await ctx.respond("Reindex failed — check logs for details.", ephemeral=True)
            return

        await ctx.respond(
            f"✓ Reindex complete — "
            f"indexed **{stats['indexed']}**, matched **{stats['matched']}**, "
            f"errors **{stats['errors']}**.",
            ephemeral=True,
        )
        await self.bot.event_bus.publish(
            "juicewrld.reindexed",
            stats=stats,
            guild_id=ctx.guild.id if ctx.guild else None,
            user_id=ctx.user.id,
        )

    # ── AI tools ───────────────────────────────────────────────

    @ai_tool(
        description=(
            "Search the Juice WRLD song catalog by title or alias. "
            "Returns up to 5 matching songs with confidence scores and IDs. "
            "Use get_song_details to fetch full metadata for a specific song."
        ),
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Song title, alias, or partial name to search for",
                },
            },
            "required": ["query"],
        },
    )
    async def search_juicewrld(self, ctx: "Context", query: str) -> str:
        try:
            with self._db() as db:
                results = SearchService(db).search(query, limit=5)
        except Exception as exc:
            logger.error("search_juicewrld tool: %s", exc)
            return "Search failed."
        if not results:
            return f"No songs found matching '{query}'."
        lines = [f"Found {len(results)} result(s) for '{query}':"]
        for r in results:
            s = r.song
            lines.append(f"  [{s.id}] {s.title} — {s.release_status} ({r.confidence:.0f}% confidence)")
        return "\n".join(lines)

    @ai_tool(
        description=(
            "Fetch full metadata for a Juice WRLD song by its numeric ID. "
            "Use search_juicewrld first to find the ID."
        ),
        parameters={
            "type": "object",
            "properties": {
                "song_id": {
                    "type": "integer",
                    "description": "Numeric song ID from the catalog",
                },
            },
            "required": ["song_id"],
        },
    )
    async def get_song_details(self, ctx: "Context", song_id: int) -> str:
        try:
            with self._db() as db:
                repo = SongRepository(db)
                song = repo.get_by_id(song_id)
        except Exception as exc:
            logger.error("get_song_details tool: %s", exc)
            return "Failed to fetch song."
        if not song:
            return f"No song found with ID {song_id}."
        parts = [f"{song.title} (ID {song.id})"]
        parts.append(f"Status: {song.release_status} | Download: {song.download_status}")
        if song.era:
            parts.append(f"Era: {song.era.name}")
        if song.aliases:
            parts.append(f"Aliases: {', '.join(a.alias for a in song.aliases)}")
        if song.official_url:
            parts.append(f"Official URL: {song.official_url}")
        if song.notes:
            parts.append(f"Notes: {redact_private_urls(song.notes)}")
        return "\n".join(parts)
