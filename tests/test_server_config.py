"""Tests for ServerConfig and ServerConfigStore."""
from __future__ import annotations

import asyncio

import pytest

from easycord.server_config import ServerConfig, ServerConfigStore


class TestServerConfig:
    def test_empty_config(self) -> None:
        cfg = ServerConfig(1)
        assert cfg.guild_id == 1
        assert cfg.list_roles() == {}
        assert cfg.list_channels() == {}
        assert cfg.list_other() == {}

    def test_set_and_get_role(self) -> None:
        cfg = ServerConfig(1)
        cfg.set_role("moderator", 111)
        assert cfg.get_role("moderator") == 111

    def test_get_role_missing_returns_none(self) -> None:
        cfg = ServerConfig(1)
        assert cfg.get_role("missing") is None

    def test_has_role_true_and_false(self) -> None:
        cfg = ServerConfig(1)
        cfg.set_role("admin", 222)
        assert cfg.has_role("admin") is True
        assert cfg.has_role("nobody") is False

    def test_remove_role(self) -> None:
        cfg = ServerConfig(1)
        cfg.set_role("mod", 333)
        cfg.remove_role("mod")
        assert cfg.get_role("mod") is None

    def test_remove_role_noop_if_missing(self) -> None:
        cfg = ServerConfig(1)
        cfg.remove_role("nonexistent")  # should not raise

    def test_list_roles(self) -> None:
        cfg = ServerConfig(1)
        cfg.set_role("a", 1)
        cfg.set_role("b", 2)
        assert cfg.list_roles() == {"a": 1, "b": 2}

    def test_clear_roles(self) -> None:
        cfg = ServerConfig(1)
        cfg.set_role("a", 1)
        cfg.clear_roles()
        assert cfg.list_roles() == {}

    def test_set_and_get_channel(self) -> None:
        cfg = ServerConfig(1)
        cfg.set_channel("logs", 999)
        assert cfg.get_channel("logs") == 999

    def test_get_channel_missing_returns_none(self) -> None:
        cfg = ServerConfig(1)
        assert cfg.get_channel("missing") is None

    def test_has_channel(self) -> None:
        cfg = ServerConfig(1)
        cfg.set_channel("general", 100)
        assert cfg.has_channel("general") is True
        assert cfg.has_channel("other") is False

    def test_remove_channel(self) -> None:
        cfg = ServerConfig(1)
        cfg.set_channel("logs", 200)
        cfg.remove_channel("logs")
        assert cfg.get_channel("logs") is None

    def test_remove_channel_noop_if_missing(self) -> None:
        cfg = ServerConfig(1)
        cfg.remove_channel("nonexistent")

    def test_list_channels(self) -> None:
        cfg = ServerConfig(1)
        cfg.set_channel("a", 1)
        cfg.set_channel("b", 2)
        assert cfg.list_channels() == {"a": 1, "b": 2}

    def test_clear_channels(self) -> None:
        cfg = ServerConfig(1)
        cfg.set_channel("x", 5)
        cfg.clear_channels()
        assert cfg.list_channels() == {}

    def test_set_and_get_other(self) -> None:
        cfg = ServerConfig(1)
        cfg.set_other("prefix", "!")
        assert cfg.get_other("prefix") == "!"

    def test_get_other_with_default(self) -> None:
        cfg = ServerConfig(1)
        assert cfg.get_other("missing", "default") == "default"

    def test_has_other(self) -> None:
        cfg = ServerConfig(1)
        cfg.set_other("key", "val")
        assert cfg.has_other("key") is True
        assert cfg.has_other("nope") is False

    def test_remove_other(self) -> None:
        cfg = ServerConfig(1)
        cfg.set_other("x", 1)
        cfg.remove_other("x")
        assert cfg.get_other("x") is None

    def test_remove_other_noop_if_missing(self) -> None:
        cfg = ServerConfig(1)
        cfg.remove_other("nonexistent")

    def test_list_other(self) -> None:
        cfg = ServerConfig(1)
        cfg.set_other("a", 1)
        cfg.set_other("b", 2)
        assert cfg.list_other() == {"a": 1, "b": 2}

    def test_clear_other(self) -> None:
        cfg = ServerConfig(1)
        cfg.set_other("x", 1)
        cfg.clear_other()
        assert cfg.list_other() == {}

    def test_reset(self) -> None:
        cfg = ServerConfig(1)
        cfg.set_role("a", 1)
        cfg.set_channel("b", 2)
        cfg.set_other("c", 3)
        cfg.reset()
        assert cfg.list_roles() == {}
        assert cfg.list_channels() == {}
        assert cfg.list_other() == {}

    def test_to_dict_returns_deep_copy(self) -> None:
        cfg = ServerConfig(1)
        cfg.set_role("mod", 1)
        d = cfg.to_dict()
        d["roles"]["mod"] = 999
        assert cfg.get_role("mod") == 1

    def test_merge(self) -> None:
        cfg1 = ServerConfig(1)
        cfg1.set_role("a", 1)
        cfg2 = ServerConfig(1)
        cfg2.set_role("b", 2)
        cfg2.set_channel("c", 3)
        cfg1.merge(cfg2)
        assert cfg1.get_role("a") == 1
        assert cfg1.get_role("b") == 2
        assert cfg1.get_channel("c") == 3

    def test_normalize_bad_data(self) -> None:
        cfg = ServerConfig(1, data={"roles": "bad", "channels": None})
        assert cfg.list_roles() == {}
        assert cfg.list_channels() == {}

    def test_normalize_none_data(self) -> None:
        cfg = ServerConfig(1, data=None)
        assert cfg.list_roles() == {}


class TestServerConfigStore:
    @pytest.fixture
    def store(self, tmp_path):
        return ServerConfigStore(str(tmp_path / "cfg"))

    @pytest.mark.asyncio
    async def test_load_missing_returns_empty(self, store) -> None:
        cfg = await store.load(1)
        assert cfg.guild_id == 1
        assert cfg.list_roles() == {}

    @pytest.mark.asyncio
    async def test_save_and_load_roundtrip(self, store) -> None:
        cfg = await store.load(1)
        cfg.set_role("mod", 123)
        await store.save(cfg)
        loaded = await store.load(1)
        assert loaded.get_role("mod") == 123

    @pytest.mark.asyncio
    async def test_exists_false_before_save(self, store) -> None:
        assert await store.exists(1) is False

    @pytest.mark.asyncio
    async def test_exists_true_after_save(self, store) -> None:
        cfg = await store.load(1)
        await store.save(cfg)
        assert await store.exists(1) is True

    @pytest.mark.asyncio
    async def test_delete(self, store) -> None:
        cfg = await store.load(1)
        await store.save(cfg)
        await store.delete(1)
        assert await store.exists(1) is False

    @pytest.mark.asyncio
    async def test_delete_noop_if_missing(self, store) -> None:
        await store.delete(999)  # should not raise

    @pytest.mark.asyncio
    async def test_load_corrupt_json_raises_runtime_error(self, store, tmp_path) -> None:
        path = tmp_path / "cfg" / "1.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("not json", encoding="utf-8")
        with pytest.raises(RuntimeError):
            await store.load(1)


class TestAtomicMutate:
    @pytest.fixture
    def store(self, tmp_path):
        return ServerConfigStore(str(tmp_path / "cfg"))

    @pytest.mark.asyncio
    async def test_naive_load_modify_save_loses_concurrent_write(self, store) -> None:
        """Documents the race that mutate() exists to prevent.

        Two unlocked load -> modify -> save sequences that interleave (an await
        sits between the load and the save) clobber each other: last save wins.
        """
        async def naive_append(value: int) -> None:
            cfg = await store.load(1)
            items = cfg.get_other("items", [])
            await asyncio.sleep(0)  # force the interleave the real code can hit
            items.append(value)
            cfg.set_other("items", items)
            await store.save(cfg)

        await asyncio.gather(naive_append(1), naive_append(2))

        loaded = await store.load(1)
        # One write was lost — exactly the bug.
        assert len(loaded.get_other("items", [])) == 1

    @pytest.mark.asyncio
    async def test_mutate_serializes_concurrent_writes(self, store) -> None:
        def _append(value: int):
            def _apply(cfg):
                items = cfg.get_other("items", [])
                items.append(value)
                cfg.set_other("items", items)
            return _apply

        await asyncio.gather(
            store.mutate(1, _append(1)),
            store.mutate(1, _append(2)),
        )

        loaded = await store.load(1)
        items = loaded.get_other("items", [])
        # Both writes survive under the per-guild lock.
        assert sorted(items) == [1, 2]

    @pytest.mark.asyncio
    async def test_mutate_returns_callback_value(self, store) -> None:
        def _bump(cfg):
            nxt = cfg.get_other("counter", 0) + 1
            cfg.set_other("counter", nxt)
            return nxt

        first = await store.mutate(1, _bump)
        second = await store.mutate(1, _bump)
        assert (first, second) == (1, 2)

    @pytest.mark.asyncio
    async def test_mutate_persists_changes(self, store) -> None:
        await store.mutate(1, lambda cfg: cfg.set_other("k", "v"))
        loaded = await store.load(1)
        assert loaded.get_other("k") == "v"

    @pytest.mark.asyncio
    async def test_mutate_isolates_guilds(self, store) -> None:
        await store.mutate(1, lambda cfg: cfg.set_other("k", "g1"))
        await store.mutate(2, lambda cfg: cfg.set_other("k", "g2"))
        assert (await store.load(1)).get_other("k") == "g1"
        assert (await store.load(2)).get_other("k") == "g2"

    @pytest.mark.asyncio
    async def test_save_unlocked_failure_raises_runtime_error(self, store) -> None:
        cfg = await store.load(1)
        # Store an unserializable object to force json.dump TypeError
        cfg.set_other("unserializable", lambda: None)
        with pytest.raises(RuntimeError, match="Failed to save config for guild 1"):
            await store.save(cfg)

