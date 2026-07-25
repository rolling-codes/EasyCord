"""Juice WRLD song metadata finder — EasyCord plugin.

This module was previously the standalone ``juice-wrld-finder`` project.  It is
now shipped as a built-in EasyCord plugin so the Discord bot, catalog database,
and web API all live in one place.

Quick start
-----------
::

    from easycord.plugins.juicewrld import JuiceWRLDPlugin

    bot.add_plugin(JuiceWRLDPlugin(
        database_url="sqlite:///./juice_wrld.db",
        mega_folder_url="https://mega.nz/folder/XXXXXXXX#YYYYYYYY",
        expose_mega_links=True,
    ))

Slash commands
--------------
+----------------+----------+----------------------------------------------+
| Command        | Access   | Description                                  |
+================+==========+==============================================+
| /jw_search     | Everyone | Fuzzy search by title or alias               |
+----------------+----------+----------------------------------------------+
| /jw_song       | Everyone | Full metadata for a song by ID               |
+----------------+----------+----------------------------------------------+
| /jw_era        | Everyone | List songs from a named era                  |
+----------------+----------+----------------------------------------------+
| /jw_random     | Everyone | Random song from the catalog                 |
+----------------+----------+----------------------------------------------+
| /jw_add_song   | Admin    | Add a new song; auto-creates era if needed   |
+----------------+----------+----------------------------------------------+
| /jw_reindex    | Admin    | Reindex configured MEGA folders              |
+----------------+----------+----------------------------------------------+

AI tools
--------
``search_juicewrld``
    AI-callable fuzzy catalog search.  Returns up to 5 results with
    confidence scores.  Use ``get_song_details`` to drill into a result.

``get_song_details``
    AI-callable full song lookup by numeric ID.

Event bus
---------
The plugin publishes the following events on ``bot.event_bus`` so other
plugins can react without tight coupling:

+------------------------------+----------------------------------------------+
| Event                        | Payload keys                                 |
+==============================+==============================================+
| ``juicewrld.searched``       | query, result_count, guild_id, user_id       |
+------------------------------+----------------------------------------------+
| ``juicewrld.song_viewed``    | song_id, title, guild_id, user_id            |
+------------------------------+----------------------------------------------+
| ``juicewrld.era_browsed``    | era_name, result_count, guild_id, user_id    |
+------------------------------+----------------------------------------------+
| ``juicewrld.random_played``  | song_id, title, guild_id, user_id            |
+------------------------------+----------------------------------------------+
| ``juicewrld.song_added``     | song_id, title, era, guild_id, user_id       |
+------------------------------+----------------------------------------------+
| ``juicewrld.reindexed``      | stats, guild_id, user_id                     |
+------------------------------+----------------------------------------------+
| ``juicewrld.api_synced``     | added                                        |
+------------------------------+----------------------------------------------+

The plugin also subscribes to ``juicewrld.song_added``, ``juicewrld.api_synced``,
and ``juicewrld.reindexed`` for internal logging and stale-index detection.

URL resolution order
--------------------
When displaying a song link, the plugin tries sources in this order and uses
the first valid ``https://`` URL it finds:

1. ``Song.official_url`` — streaming / release link entered by an admin
2. ``Song.mega_files[0].mega_url`` — specific file matched by the MEGA indexer
   *(only shown when* ``expose_mega_links=True`` *)*
3. ``mega_folder_url`` — the MEGA folder you configured at plugin startup
   *(only shown when* ``expose_mega_links=True`` *)*

Dependencies
------------
Requires the ``juice-wrld-finder`` service layer (``app.*``) on the Python
path.  Install it alongside EasyCord or add the project root to ``PYTHONPATH``.
Optional extras: ``mega.py`` for ``/jw_reindex``; ``httpx`` for background
API sync.
"""
from __future__ import annotations

import asyncio
import logging
import random
from contextlib import contextmanager
from typing import TYPE_CHECKING, Generator

import discord
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from easycord import Plugin, on, slash, task
from easycord.decorators import ai_tool, describe, subscribe
from easycord.server_config import ServerConfigStore
from ._shared import GuildLockManager, respond_error

# Juice WRLD finder service layer — install the juice-wrld-finder package alongside EasyCord.
# None of these modules import app.core.config.settings at import time.
from app.core.security import redact_private_urls
from app.models.media import MegaFileReference
from app.models.song import Era, Song
from app.repositories.song_repo import SongRepository
from app.services.search_service import SearchService
from app.services.song_service import SongService

if TYPE_CHECKING:
    from easycord import Context

logger = logging.getLogger(__name__)


class JuiceWRLDPlugin(Plugin):
    """Juice WRLD song catalog plugin.

    Parameters
    ----------
    database_url:
        SQLAlchemy URL for the catalog database, e.g.
        ``"sqlite:///./juice_wrld.db"`` or ``"postgresql://user:pw@host/db"``.
        The plugin creates its own engine and does not read any
        ``juice-wrld-finder`` environment variables.
    mega_folder_url:
        Your MEGA folder URL (``https://mega.nz/folder/…``).  Used as the
        last-resort link when a song has no ``official_url`` and no specific
        MEGA file has been indexed for it yet.  Only shown in embeds when
        ``expose_mega_links=True``.  Defaults to ``""`` (disabled).
    expose_mega_links:
        When ``True``, MEGA file links and the ``mega_folder_url`` fallback
        are included in song embeds and are **not** redacted.  Set to
        ``False`` (default) for public servers where MEGA links should stay
        private.
    expose_api_download_links:
        When ``True``, ``/jw_song`` also shows the ``api_download_url`` field
        stored on a song record.  Defaults to ``False``.
    use_external_api:
        When ``True``, search commands also query the public Juice WRLD API
        (``juicewrldapi.com``) and a background task syncs new songs every
        6 hours.  No API key is required.  Defaults to ``False``.
    store_path:
        Root directory for per-guild ``ServerConfigStore`` JSON files.
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
        mega_folder_url: str = "",
        expose_mega_links: bool = False,
        expose_api_download_links: bool = False,
        use_external_api: bool = False,
        store_path: str = ".easycord/juicewrld",
    ) -> None:
        super().__init__()

        connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
        engine = create_engine(database_url, connect_args=connect_args)
        self._SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

        self._mega_folder_url = self._safe_url(mega_folder_url)
        self._expose_mega_links = expose_mega_links
        self._expose_api_download_links = expose_api_download_links
        self._use_external_api = use_external_api

        self._store = ServerConfigStore(store_path)
        self._locks = GuildLockManager()

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

    def _resolve_song_url(self, song: Song, db: Session) -> tuple[str, str] | None:
        """Resolve the best available URL for a song, returning ``(url, label)``.

        Priority
        --------
        1. ``Song.official_url`` — labelled "Official Link"
        2. Matched ``MegaFileReference.mega_url`` — labelled "MEGA File"
           *(only when* ``expose_mega_links=True`` *)*
        3. ``mega_folder_url`` supplied at plugin startup — labelled "MEGA Folder"
           *(only when* ``expose_mega_links=True`` *)*

        Returns ``None`` when no valid URL is found.
        """
        url = self._safe_url(song.official_url)
        if url:
            return url, "Official Link"

        if not self._expose_mega_links:
            return None

        ref = (
            db.query(MegaFileReference)
            .filter(MegaFileReference.song_id == song.id)
            .first()
        )
        if ref:
            url = self._safe_url(ref.mega_url)
            if url:
                return url, "MEGA File"

        if self._mega_folder_url:
            return self._mega_folder_url, "MEGA Folder"

        return None

    # ── External API helpers ───────────────────────────────────

    @staticmethod
    def _normalise_api_song(song) -> dict:
        """Normalise a juicewrld_api_wrapper result to a plain dict with a 'title' key."""
        if isinstance(song, dict):
            return song
        return {
            "title": getattr(song, "title", getattr(song, "name", "")),
            "release_status": getattr(song, "release_status", getattr(song, "category", "—")),
            "era": getattr(song, "era", None),
            "id": getattr(song, "id", None),
        }

    async def _api_search(self, query: str, limit: int = 10) -> list[dict]:
        """Search juicewrldapi.com. Returns [] when use_external_api is False or on error."""
        if not self._use_external_api:
            return []
        try:
            from juicewrld_api_wrapper import JuiceWRLDAPI
            results = await asyncio.to_thread(
                lambda: JuiceWRLDAPI().search_songs(query, limit=limit)
            )
            return [self._normalise_api_song(r) for r in (results or [])]
        except Exception as exc:
            logger.warning("_api_search: %s", exc)
            return []

    async def _api_random_song(self) -> dict | None:
        """Fetch songs from juicewrldapi.com and return one at random. None on error."""
        if not self._use_external_api:
            return None
        try:
            from juicewrld_api_wrapper import JuiceWRLDAPI
            songs = await asyncio.to_thread(
                lambda: JuiceWRLDAPI().get_songs(page=1, page_size=50)
            )
            if not songs:
                return None
            return self._normalise_api_song(random.choice(songs))
        except Exception as exc:
            logger.warning("_api_random_song: %s", exc)
            return None

    async def _api_get_song(self, song_id: int) -> dict | None:
        """Fetch a single song from juicewrldapi.com by ID. None on error or when disabled."""
        if not self._use_external_api:
            return None
        try:
            from juicewrld_api_wrapper import JuiceWRLDAPI
            result = await asyncio.to_thread(lambda: JuiceWRLDAPI().get_song(song_id))
            return self._normalise_api_song(result) if result else None
        except Exception as exc:
            logger.warning("_api_get_song: %s", exc)
            return None

    async def _api_era_songs(self, era_name: str) -> list[dict]:
        """Fetch songs by category from juicewrldapi.com. Returns [] when disabled or on error."""
        if not self._use_external_api:
            return []
        try:
            from juicewrld_api_wrapper import JuiceWRLDAPI
            results = await asyncio.to_thread(
                lambda: JuiceWRLDAPI().get_songs_by_category(era_name, page=1, page_size=20)
            )
            return [self._normalise_api_song(r) for r in (results or [])]
        except Exception as exc:
            logger.warning("_api_era_songs: %s", exc)
            return []

    @staticmethod
    def _titles_match(a: str, b: str) -> bool:
        """Return True when two song titles are ≥85% similar (case-insensitive)."""
        from rapidfuzz import fuzz
        return fuzz.partial_ratio(a.lower(), b.lower()) >= 85

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
        """Sync new song metadata from juicewrldapi.com every 6 hours."""
        if not self._use_external_api:
            return
        try:
            from juicewrld_api_wrapper import JuiceWRLDAPI
            remote_songs = await asyncio.to_thread(
                lambda: [self._normalise_api_song(s) for s in JuiceWRLDAPI().get_songs(page=1, page_size=200)]
            )
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
        """Fuzzy search the local catalog. When use_external_api=True, also queries
        juicewrldapi.com in parallel and shows a three-way comparison."""
        def _local_search() -> list:
            with self._db() as db:
                return SearchService(db).search(query, limit=10)

        try:
            local_results, api_results = await asyncio.gather(
                asyncio.to_thread(_local_search),
                self._api_search(query, limit=10),
            )
        except Exception as exc:
            logger.error("jw_search: %s", exc)
            await respond_error(ctx, "Search failed — please try again.")
            return

        api_titles = [r.get("title", "") for r in api_results]

        # Simple path — no API configured
        if not api_results:
            if not local_results:
                await respond_error(ctx, f"No songs found matching `{query}`.")
                return
            embed = discord.Embed(
                title=f"Results for `{query}`",
                description=f"{len(local_results)} match(es) — use `/jw_song <id>` for full details",
                color=discord.Color.green(),
            )
            for r in local_results:
                embed.add_field(
                    name=f"{r.song.title}  ({r.confidence:.0f}%)",
                    value=f"{r.song.release_status}  •  ID `{r.song.id}`",
                    inline=False,
                )
            await ctx.respond(embed=self._redact_embed(embed))
            await self.bot.event_bus.publish(
                "juicewrld.searched",
                query=query,
                result_count=len(local_results),
                api_result_count=0,
                guild_id=ctx.guild.id if ctx.guild else None,
                user_id=ctx.user.id,
            )
            return

        # Comparison path — partition into three buckets
        in_both, local_only = [], []
        for r in local_results:
            if any(self._titles_match(r.song.title, t) for t in api_titles):
                in_both.append(r)
            else:
                local_only.append(r)

        local_titles = [r.song.title for r in local_results]
        api_only = [
            r for r in api_results
            if not any(self._titles_match(r.get("title", ""), lt) for lt in local_titles)
        ]

        embed = discord.Embed(
            title=f"Results for `{query}`",
            color=discord.Color.green(),
        )

        if in_both:
            lines = "\n".join(
                f"• {r.song.title}  ({r.confidence:.0f}%)  •  ID `{r.song.id}`"
                for r in in_both
            )
            embed.add_field(name=f"✅ In both sources ({len(in_both)})", value=lines, inline=False)

        if local_only:
            lines = "\n".join(
                f"• {r.song.title}  ({r.confidence:.0f}%)  •  ID `{r.song.id}`"
                for r in local_only
            )
            embed.add_field(name=f"🗄️ Local only ({len(local_only)})", value=lines, inline=False)

        if api_only:
            lines = "\n".join(
                f"• {r.get('title', '?')}" for r in api_only[:5]
            )
            embed.add_field(
                name=f"🌐 API only — not in local catalog ({len(api_only)})",
                value=lines + ("\n*Use `/jw_add_song` to import*" if api_only else ""),
                inline=False,
            )

        await ctx.respond(embed=self._redact_embed(embed))
        await self.bot.event_bus.publish(
            "juicewrld.searched",
            query=query,
            result_count=len(local_results),
            api_result_count=len(api_results),
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
                resolved = self._resolve_song_url(song, db) if song else None
                safe_api = self._safe_url(getattr(song, "api_download_url", None)) if song else None
        except Exception as exc:
            logger.error("jw_song: %s", exc)
            await respond_error(ctx, "Failed to fetch song details.")
            return

        if not song:
            api_song = await self._api_get_song(song_id)
            if api_song:
                embed = discord.Embed(
                    title=api_song.get("title", "Unknown"),
                    color=discord.Color.orange(),
                )
                embed.add_field(name="Status", value=api_song.get("release_status", "—"), inline=True)
                era = api_song.get("era")
                if era:
                    embed.add_field(
                        name="Era",
                        value=era.name if hasattr(era, "name") else str(era),
                        inline=True,
                    )
                embed.set_footer(text="Source: Juice WRLD API  •  ID may differ from local catalog")
                await ctx.respond(embed=embed)
                await self.bot.event_bus.publish(
                    "juicewrld.song_viewed",
                    song_id=song_id,
                    title=api_song.get("title", "Unknown"),
                    guild_id=ctx.guild.id if ctx.guild else None,
                    user_id=ctx.user.id,
                )
            else:
                await respond_error(ctx, f"No song found with ID `{song_id}`.")
            return

        embed = discord.Embed(title=song.title, color=discord.Color.blue())
        embed.add_field(name="Status", value=song.release_status or "—", inline=True)
        embed.add_field(name="Download", value=song.download_status or "—", inline=True)
        if song.era:
            embed.add_field(name="Era", value=song.era.name, inline=True)
        if resolved:
            song_url, song_url_label = resolved
            embed.add_field(name=song_url_label, value=f"[Listen]({song_url})", inline=False)
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
        """Return up to 20 songs from the named era, supplemented by API results when enabled."""
        def _local_era_query():
            with self._db() as db:
                era = db.query(Era).filter(Era.name.ilike(f"%{era_name}%")).first()
                if not era:
                    return None, []
                return era, SongRepository(db).get_by_era_id(era.id, limit=20)

        try:
            (era_obj, local_songs), api_songs = await asyncio.gather(
                asyncio.to_thread(_local_era_query),
                self._api_era_songs(era_name),
            )
        except Exception as exc:
            logger.error("jw_era: %s", exc)
            await respond_error(ctx, "Era lookup failed.")
            return

        local_titles = [s.title for s in local_songs]
        api_only = [
            s for s in api_songs
            if not any(self._titles_match(s.get("title", ""), lt) for lt in local_titles)
        ]

        if not era_obj and not api_only:
            await respond_error(ctx, f"Era `{era_name}` not found.")
            return

        if not era_obj:
            embed = discord.Embed(
                title=f"{era_name} (API results)",
                description=f"{len(api_only)} song(s) — use `/jw_song <id>` for details",
                color=discord.Color.orange(),
            )
            for s in api_only:
                embed.add_field(name=s.get("title", "?"), value=s.get("release_status", "—"), inline=True)
            embed.set_footer(text="Source: Juice WRLD API  •  Era not in local catalog")
            await ctx.respond(embed=embed)
            await self.bot.event_bus.publish(
                "juicewrld.era_browsed",
                era_name=era_name,
                result_count=len(api_only),
                guild_id=ctx.guild.id if ctx.guild else None,
                user_id=ctx.user.id,
            )
            return

        if not local_songs and not api_only:
            await respond_error(ctx, f"No songs in era `{era_obj.name}`.")
            return

        embed = discord.Embed(
            title=f"{era_obj.name} Era",
            description=f"{len(local_songs)} song(s) — use `/jw_song <id>` for details",
            color=discord.Color.purple(),
        )
        for song in local_songs:
            embed.add_field(name=song.title, value=song.release_status or "—", inline=True)

        if api_only:
            lines = "\n".join(f"• {s.get('title', '?')}" for s in api_only[:5])
            embed.add_field(
                name=f"🌐 API only — not in local catalog ({len(api_only)})",
                value=lines,
                inline=False,
            )

        await ctx.respond(embed=self._redact_embed(embed))
        await self.bot.event_bus.publish(
            "juicewrld.era_browsed",
            era_name=era_obj.name,
            result_count=len(local_songs),
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
                resolved = self._resolve_song_url(song, db) if song else None
        except Exception as exc:
            logger.error("jw_random: %s", exc)
            await respond_error(ctx, "Failed to get a random song.")
            return

        if not song:
            api_song = await self._api_random_song()
            if api_song:
                embed = discord.Embed(
                    title=f"🎲 {api_song.get('title', 'Unknown')}",
                    color=discord.Color.orange(),
                )
                embed.add_field(
                    name="Status",
                    value=api_song.get("release_status", "—"),
                    inline=True,
                )
                if api_song.get("era"):
                    embed.add_field(name="Era", value=api_song["era"], inline=True)
                embed.set_footer(text="Source: Juice WRLD API  •  Not yet in local catalog")
                await ctx.respond(embed=embed)
            else:
                await respond_error(ctx, "No songs in the catalog yet.")
            return

        embed = discord.Embed(title=f"🎲 {song.title}", color=discord.Color.gold())
        embed.add_field(name="Status", value=song.release_status or "—", inline=True)
        embed.add_field(name="Download", value=song.download_status or "—", inline=True)
        if song.era:
            embed.add_field(name="Era", value=song.era.name, inline=True)
        if resolved:
            song_url, song_url_label = resolved
            embed.add_field(name=song_url_label, value=f"[Listen]({song_url})", inline=False)
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
            await respond_error(ctx, "Failed to add song — check logs for details.")
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
            await respond_error(ctx, "Reindex failed — check logs for details.")
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
        def _local():
            with self._db() as db:
                return SearchService(db).search(query, limit=5)

        try:
            local_results, api_results = await asyncio.gather(
                asyncio.to_thread(_local),
                self._api_search(query, limit=5),
            )
        except Exception as exc:
            logger.error("search_juicewrld tool: %s", exc)
            return "Search failed."

        local_titles = [r.song.title for r in local_results]
        api_only = [
            r for r in api_results
            if not any(self._titles_match(r.get("title", ""), lt) for lt in local_titles)
        ]

        if not local_results and not api_only:
            return f"No songs found matching '{query}'."
        lines = [f"Found {len(local_results) + len(api_only)} result(s) for '{query}':"]
        for r in local_results:
            s = r.song
            lines.append(f"  [{s.id}] {s.title} — {s.release_status} ({r.confidence:.0f}% confidence)")
        for r in api_only:
            lines.append(f"  [?] {r.get('title', '?')} — {r.get('release_status', '—')} (API)")
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
            api = await self._api_get_song(song_id)
            if not api:
                return f"No song found with ID {song_id}."
            parts = [f"{api.get('title', 'Unknown')} (API ID {song_id})"]
            parts.append(f"Status: {api.get('release_status', '—')}")
            era = api.get("era")
            if era:
                parts.append(f"Era: {era.name if hasattr(era, 'name') else era}")
            return "\n".join(parts)
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
