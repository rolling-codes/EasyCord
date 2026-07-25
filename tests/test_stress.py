"""Stress tests for EasyCord framework — concurrent load, edge cases, and regression prevention.

Each test class targets a specific subsystem. Tests in *TestBugs* are
regression guards for confirmed bugs; the others exercise invariants
under concurrent load.
"""
from __future__ import annotations

import asyncio
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from easycord.middleware import build_chain, rate_limit
from easycord.registry import InteractionRegistry
from easycord.server_config import ServerConfig, ServerConfigStore
from easycord.tool_limits import MAX_TRACKED_ENTRIES, RateLimit, ToolLimiter


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ctx(user_id: int = 1, guild_id: int | None = 100) -> MagicMock:
    ctx = MagicMock()
    ctx.user = MagicMock()
    ctx.user.id = user_id
    ctx.guild = MagicMock() if guild_id is not None else None
    if ctx.guild is not None:
        ctx.guild.id = guild_id
    ctx.respond = AsyncMock()
    ctx.t = lambda key, default="", **kw: default.format(**kw) if kw else default
    ctx.command_name = "test_cmd"
    ctx.channel = MagicMock()
    ctx.channel.id = 9999
    return ctx


def _dummy_cmd():
    pass


# ---------------------------------------------------------------------------
# Bug regressions
# ---------------------------------------------------------------------------

class TestBugs:
    """Regression tests for confirmed bugs — each test names the bug it guards."""

    @pytest.mark.asyncio
    async def test_tool_limiter_cleanup_does_not_raise_key_error(self) -> None:
        """BUG: ToolLimiter._cleanup_usage used `del self._usage[key[0]]` where key is
        a (user_id, tool_name) tuple and key[0] is an int. The dict has tuple keys,
        so this raises KeyError when MAX_TRACKED_ENTRIES is exceeded.
        Fixed: should be `del self._usage[key]`.
        """
        limiter = ToolLimiter()
        limit = RateLimit(max_calls=100, window_minutes=60)

        # Fill the usage dict past MAX_TRACKED_ENTRIES to trigger the cleanup path.
        # We go 10% over to ensure the cleanup actually fires.
        target = MAX_TRACKED_ENTRIES + (MAX_TRACKED_ENTRIES // 10)
        for i in range(target):
            # Directly inject entries so we don't wait for real async calls.
            from datetime import datetime, timezone
            from easycord.tool_limits import RateLimitEntry
            entry = RateLimitEntry(timestamps=[datetime.now(timezone.utc)])
            limiter._usage[(i, "tool")] = entry

        # This must not raise KeyError.
        # The cleanup fires inside check_limit when a new entry is added.
        allowed, _ = await limiter.check_limit(target, "tool", limit)
        assert isinstance(allowed, bool)

    @pytest.mark.asyncio
    async def test_economy_lock_cleanup_does_not_bypass_serialization(self, tmp_path) -> None:
        """BUG: EconomyPlugin._cleanup_old_locks deleted locks based on creation-time
        age without checking whether the lock was currently acquired. A lock older than
        7 days could be removed while still held by an active coroutine; the next caller
        then received a brand-new unacquired lock and bypassed serialization, creating a
        concurrent write race on guild balances.

        Fixed: cleanup now skips locks whose `asyncio.Lock.locked()` returns True,
        AND _balance_lock() refreshes the last-used timestamp on every access so
        active guilds never age out.

        This test directly acquires the lock (bypassing _balance_lock's timestamp
        refresh) to verify the `.locked()` guard independently.
        """
        from easycord.plugins.economy import EconomyPlugin
        from easycord.plugins import PluginConfigManager
        from easycord.plugins._shared import GuildLockManager

        plugin = EconomyPlugin.__new__(EconomyPlugin)
        plugin._locks = GuildLockManager()
        plugin.config = PluginConfigManager(str(tmp_path / "economy"))

        guild_id = 999

        # Insert the lock and its timestamp directly into the manager
        # — bypassing .lock() so the timestamp refresh doesn't undo our backdating.
        plugin._locks._registry[guild_id] = asyncio.Lock()
        plugin._locks._created[guild_id] = datetime.now(timezone.utc) - timedelta(days=8)

        original_lock = plugin._locks._registry[guild_id]

        acquired_event = asyncio.Event()
        cleanup_done_event = asyncio.Event()

        async def holding_task():
            # Acquire directly — avoids the timestamp refresh in _balance_lock().
            async with original_lock:
                acquired_event.set()
                await cleanup_done_event.wait()
                # The lock must still be present in the dict while we hold it.
                assert plugin._locks._registry.get(guild_id) is original_lock, (
                    "Lock for guild 999 was deleted while it was acquired; "
                    "future callers would get a fresh unacquired lock, bypassing serialization."
                )

        async def cleanup_task():
            await acquired_event.wait()
            # Trigger cleanup by registering a new guild.
            plugin._locks.lock(guild_id + 1)
            cleanup_done_event.set()

        await asyncio.wait_for(
            asyncio.gather(holding_task(), cleanup_task()),
            timeout=5.0,
        )


# ---------------------------------------------------------------------------
# ToolLimiter — concurrent stress
# ---------------------------------------------------------------------------

class TestToolLimiterStress:
    @pytest.mark.asyncio
    async def test_concurrent_limit_enforcement(self) -> None:
        """N concurrent check_limit calls must respect the max_calls ceiling."""
        limiter = ToolLimiter()
        limit = RateLimit(max_calls=5, window_minutes=60)
        n = 50

        results = await asyncio.gather(
            *(limiter.check_limit(1, "search", limit) for _ in range(n))
        )
        allowed_count = sum(1 for allowed, _ in results if allowed)
        assert allowed_count == 5, (
            f"Expected exactly 5 allowed requests (max_calls=5), got {allowed_count}"
        )

    @pytest.mark.asyncio
    async def test_window_expires_and_allows_new_calls(self) -> None:
        """After the window expires, new calls must be allowed again."""
        limiter = ToolLimiter()
        limit = RateLimit(max_calls=2, window_minutes=60)

        allowed1, _ = await limiter.check_limit(1, "op", limit)
        allowed2, _ = await limiter.check_limit(1, "op", limit)
        denied, _ = await limiter.check_limit(1, "op", limit)
        assert allowed1 and allowed2 and not denied

        # Expire the timestamps manually.
        key = (1, "op")
        entry = limiter._usage[key]
        entry.timestamps = [t.replace(year=t.year - 1) for t in entry.timestamps]

        allowed_after, _ = await limiter.check_limit(1, "op", limit)
        assert allowed_after, "Should be allowed after window expires"

    @pytest.mark.asyncio
    async def test_reset_user_clears_all_tools(self) -> None:
        """reset_user must clear limits for all tools that user has hit."""
        limiter = ToolLimiter()
        limit = RateLimit(max_calls=1, window_minutes=60)

        await limiter.check_limit(42, "tool_a", limit)
        await limiter.check_limit(42, "tool_b", limit)

        denied_a, _ = await limiter.check_limit(42, "tool_a", limit)
        denied_b, _ = await limiter.check_limit(42, "tool_b", limit)
        assert not denied_a and not denied_b

        await limiter.reset_user(42)

        ok_a, _ = await limiter.check_limit(42, "tool_a", limit)
        ok_b, _ = await limiter.check_limit(42, "tool_b", limit)
        assert ok_a and ok_b

    @pytest.mark.asyncio
    async def test_many_unique_users_independent_limits(self) -> None:
        """Each user's rate limit must be independent — one user exhausted must
        not block another."""
        limiter = ToolLimiter()
        limit = RateLimit(max_calls=3, window_minutes=60)
        n_users = 100

        # Exhaust user 0's limit.
        for _ in range(3):
            await limiter.check_limit(0, "cmd", limit)
        denied, _ = await limiter.check_limit(0, "cmd", limit)
        assert not denied

        # All other users must still get through.
        results = await asyncio.gather(
            *(limiter.check_limit(uid, "cmd", limit) for uid in range(1, n_users))
        )
        assert all(allowed for allowed, _ in results), (
            "Some users were blocked even though only user 0 was rate-limited"
        )

    @pytest.mark.asyncio
    async def test_stats_reflect_tracked_entries(self) -> None:
        """get_stats must return accurate tracking counts."""
        limiter = ToolLimiter()
        limit = RateLimit(max_calls=10, window_minutes=60)
        n = 20

        await asyncio.gather(
            *(limiter.check_limit(uid, "op", limit) for uid in range(n))
        )
        stats = limiter.get_stats()
        assert stats["tracked_limits"] == n
        assert stats["total_calls"] == n


# ---------------------------------------------------------------------------
# rate_limit middleware — exact enforcement under concurrent load
# ---------------------------------------------------------------------------

class TestRateLimitMiddleware:
    @pytest.mark.asyncio
    async def test_exactly_limit_requests_pass(self) -> None:
        """With limit=3 and N > 3 concurrent requests from the same user,
        exactly 3 must be forwarded; the rest must receive the rate-limited reply."""
        mw = rate_limit(limit=3, window=60.0)
        proceed_count = 0

        async def proceed():
            nonlocal proceed_count
            proceed_count += 1

        ctx = _ctx(user_id=77)
        # Run 10 concurrent invocations.
        await asyncio.gather(*(mw(ctx, proceed) for _ in range(10)))

        assert proceed_count == 3, (
            f"Expected exactly 3 allowed requests (limit=3), got {proceed_count}"
        )
        # The remaining 7 should have received a rate-limited reply.
        assert ctx.respond.call_count == 7

    @pytest.mark.asyncio
    async def test_different_users_do_not_share_bucket(self) -> None:
        """Each user must have an independent bucket — user A exhausting their
        limit must not block user B."""
        mw = rate_limit(limit=2, window=60.0)
        pass_counts: dict[int, int] = defaultdict(int)

        async def make_proceed(uid: int):
            async def proceed():
                pass_counts[uid] += 1
            ctx = _ctx(user_id=uid)
            await mw(ctx, proceed)

        # 3 calls for user 1 (limit 2 → 1 blocked), 3 calls for user 2.
        await asyncio.gather(
            make_proceed(1), make_proceed(1), make_proceed(1),
            make_proceed(2), make_proceed(2), make_proceed(2),
        )
        assert pass_counts[1] == 2
        assert pass_counts[2] == 2

    @pytest.mark.asyncio
    async def test_rate_limit_rejects_invalid_config(self) -> None:
        with pytest.raises(ValueError, match="limit must be at least 1"):
            rate_limit(limit=0)
        with pytest.raises(ValueError, match="window must be greater than 0"):
            rate_limit(limit=1, window=0.0)

    @pytest.mark.asyncio
    async def test_build_chain_preserves_order(self) -> None:
        """Middleware chain must execute in registration order (first added = outermost)."""
        order: list[str] = []

        def make_mw(label: str):
            async def mw(ctx, proceed):
                order.append(f"{label}:before")
                await proceed()
                order.append(f"{label}:after")
            return mw

        ctx = _ctx()
        visited = []

        async def invoke():
            visited.append("invoke")

        chain = build_chain(ctx, invoke, [make_mw("A"), make_mw("B"), make_mw("C")])
        await chain()

        assert order == [
            "A:before", "B:before", "C:before",
            "C:after", "B:after", "A:after",
        ], f"Middleware order wrong: {order}"
        assert visited == ["invoke"]

    @pytest.mark.asyncio
    async def test_middleware_abort_skips_downstream(self) -> None:
        """A middleware that does NOT call proceed must block downstream handlers."""
        blocker_calls = 0
        downstream_calls = 0

        async def blocker(ctx, proceed):
            nonlocal blocker_calls
            blocker_calls += 1
            # Intentionally does NOT call proceed.

        async def downstream(ctx, proceed):
            nonlocal downstream_calls
            downstream_calls += 1
            await proceed()

        async def invoke():
            pass

        ctx = _ctx()
        chain = build_chain(ctx, invoke, [blocker, downstream])
        await chain()

        assert blocker_calls == 1
        assert downstream_calls == 0


# ---------------------------------------------------------------------------
# InteractionRegistry — concurrent registration, TTL, and collision detection
# ---------------------------------------------------------------------------

class TestInteractionRegistryStress:
    def test_concurrent_slash_registration_raises_on_duplicate(self) -> None:
        """Registering the same slash command twice must raise ValueError."""
        reg = InteractionRegistry()
        reg.register_slash_command("ping", _dummy_cmd)
        with pytest.raises(ValueError, match="already registered"):
            reg.register_slash_command("ping", _dummy_cmd)

    def test_concurrent_modal_registration_raises_on_duplicate(self) -> None:
        reg = InteractionRegistry()
        reg.register_modal("my_modal", _dummy_cmd)
        with pytest.raises(ValueError, match="already registered"):
            reg.register_modal("my_modal", _dummy_cmd)

    def test_component_ttl_expires(self) -> None:
        """A component registered with TTL=0 must be inactive immediately."""
        reg = InteractionRegistry()
        reg.register_component("btn:act", _dummy_cmd, ttl=0)
        entry, _ = reg.resolve_component("btn:act")
        assert entry is None, "Expired TTL component must not resolve"

    def test_component_ttl_still_active(self) -> None:
        """A component with a future TTL must resolve correctly."""
        reg = InteractionRegistry()
        reg.register_component("btn:ok", _dummy_cmd, ttl=3600)
        entry, _ = reg.resolve_component("btn:ok")
        assert entry is not None

    def test_dynamic_component_pattern_resolves_with_variables(self) -> None:
        reg = InteractionRegistry()
        reg.register_component("ticket:{id:int}:close", _dummy_cmd)
        entry, params = reg.resolve_component("ticket:42:close")
        assert entry is not None
        assert params == {"id": 42}

    def test_dynamic_pattern_collision_detected(self) -> None:
        reg = InteractionRegistry()
        reg.register_component("item:{id:int}", _dummy_cmd)
        with pytest.raises(ValueError, match="collides"):
            reg.register_component("item:{code:int}", _dummy_cmd)

    def test_static_id_collides_with_dynamic_pattern(self) -> None:
        reg = InteractionRegistry()
        reg.register_component("order:{id:int}", _dummy_cmd)
        with pytest.raises(ValueError, match="collides"):
            reg.register_component("order:42", _dummy_cmd)

    def test_unregister_plugin_removes_all_interaction_types(self) -> None:
        reg = InteractionRegistry()
        reg.register_slash_command("cmd", _dummy_cmd, source_plugin="myplugin")
        reg.register_modal("form", _dummy_cmd, source_plugin="myplugin")
        reg.register_component("btn", _dummy_cmd, source_plugin="myplugin")

        reg.unregister_plugin("myplugin")

        grouped = reg.grouped()
        assert not grouped["slash"]
        assert not grouped["modal"]
        assert not grouped["component"]

    def test_unregister_only_removes_target_plugin(self) -> None:
        reg = InteractionRegistry()
        reg.register_slash_command("shared", _dummy_cmd, source_plugin="plugin_a")
        reg.register_slash_command("owned", _dummy_cmd, source_plugin="plugin_b")

        reg.unregister_plugin("plugin_a")

        grouped = reg.grouped()
        names = [e["name"] for e in grouped["slash"]]
        assert "shared" not in names
        assert "owned" in names

    def test_many_unique_components_all_resolve(self) -> None:
        """500 unique static components must all resolve to their entry."""
        reg = InteractionRegistry()
        n = 500
        for i in range(n):
            reg.register_component(f"btn:{i}", _dummy_cmd)

        misses = sum(
            1 for i in range(n) if reg.resolve_component(f"btn:{i}")[0] is None
        )
        assert misses == 0, f"{misses} / {n} components did not resolve"

    def test_scoped_vs_global_slash_commands_coexist(self) -> None:
        """Guild-scoped and global commands with the same name must not collide."""
        reg = InteractionRegistry()
        reg.register_slash_command("help", _dummy_cmd, guild_id=None)
        reg.register_slash_command("help", _dummy_cmd, guild_id=12345)
        # Both should exist.
        assert len(reg.slash_commands) == 2


# ---------------------------------------------------------------------------
# ServerConfigStore — concurrent integrity
# ---------------------------------------------------------------------------

class TestServerConfigStoreConcurrency:
    @pytest.mark.asyncio
    async def test_concurrent_saves_do_not_corrupt_data(self, tmp_path) -> None:
        """50 concurrent tasks each incrementing a counter must end at exactly 50.

        This test verifies the per-guild asyncio.Lock on the store prevents
        lost-update races when multiple coroutines load + mutate + save.
        """
        store = ServerConfigStore(str(tmp_path / "cfg"))
        guild_id = 1

        async def increment():
            cfg = await store.load(guild_id)
            count = cfg.get_other("count", 0)
            cfg.set_other("count", count + 1)
            await store.save(cfg)

        n = 50
        await asyncio.gather(*(increment() for _ in range(n)))

        final = await store.load(guild_id)
        assert final.get_other("count") == n, (
            f"Expected count={n} after {n} increments; got {final.get_other('count')}"
        )

    @pytest.mark.asyncio
    async def test_concurrent_saves_different_guilds_are_independent(self, tmp_path) -> None:
        """Each guild's store must be isolated; concurrent writes to different
        guilds must not interfere with each other."""
        store = ServerConfigStore(str(tmp_path / "cfg"))
        n_guilds = 20
        n_writes = 10

        async def write_guild(guild_id: int):
            for i in range(n_writes):
                cfg = await store.load(guild_id)
                cfg.set_other("val", i)
                await store.save(cfg)

        await asyncio.gather(*(write_guild(gid) for gid in range(n_guilds)))

        for gid in range(n_guilds):
            cfg = await store.load(gid)
            assert cfg.get_other("val") == n_writes - 1

    @pytest.mark.asyncio
    async def test_load_returns_fresh_object_each_time(self, tmp_path) -> None:
        """Mutating a loaded ServerConfig must not affect a subsequent load."""
        store = ServerConfigStore(str(tmp_path / "cfg"))
        guild_id = 99

        cfg1 = await store.load(guild_id)
        cfg1.set_other("key", "value")
        # Do NOT save — mutation is local.

        cfg2 = await store.load(guild_id)
        assert cfg2.get_other("key") is None, (
            "Load returned the same mutable object instead of a fresh instance"
        )

    @pytest.mark.asyncio
    async def test_delete_and_reload_returns_empty_config(self, tmp_path) -> None:
        store = ServerConfigStore(str(tmp_path / "cfg"))
        guild_id = 55

        cfg = await store.load(guild_id)
        cfg.set_other("data", "present")
        await store.save(cfg)

        await store.delete(guild_id)
        assert not await store.exists(guild_id)

        fresh = await store.load(guild_id)
        assert fresh.get_other("data") is None


# ---------------------------------------------------------------------------
# ServerConfig — merge and reset correctness
# ---------------------------------------------------------------------------

class TestServerConfigLogic:
    def test_merge_overwrites_keys(self) -> None:
        a = ServerConfig(1, {"roles": {"admin": 10}, "channels": {}, "other": {}})
        b = ServerConfig(1, {"roles": {"admin": 20, "mod": 30}, "channels": {}, "other": {}})
        a.merge(b)
        assert a.get_role("admin") == 20
        assert a.get_role("mod") == 30

    def test_merge_does_not_mutate_source(self) -> None:
        a = ServerConfig(1)
        b = ServerConfig(2)
        b.set_role("admin", 42)
        a.merge(b)
        # Mutating a must not affect b.
        a.set_role("admin", 999)
        assert b.get_role("admin") == 42

    def test_reset_clears_all_sections(self) -> None:
        cfg = ServerConfig(1)
        cfg.set_role("admin", 1)
        cfg.set_channel("logs", 2)
        cfg.set_other("prefix", "!")
        cfg.reset()
        assert cfg.list_roles() == {}
        assert cfg.list_channels() == {}
        assert cfg.list_other() == {}

    def test_to_dict_is_deep_copy(self) -> None:
        cfg = ServerConfig(1)
        cfg.set_other("nested", {"a": 1})
        d = cfg.to_dict()
        d["other"]["nested"]["a"] = 999
        assert cfg.get_other("nested") == {"a": 1}, (
            "to_dict returned a reference; mutation of the dict affected the original"
        )

    def test_normalize_ignores_malformed_sections(self) -> None:
        cfg = ServerConfig(1, {"roles": "not_a_dict", "channels": None, "other": {}})
        assert cfg.list_roles() == {}
        assert cfg.list_channels() == {}

    def test_merge_with_empty_source_is_noop(self) -> None:
        cfg = ServerConfig(1)
        cfg.set_role("admin", 7)
        cfg.merge(ServerConfig(2))
        assert cfg.get_role("admin") == 7

    def test_set_other_stores_complex_types(self) -> None:
        cfg = ServerConfig(1)
        payload = {"nested": [1, 2, {"deep": True}]}
        cfg.set_other("data", payload)
        assert cfg.get_other("data") == payload

    def test_remove_missing_key_is_noop(self) -> None:
        cfg = ServerConfig(1)
        cfg.remove_role("nonexistent")
        cfg.remove_channel("nonexistent")
        cfg.remove_other("nonexistent")


# ---------------------------------------------------------------------------
# Economy plugin — high-load concurrency
# ---------------------------------------------------------------------------

class TestEconomyPluginHighLoad:
    @pytest.fixture
    def plugin(self, tmp_path):
        from easycord.plugins.economy import EconomyPlugin
        from easycord.plugins import PluginConfigManager
        from easycord.plugins._shared import GuildLockManager

        p = EconomyPlugin.__new__(EconomyPlugin)
        p._locks = GuildLockManager()
        p.config = PluginConfigManager(str(tmp_path / "economy"))

        # Wrap load/save with a cooperative yield to expose any async races.
        orig_load = p.config.store.load
        orig_save = p.config.store.save

        async def yielding_load(guild_id):
            await asyncio.sleep(0)
            return await orig_load(guild_id)

        async def yielding_save(config):
            await asyncio.sleep(0)
            return await orig_save(config)

        p.config.store.load = yielding_load
        p.config.store.save = yielding_save
        return p

    @pytest.mark.asyncio
    async def test_100_concurrent_increments_lose_no_updates(self, plugin) -> None:
        """100 concurrent +1 rewards must sum to exactly 100."""
        n = 100
        await asyncio.gather(*(plugin._add_balance(1, 1, 1) for _ in range(n)))
        assert await plugin._get_balance(1, 1) == n

    @pytest.mark.asyncio
    async def test_multi_guild_concurrent_increments_isolated(self, plugin) -> None:
        """Concurrent increments across 10 guilds must each total independently."""
        n = 20
        n_guilds = 10
        tasks = [
            plugin._add_balance(gid, 1, 1)
            for gid in range(n_guilds)
            for _ in range(n)
        ]
        await asyncio.gather(*tasks)

        for gid in range(n_guilds):
            bal = await plugin._get_balance(gid, 1)
            assert bal == n, f"Guild {gid}: expected {n}, got {bal}"

    @pytest.mark.asyncio
    async def test_total_currency_conserved_under_heavy_transfers(self, plugin) -> None:
        """Under heavy bidirectional transfers, total currency must never change."""
        await plugin._set_balance(1, 1, 500)
        await plugin._set_balance(1, 2, 500)
        initial_total = 1000

        n = 30
        await asyncio.gather(
            *(plugin._transfer(1, 1, 2, 5) for _ in range(n)),
            *(plugin._transfer(1, 2, 1, 5) for _ in range(n)),
        )

        total = await plugin._get_balance(1, 1) + await plugin._get_balance(1, 2)
        assert total == initial_total, (
            f"Currency was created or destroyed: {total} != {initial_total}"
        )

    @pytest.mark.asyncio
    async def test_overdraw_never_goes_negative(self, plugin) -> None:
        """Concurrent overdraw attempts must never let any balance go below zero."""
        await plugin._set_balance(1, 1, 50)

        # Attempt 20 transfers of 10 each (total would be 200 > 50).
        n = 20
        await asyncio.gather(
            *(plugin._transfer(1, 1, 2, 10) for _ in range(n))
        )

        bal1 = await plugin._get_balance(1, 1)
        bal2 = await plugin._get_balance(1, 2)

        assert bal1 >= 0, f"Sender balance went negative: {bal1}"
        assert bal2 >= 0, f"Receiver balance went negative: {bal2}"
        assert bal1 + bal2 == 50, (
            f"Currency leak: {bal1} + {bal2} != 50"
        )

    @pytest.mark.asyncio
    async def test_daily_reward_claimed_exactly_once_concurrently(self, plugin) -> None:
        """Concurrent /daily invocations for the same user in the same guild must
        award the reward exactly once."""
        from unittest.mock import AsyncMock, MagicMock

        def _make_ctx(user_id: int = 1, guild_id: int = 1) -> MagicMock:
            ctx = MagicMock()
            ctx.user = MagicMock()
            ctx.user.id = user_id
            ctx.guild = MagicMock()
            ctx.guild.id = guild_id
            ctx.respond = AsyncMock()
            ctx.t = lambda key, default="", **kw: default.format(**kw) if kw else default
            return ctx

        n = 10
        ctxs = [_make_ctx() for _ in range(n)]
        await asyncio.gather(*(plugin.daily(ctx) for ctx in ctxs))

        final = await plugin._get_balance(1, 1)
        default_reward = 100
        assert final == default_reward, (
            f"Expected reward claimed exactly once (balance={default_reward}); got {final}"
        )

        # Exactly n-1 ephemeral "already claimed" responses must exist across
        # all contexts.
        ephemeral_count = sum(
            1
            for ctx in ctxs
            for call in ctx.respond.call_args_list
            if call.kwargs.get("ephemeral")
        )
        assert ephemeral_count == n - 1, (
            f"Expected {n - 1} 'already claimed' ephemeral responses, got {ephemeral_count}"
        )


# ---------------------------------------------------------------------------
# XP / levels math — pure-function invariants
# ---------------------------------------------------------------------------

class TestLevelsMath:
    def test_xp_for_level_zero_is_zero(self) -> None:
        from easycord.plugins._levels_data import xp_for_level
        assert xp_for_level(0) == 0

    def test_xp_for_level_one_is_100(self) -> None:
        from easycord.plugins._levels_data import xp_for_level
        assert xp_for_level(1) == 100

    def test_xp_for_level_strictly_increasing(self) -> None:
        from easycord.plugins._levels_data import xp_for_level
        for n in range(50):
            assert xp_for_level(n) < xp_for_level(n + 1), (
                f"xp_for_level({n}) >= xp_for_level({n + 1})"
            )

    def test_level_from_xp_roundtrip(self) -> None:
        """level_from_xp(xp_for_level(n)) must return n for all n in [0, 100]."""
        from easycord.plugins._levels_data import level_from_xp, xp_for_level
        for n in range(101):
            assert level_from_xp(xp_for_level(n)) == n, (
                f"level_from_xp(xp_for_level({n})) != {n}"
            )

    def test_level_from_xp_one_below_threshold(self) -> None:
        """xp_for_level(n) - 1 must map to level n-1."""
        from easycord.plugins._levels_data import level_from_xp, xp_for_level
        for n in range(1, 50):
            xp = xp_for_level(n) - 1
            assert level_from_xp(xp) == n - 1, (
                f"level_from_xp(xp_for_level({n}) - 1) != {n - 1}"
            )

    def test_progress_bar_length_always_equals_width(self) -> None:
        """BUG: progress_bar returned more than `width` characters when XP
        exceeded the current level band (no upper-bound clamp on `filled`).

        ``filled = int((xp - floor) / span * width)`` can exceed ``width`` if
        ``xp > next_ceil``.  The bar then contains ``filled`` filled glyphs and
        ``width - filled`` (negative!) empty glyphs, so ``"░" * negative == ""``,
        producing a string longer than ``width``.

        Fixed: ``filled`` is now clamped to ``[0, width]``.
        """
        from easycord.plugins._levels_data import progress_bar, xp_for_level
        width = 10
        # At each level, test at the floor, midpoint, and one XP ABOVE the ceiling.
        for level in range(0, 20):
            floor = xp_for_level(level)
            ceil_ = xp_for_level(level + 1)

            for xp in (floor, (floor + ceil_) // 2, ceil_ + 50):
                bar = progress_bar(xp, level, width=width)
                assert len(bar) == width, (
                    f"progress_bar(xp={xp}, level={level}) returned {len(bar)!r} "
                    f"chars (expected {width}): {bar!r}"
                )

    def test_progress_bar_full_at_or_above_ceiling(self) -> None:
        """When XP meets or exceeds the level ceiling the bar should be full (all filled)."""
        from easycord.plugins._levels_data import progress_bar, xp_for_level
        level = 5
        bar = progress_bar(xp_for_level(level + 1), level, width=10)
        assert bar == "█" * 10, f"Expected full bar, got {bar!r}"

    def test_progress_bar_empty_at_floor(self) -> None:
        """When XP is exactly at the level floor the bar should be empty."""
        from easycord.plugins._levels_data import progress_bar, xp_for_level
        level = 3
        bar = progress_bar(xp_for_level(level), level, width=10)
        assert bar == "░" * 10, f"Expected empty bar, got {bar!r}"

    @pytest.mark.asyncio
    async def test_levels_store_concurrent_xp_no_lost_updates(self, tmp_path) -> None:
        """50 concurrent +10 XP additions must sum to exactly 500."""
        from easycord.plugins._levels_data import LevelsStore
        store = LevelsStore(str(tmp_path / "lvls"))
        n = 50
        await asyncio.gather(*(store.add_xp(1, 1, 10) for _ in range(n)))
        entry = store.get_entry(1, 1)
        assert entry["xp"] == n * 10, (
            f"Expected {n * 10} XP after {n} concurrent adds; got {entry['xp']}"
        )

    @pytest.mark.asyncio
    async def test_levels_store_concurrent_multi_user(self, tmp_path) -> None:
        """Concurrent XP adds for 10 users in the same guild must all be correct."""
        from easycord.plugins._levels_data import LevelsStore
        store = LevelsStore(str(tmp_path / "lvls"))
        n = 20
        n_users = 10
        tasks = [
            store.add_xp(1, uid, 5)
            for uid in range(n_users)
            for _ in range(n)
        ]
        await asyncio.gather(*tasks)
        for uid in range(n_users):
            entry = store.get_entry(1, uid)
            assert entry["xp"] == n * 5, (
                f"User {uid}: expected {n * 5} XP, got {entry['xp']}"
            )


# ---------------------------------------------------------------------------
# Validators — edge cases and correctness
# ---------------------------------------------------------------------------

class TestValidators:
    def test_duration_seconds(self) -> None:
        from easycord.validators import Duration
        assert Duration()("30s") == 30.0

    def test_duration_minutes(self) -> None:
        from easycord.validators import Duration
        assert Duration()("5m") == 300.0

    def test_duration_hours(self) -> None:
        from easycord.validators import Duration
        assert Duration()("2h") == 7200.0

    def test_duration_days(self) -> None:
        from easycord.validators import Duration
        assert Duration()("1d") == 86400.0

    def test_duration_case_insensitive(self) -> None:
        from easycord.validators import Duration
        assert Duration()("10M") == Duration()("10m")

    def test_duration_decimal(self) -> None:
        from easycord.validators import Duration
        assert Duration()("0.5h") == pytest.approx(1800.0)

    def test_duration_numeric_positive(self) -> None:
        from easycord.validators import Duration
        assert Duration()(60) == 60.0

    def test_duration_numeric_negative_raises(self) -> None:
        from easycord.validators import Duration, ValidationError
        with pytest.raises(ValidationError, match="positive"):
            Duration()(-1)

    def test_duration_invalid_unit_raises(self) -> None:
        from easycord.validators import Duration, ValidationError
        with pytest.raises(ValidationError):
            Duration()("10x")

    def test_duration_empty_string_raises(self) -> None:
        from easycord.validators import Duration, ValidationError
        with pytest.raises(ValidationError):
            Duration()("")

    def test_url_valid_http(self) -> None:
        from easycord.validators import URL
        assert URL()("http://example.com") == "http://example.com"

    def test_url_valid_https(self) -> None:
        from easycord.validators import URL
        assert URL()("https://example.com/path?q=1") == "https://example.com/path?q=1"

    def test_url_no_scheme_raises(self) -> None:
        from easycord.validators import URL, ValidationError
        with pytest.raises(ValidationError):
            URL()("example.com")

    def test_url_ftp_raises(self) -> None:
        from easycord.validators import URL, ValidationError
        with pytest.raises(ValidationError):
            URL()("ftp://files.example.com")

    def test_snowflake_15_digits(self) -> None:
        from easycord.validators import Snowflake
        assert Snowflake()("123456789012345") == 123456789012345

    def test_snowflake_22_digits(self) -> None:
        from easycord.validators import Snowflake
        assert Snowflake()("1234567890123456789012") == 1234567890123456789012

    def test_snowflake_14_digits_raises(self) -> None:
        from easycord.validators import Snowflake, ValidationError
        with pytest.raises(ValidationError):
            Snowflake()("12345678901234")  # 14 digits

    def test_snowflake_23_digits_raises(self) -> None:
        from easycord.validators import Snowflake, ValidationError
        with pytest.raises(ValidationError):
            Snowflake()("12345678901234567890123")  # 23 digits

    def test_snowflake_non_digits_raises(self) -> None:
        from easycord.validators import Snowflake, ValidationError
        with pytest.raises(ValidationError):
            Snowflake()("12345678901234X")

    def test_range_min_only(self) -> None:
        from easycord.validators import Range
        assert Range(min=5)(10) == 10

    def test_range_max_only(self) -> None:
        from easycord.validators import Range
        assert Range(max=10)(5) == 5

    def test_range_both_bounds(self) -> None:
        from easycord.validators import Range
        assert Range(min=1, max=10)(5) == 5

    def test_range_at_min_boundary(self) -> None:
        from easycord.validators import Range
        assert Range(min=5)(5) == 5

    def test_range_at_max_boundary(self) -> None:
        from easycord.validators import Range
        assert Range(max=10)(10) == 10

    def test_range_below_min_raises(self) -> None:
        from easycord.validators import Range, ValidationError
        with pytest.raises(ValidationError, match="at least"):
            Range(min=5)(4)

    def test_range_above_max_raises(self) -> None:
        from easycord.validators import Range, ValidationError
        with pytest.raises(ValidationError, match="at most"):
            Range(max=10)(11)

    def test_range_inverted_bounds_raises(self) -> None:
        """BUG: Range(min=5, max=3) silently accepted contradictory bounds —
        the constructor performed no validation of min <= max.  A validator
        with inverted bounds always raises on every input, so any misconfigured
        command would silently reject ALL values instead of the expected range.
        Fixed: __post_init__ now raises ValueError when min > max.
        """
        from easycord.validators import Range
        with pytest.raises(ValueError, match="min.*max|max.*min"):
            Range(min=5, max=3)

    def test_regex_valid_match(self) -> None:
        from easycord.validators import Regex
        assert Regex(r"\d{4}")(value="1234") == "1234"

    def test_regex_no_match_raises(self) -> None:
        from easycord.validators import Regex, ValidationError
        with pytest.raises(ValidationError, match="invalid format"):
            Regex(r"\d{4}")("abcd")

    def test_regex_min_length_enforced(self) -> None:
        from easycord.validators import Regex, ValidationError
        with pytest.raises(ValidationError, match="at least 3"):
            Regex(r".*", min_length=3)("ab")

    def test_regex_max_length_enforced(self) -> None:
        from easycord.validators import Regex, ValidationError
        with pytest.raises(ValidationError, match="at most 5"):
            Regex(r".*", max_length=5)("toolong")

    def test_choice_set_valid(self) -> None:
        from easycord.validators import ChoiceSet
        assert ChoiceSet("a", "b", "c")("b") == "b"

    def test_choice_set_invalid_raises(self) -> None:
        from easycord.validators import ChoiceSet, ValidationError
        with pytest.raises(ValidationError, match="Choose one of"):
            ChoiceSet("a", "b")("c")

    def test_choice_set_empty_raises(self) -> None:
        from easycord.validators import ChoiceSet
        with pytest.raises(ValueError, match="at least one choice"):
            ChoiceSet()

    def test_choice_set_numeric(self) -> None:
        from easycord.validators import ChoiceSet
        assert ChoiceSet(1, 2, 3)(2) == 2

    def test_validation_error_user_message(self) -> None:
        from easycord.validators import ValidationError
        err = ValidationError("Too short.", key="errors.min_len")
        ctx = MagicMock()
        ctx.t = lambda _key, default="", **_kw: default
        assert err.user_message(ctx) == "Too short."


# ---------------------------------------------------------------------------
# ConversationMemory — correctness and eviction
# ---------------------------------------------------------------------------

class TestConversationMemory:
    def test_max_cap_enforced_on_add(self) -> None:
        """Adding more conversations than max_conversations must evict the oldest."""
        from easycord.conversation_memory import ConversationMemory
        mem = ConversationMemory(max_conversations=3)
        for uid in range(5):
            mem.add_user_message(uid, "hello")
        assert mem.get_stats()["total_conversations"] <= 3

    def test_eviction_removes_least_recently_updated(self) -> None:
        """The oldest-updated conversation must be evicted first when over cap."""
        from easycord.conversation_memory import ConversationMemory
        from datetime import datetime, timedelta, timezone
        mem = ConversationMemory(max_conversations=2)
        mem.add_user_message(1, "first")
        mem.add_user_message(2, "second")
        # Manually backdate user 1 so they are the oldest.
        mem._conversations[(1, None)].last_updated = (
            datetime.now(timezone.utc) - timedelta(hours=1)
        )
        # Adding a third user must evict user 1.
        mem.add_user_message(3, "third")
        stats = mem.get_stats()
        assert stats["total_conversations"] == 2
        # User 1 (oldest) should be gone; users 2 and 3 should remain.
        assert mem.get_messages(2) != []
        assert mem.get_messages(3) != []

    def test_expired_conversation_cleared_on_next_access(self) -> None:
        """Accessing an expired conversation must return empty messages (fresh state)."""
        from easycord.conversation_memory import ConversationMemory
        from datetime import datetime, timedelta, timezone
        mem = ConversationMemory(max_conversations=10, default_max_age_minutes=60)
        mem.add_user_message(1, "original message")
        # Expire the conversation manually.
        mem._conversations[(1, None)].last_updated = (
            datetime.now(timezone.utc) - timedelta(hours=2)
        )
        messages = mem.get_messages(1)
        assert messages == [], (
            "Expected empty messages after expiry; got stale history"
        )

    def test_clear_removes_history(self) -> None:
        from easycord.conversation_memory import ConversationMemory
        mem = ConversationMemory(max_conversations=10)
        mem.add_user_message(1, "msg")
        mem.clear(1)
        assert mem.get_messages(1) == []

    def test_turn_count_limit_enforced(self) -> None:
        """Conversation must not retain more than max_turns turns."""
        from easycord.conversation_memory import ConversationMemory
        mem = ConversationMemory(max_conversations=10, default_max_turns=5)
        for i in range(10):
            mem.add_user_message(1, f"msg {i}")
        msgs = mem.get_messages(1)
        assert len(msgs) <= 5, f"Expected <=5 turns, got {len(msgs)}"

    def test_guild_isolation(self) -> None:
        """Same user in different guilds must have independent conversations."""
        from easycord.conversation_memory import ConversationMemory
        mem = ConversationMemory(max_conversations=10)
        mem.add_user_message(1, "guild A message", guild_id=100)
        mem.add_user_message(1, "guild B message", guild_id=200)
        msgs_a = mem.get_messages(1, guild_id=100)
        msgs_b = mem.get_messages(1, guild_id=200)
        assert len(msgs_a) == 1
        assert len(msgs_b) == 1
        assert msgs_a[0]["content"] == "guild A message"
        assert msgs_b[0]["content"] == "guild B message"

    def test_cleanup_expired_returns_count(self) -> None:
        from easycord.conversation_memory import ConversationMemory
        from datetime import datetime, timedelta, timezone
        mem = ConversationMemory(max_conversations=10, default_max_age_minutes=1)
        mem.add_user_message(1, "old")
        mem.add_user_message(2, "also old")
        mem.add_user_message(3, "fresh")
        # Expire two.
        for uid in (1, 2):
            mem._conversations[(uid, None)].last_updated = (
                datetime.now(timezone.utc) - timedelta(minutes=5)
            )
        removed = mem.cleanup_expired()
        assert removed == 2
        assert mem.get_stats()["total_conversations"] == 1

    def test_stats_accurate(self) -> None:
        from easycord.conversation_memory import ConversationMemory
        mem = ConversationMemory(max_conversations=10)
        mem.add_user_message(1, "a")
        mem.add_user_message(1, "b")
        mem.add_user_message(2, "x")
        stats = mem.get_stats()
        assert stats["total_conversations"] == 2
        assert stats["total_turns"] == 3
