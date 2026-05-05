"""Tests for ServerConfig and ServerConfigStore."""
from __future__ import annotations

import json

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
