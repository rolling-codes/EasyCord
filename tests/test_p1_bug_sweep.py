"""Phase 1 bug-sweep regression net for the bugs.md deferred items.

Regression guards in the ``TestBugs`` docstring style (see
``tests/test_stress.py::TestBugs``) for:

- B-015: levels ``_grant_level_reward`` exception narrowing
- B-016: auto_role post-sleep ``add_roles`` exception coverage
- B-007: invite_tracker ``_invite_cache`` pruning on guild removal

B-013 (auto_responder TOCTOU) is intentionally NOT duplicated here: the fix
routes RMW through ``ServerConfigStore.mutate`` (auto_responder.py:102/116/135)
and interleaved-RMW atomicity is already asserted directly by
``tests/test_auto_responder.py::test_concurrent_add_triggers_all_persist`` and
``test_concurrent_remove_triggers_no_corruption``.

REQ-01 note: auto_role's only role mutation is the ``_on_member_join`` event
handler; its slash commands are config-setters, so no ``bot_permissions``
preflight is added (per the B-021 misleading-preflight lesson). Graceful
degradation without ``manage_roles`` is proven by the B-016 tests below
(``discord.Forbidden`` is absorbed, never escapes the dispatcher).
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest

from easycord.plugins.auto_role import AutoRolePlugin
from easycord.plugins.invite_tracker import InviteTrackerPlugin
from easycord.plugins.levels import LevelsPlugin


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _levels_plugin() -> LevelsPlugin:
    # __new__ + direct attribute pattern per CLAUDE.md; _grant_level_reward
    # touches no plugin state, so no _bot/_store wiring is needed.
    return LevelsPlugin.__new__(LevelsPlugin)


def _invite_plugin() -> InviteTrackerPlugin:
    plugin = InviteTrackerPlugin.__new__(InviteTrackerPlugin)
    plugin._bot = MagicMock()
    plugin._invite_cache = {}
    return plugin


async def _auto_role_plugin(tmp_path, *, guild_id: int, role_ids: list[int], delay: int) -> AutoRolePlugin:
    plugin = AutoRolePlugin(store_path=str(tmp_path / "auto_role"))
    cfg = await plugin._store.load(guild_id)
    cfg.set_other("auto_role", {"role_ids": role_ids, "delay_seconds": delay})
    await plugin._store.save(cfg)
    return plugin


def _member(guild_id: int, role: MagicMock | None) -> MagicMock:
    member = MagicMock(spec=discord.Member)
    member.bot = False
    member.id = 555
    guild = MagicMock(spec=discord.Guild)
    guild.id = guild_id
    guild.get_role.return_value = role
    member.guild = guild
    member.add_roles = AsyncMock()
    return member


# ---------------------------------------------------------------------------
# Bug regressions
# ---------------------------------------------------------------------------

class TestBugs:
    """Regression tests for bugs.md deferred items — each test names its bug."""

    async def test_b015_levels_role_reward_absorbs_http_exception(self) -> None:
        """B-015: levels._grant_level_reward caught Forbidden only; an
        HTTPException from add_roles could escape into the message dispatcher.
        Fixed: except narrowed to discord.HTTPException (covers Forbidden as a
        subclass) — the failed grant returns None instead of raising.
        """
        plugin = _levels_plugin()
        role = MagicMock(spec=discord.Role)
        role.id = 42
        guild = MagicMock(spec=discord.Guild)
        guild.id = 1
        guild.get_role.return_value = role
        member = MagicMock(spec=discord.Member)
        member.id = 7
        member.add_roles = AsyncMock(side_effect=discord.HTTPException(MagicMock(), "boom"))

        result = await plugin._grant_level_reward(member, guild, 5, {"role_rewards": {"5": 42}})

        assert result is None
        member.add_roles.assert_awaited_once()

    async def test_b015_levels_role_reward_does_not_swallow_non_http_errors(self) -> None:
        """B-015 (flip side): narrowing to discord.HTTPException must not hide
        genuine programming errors — a non-HTTP exception raised by add_roles
        propagates instead of being silently converted to None.
        """
        plugin = _levels_plugin()
        role = MagicMock(spec=discord.Role)
        role.id = 42
        guild = MagicMock(spec=discord.Guild)
        guild.id = 1
        guild.get_role.return_value = role
        member = MagicMock(spec=discord.Member)
        member.id = 7
        member.add_roles = AsyncMock(side_effect=ValueError("programming error"))

        with pytest.raises(ValueError, match="programming error"):
            await plugin._grant_level_reward(member, guild, 5, {"role_rewards": {"5": 42}})

    @pytest.mark.parametrize(
        "exc_factory",
        [
            pytest.param(lambda: discord.Forbidden(MagicMock(status=403), "no perms"), id="forbidden"),
            pytest.param(lambda: discord.NotFound(MagicMock(status=404), "role gone"), id="notfound"),
            pytest.param(lambda: discord.HTTPException(MagicMock(status=500), "api down"), id="httpexception"),
        ],
    )
    async def test_b016_auto_role_post_sleep_add_roles_never_raises(self, tmp_path, exc_factory) -> None:
        """B-016: auto_role._on_member_join originally caught only Forbidden
        after the asyncio.sleep delay window; a role deleted during the sleep
        (NotFound) or an API failure (HTTPException) escaped into the event
        dispatcher. Fixed: except discord.HTTPException (parent of Forbidden
        and NotFound) — none of the three may raise out of the handler.

        This also satisfies REQ-01's graceful-denial requirement for the
        event-handler role mutation: Forbidden (bot lacks manage_roles) is
        absorbed with a warning, not raised.
        """
        role = MagicMock(spec=discord.Role)
        role.id = 42
        plugin = await _auto_role_plugin(tmp_path, guild_id=100, role_ids=[42], delay=0)
        member = _member(100, role)
        member.add_roles = AsyncMock(side_effect=exc_factory())

        # Must not raise.
        await plugin._on_member_join(member)

        member.add_roles.assert_awaited_once()

    async def test_b016_auto_role_sleep_window_path_is_guarded(self, tmp_path) -> None:
        """B-016 (delay path): with delay_seconds > 0 the handler awaits
        asyncio.sleep before add_roles — the exact window where the role can
        vanish. Patch sleep (no real waiting) and raise NotFound afterwards:
        the sleep must be awaited with the configured delay and the exception
        must still be absorbed.
        """
        role = MagicMock(spec=discord.Role)
        role.id = 42
        plugin = await _auto_role_plugin(tmp_path, guild_id=100, role_ids=[42], delay=30)
        member = _member(100, role)
        member.add_roles = AsyncMock(side_effect=discord.NotFound(MagicMock(status=404), "role gone"))

        with patch("easycord.plugins.auto_role.asyncio.sleep", new_callable=AsyncMock) as fake_sleep:
            await plugin._on_member_join(member)

        fake_sleep.assert_awaited_once_with(30)
        member.add_roles.assert_awaited_once()

    async def test_b007_guild_remove_prunes_invite_cache(self) -> None:
        """B-007: _invite_cache was never pruned when the bot left a guild —
        entries for departed guilds lingered until restart. Fixed: an
        @on("guild_remove") handler pops the departing guild's cache entry,
        leaving other guilds untouched.
        """
        plugin = _invite_plugin()
        plugin._invite_cache = {100: {"abc": 3}, 200: {"xyz": 1}}
        guild = MagicMock(spec=discord.Guild)
        guild.id = 100

        await plugin._on_guild_remove(guild)

        assert 100 not in plugin._invite_cache
        assert plugin._invite_cache == {200: {"xyz": 1}}

    async def test_b007_guild_remove_uncached_guild_is_noop(self) -> None:
        """B-007 (idempotence): guild_remove for a guild never cached (e.g.
        invites unfetchable at on_load) must be a silent no-op, not a KeyError.
        """
        plugin = _invite_plugin()
        plugin._invite_cache = {200: {"xyz": 1}}
        guild = MagicMock(spec=discord.Guild)
        guild.id = 999

        await plugin._on_guild_remove(guild)

        assert plugin._invite_cache == {200: {"xyz": 1}}

    async def test_b007_guild_remove_handler_is_registered_event(self) -> None:
        """B-007 (wiring): the pruning handler must be a framework event
        handler for "guild_remove" so Bot.dispatch actually invokes it —
        @on(...) sets _is_event/_event_name consumed by the plugin scanner.
        """
        handler = InviteTrackerPlugin._on_guild_remove
        assert getattr(handler, "_is_event", False) is True
        assert getattr(handler, "_event_name", None) == "guild_remove"
