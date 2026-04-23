import json
import pytest

from easycord.server_config import ServerConfig, ServerConfigStore


# ── ServerConfig ──────────────────────────────────────────────────────────────

class TestServerConfigRoles:
    def test_set_and_get(self):
        cfg = ServerConfig(guild_id=1)
        cfg.set_role("mod", 100)
        assert cfg.get_role("mod") == 100

    def test_has_role(self):
        cfg = ServerConfig(guild_id=1)
        assert not cfg.has_role("mod")
        cfg.set_role("mod", 100)
        assert cfg.has_role("mod")

    def test_remove_role(self):
        cfg = ServerConfig(guild_id=1)
        cfg.set_role("mod", 100)
        cfg.remove_role("mod")
        assert not cfg.has_role("mod")
        assert cfg.get_role("mod") is None

    def test_remove_nonexistent_is_noop(self):
        cfg = ServerConfig(guild_id=1)
        cfg.remove_role("ghost")  # should not raise

    def test_list_roles(self):
        cfg = ServerConfig(guild_id=1)
        cfg.set_role("mod", 1)
        cfg.set_role("admin", 2)
        assert cfg.list_roles() == {"mod": 1, "admin": 2}

    def test_list_roles_is_copy(self):
        cfg = ServerConfig(guild_id=1)
        cfg.set_role("mod", 1)
        cfg.list_roles()["mod"] = 999
        assert cfg.get_role("mod") == 1

    def test_clear_roles(self):
        cfg = ServerConfig(guild_id=1)
        cfg.set_role("mod", 1)
        cfg.clear_roles()
        assert cfg.list_roles() == {}


class TestServerConfigChannels:
    def test_set_get_has_remove(self):
        cfg = ServerConfig(guild_id=1)
        cfg.set_channel("logs", 200)
        assert cfg.has_channel("logs")
        assert cfg.get_channel("logs") == 200
        cfg.remove_channel("logs")
        assert not cfg.has_channel("logs")
        assert cfg.get_channel("logs") is None

    def test_list_channels(self):
        cfg = ServerConfig(guild_id=1)
        cfg.set_channel("logs", 1)
        cfg.set_channel("welcome", 2)
        assert cfg.list_channels() == {"logs": 1, "welcome": 2}

    def test_clear_channels(self):
        cfg = ServerConfig(guild_id=1)
        cfg.set_channel("logs", 1)
        cfg.clear_channels()
        assert cfg.list_channels() == {}


class TestServerConfigOther:
    def test_set_get_has_remove(self):
        cfg = ServerConfig(guild_id=1)
        cfg.set_other("prefix", "!")
        assert cfg.has_other("prefix")
        assert cfg.get_other("prefix") == "!"
        cfg.remove_other("prefix")
        assert not cfg.has_other("prefix")
        assert cfg.get_other("prefix") is None

    def test_get_with_default(self):
        cfg = ServerConfig(guild_id=1)
        assert cfg.get_other("missing", "fallback") == "fallback"

    def test_list_other(self):
        cfg = ServerConfig(guild_id=1)
        cfg.set_other("x", 1)
        assert cfg.list_other() == {"x": 1}

    def test_clear_other(self):
        cfg = ServerConfig(guild_id=1)
        cfg.set_other("x", 1)
        cfg.clear_other()
        assert cfg.list_other() == {}

    def test_set_other_any_type(self):
        cfg = ServerConfig(guild_id=1)
        cfg.set_other("list", [1, 2, 3])
        assert cfg.get_other("list") == [1, 2, 3]


class TestServerConfigBulk:
    def test_reset_clears_all(self):
        cfg = ServerConfig(guild_id=1)
        cfg.set_role("mod", 1)
        cfg.set_channel("logs", 2)
        cfg.set_other("prefix", "!")
        cfg.reset()
        assert cfg.list_roles() == {}
        assert cfg.list_channels() == {}
        assert cfg.list_other() == {}

    def test_merge_overwrites_existing_keys(self):
        cfg1 = ServerConfig(guild_id=1)
        cfg1.set_role("mod", 1)
        cfg2 = ServerConfig(guild_id=2)
        cfg2.set_role("mod", 99)
        cfg2.set_role("admin", 2)
        cfg1.merge(cfg2)
        assert cfg1.get_role("mod") == 99
        assert cfg1.get_role("admin") == 2

    def test_to_dict_is_deep_copy(self):
        cfg = ServerConfig(guild_id=1)
        cfg.set_role("mod", 1)
        d = cfg.to_dict()
        d["roles"]["mod"] = 999
        assert cfg.get_role("mod") == 1

    def test_to_dict_contains_all_sections(self):
        cfg = ServerConfig(guild_id=1)
        d = cfg.to_dict()
        assert set(d.keys()) == {"roles", "channels", "other"}


class TestServerConfigNormalize:
    def test_invalid_data_returns_empty(self):
        cfg = ServerConfig(guild_id=1, data="not a dict")
        assert cfg.list_roles() == {}
        assert cfg.list_channels() == {}
        assert cfg.list_other() == {}

    def test_none_data_returns_empty(self):
        cfg = ServerConfig(guild_id=1, data=None)
        assert cfg.list_roles() == {}

    def test_partial_data_fills_missing_sections(self):
        cfg = ServerConfig(guild_id=1, data={"roles": {"mod": 1}})
        assert cfg.get_role("mod") == 1
        assert cfg.list_channels() == {}
        assert cfg.list_other() == {}

    def test_null_subsections_become_empty_dicts(self):
        cfg = ServerConfig(guild_id=1, data={"roles": None, "channels": None, "other": None})
        assert cfg.list_roles() == {}

    def test_invalid_subsection_values_fall_back_to_empty_dicts(self):
        cfg = ServerConfig(guild_id=1, data={"roles": 123, "channels": ["bad"], "other": object()})
        assert cfg.list_roles() == {}
        assert cfg.list_channels() == {}
        assert cfg.list_other() == {}


# ── ServerConfigStore ─────────────────────────────────────────────────────────

@pytest.fixture
def store(tmp_path):
    return ServerConfigStore(base_dir=str(tmp_path / "cfg"))


async def test_load_nonexistent_returns_empty_config(store):
    cfg = await store.load(guild_id=999)
    assert isinstance(cfg, ServerConfig)
    assert cfg.guild_id == 999
    assert cfg.list_roles() == {}


async def test_exists_false_for_new_guild(store):
    assert not await store.exists(guild_id=42)


async def test_save_and_load_round_trip(store):
    cfg = ServerConfig(guild_id=42)
    cfg.set_role("mod", 123)
    cfg.set_channel("logs", 456)
    cfg.set_other("prefix", "!")
    await store.save(cfg)

    loaded = await store.load(guild_id=42)
    assert loaded.get_role("mod") == 123
    assert loaded.get_channel("logs") == 456
    assert loaded.get_other("prefix") == "!"


async def test_save_creates_file(store):
    cfg = ServerConfig(guild_id=7)
    await store.save(cfg)
    assert await store.exists(guild_id=7)


async def test_delete_removes_file(store):
    cfg = ServerConfig(guild_id=10)
    await store.save(cfg)
    await store.delete(guild_id=10)
    assert not await store.exists(guild_id=10)


async def test_delete_nonexistent_is_noop(store):
    await store.delete(guild_id=404)  # should not raise


async def test_load_corrupt_file_raises(store, tmp_path):
    path = tmp_path / "cfg" / "1.json"
    path.write_text("not valid json")
    with pytest.raises(RuntimeError, match="Failed to load"):
        await store.load(guild_id=1)


async def test_overwrite_existing_config(store):
    cfg = ServerConfig(guild_id=5)
    cfg.set_role("mod", 1)
    await store.save(cfg)

    cfg.set_role("mod", 999)
    await store.save(cfg)

    loaded = await store.load(guild_id=5)
    assert loaded.get_role("mod") == 999
