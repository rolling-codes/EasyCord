"""Tests for ConfigSchema.apply() and PluginConfigManager.get_schema()."""
from __future__ import annotations

import copy
from pathlib import Path

from easycord.config_schema import ConfigSchema


_DEFAULTS: dict = {"enabled": True, "count": 0, "name": "default"}


# ---------------------------------------------------------------------------
# ConfigSchema.apply() — unit tests (pure, no I/O)
# ---------------------------------------------------------------------------


def test_apply_absent_section_returns_defaults() -> None:
    schema = ConfigSchema(key="test", version=1, defaults=_DEFAULTS)
    result, changes = schema.apply(None)
    assert result["enabled"] is True
    assert result["count"] == 0
    assert result["name"] == "default"
    assert result["_v"] == 1
    assert changes  # something reported


def test_apply_empty_dict_returns_defaults() -> None:
    schema = ConfigSchema(key="test", version=1, defaults=_DEFAULTS)
    result, changes = schema.apply({})
    assert result == {**_DEFAULTS, "_v": 1}
    assert changes


def test_apply_clean_section_returns_no_changes() -> None:
    schema = ConfigSchema(key="test", version=1, defaults=_DEFAULTS)
    existing = {**_DEFAULTS, "_v": 1}
    result, changes = schema.apply(existing)
    assert result["enabled"] is True
    assert not changes  # already valid — nothing to heal


def test_apply_backfills_missing_keys() -> None:
    schema = ConfigSchema(key="test", version=1, defaults=_DEFAULTS)
    # count and name are absent
    result, changes = schema.apply({"enabled": False, "_v": 1})
    assert result["enabled"] is False          # existing value preserved
    assert result["count"] == 0               # backfilled
    assert result["name"] == "default"        # backfilled
    assert any("count" in c for c in changes)
    assert any("name" in c for c in changes)


def test_apply_preserves_unknown_keys() -> None:
    schema = ConfigSchema(key="test", version=1, defaults=_DEFAULTS)
    existing = {**_DEFAULTS, "_v": 1, "custom": "keep_me"}
    result, _ = schema.apply(existing)
    assert result["custom"] == "keep_me"


def test_apply_replaces_non_dict_with_defaults() -> None:
    schema = ConfigSchema(key="test", version=1, defaults=_DEFAULTS)
    result, changes = schema.apply("not a dict")  # type: ignore[arg-type]
    assert result == {**_DEFAULTS, "_v": 1}
    assert changes


def test_apply_is_pure_no_side_effects() -> None:
    schema = ConfigSchema(key="test", version=1, defaults=_DEFAULTS)
    original: dict = {"enabled": False, "_v": 1}
    snapshot = copy.deepcopy(original)
    schema.apply(original)
    assert original == snapshot  # apply must never mutate the input dict


def test_apply_treats_missing_v_as_version_1() -> None:
    """A section with no _v stamp is pre-schema and treated as version 1."""
    schema = ConfigSchema(
        key="test", version=2, defaults={**_DEFAULTS, "extra": True}
    )

    @schema.migration(from_version=1)
    def _v1_to_v2(s: dict) -> dict:
        return {**s, "extra": True}

    # Section at v1 with no version stamp
    result, _ = schema.apply(dict(_DEFAULTS))
    assert result["extra"] is True
    assert result["_v"] == 2


def test_apply_runs_migration_chain() -> None:
    schema = ConfigSchema(
        key="test", version=3, defaults={**_DEFAULTS, "new_v3": "hi"}
    )

    @schema.migration(from_version=1)
    def _v1_to_v2(s: dict) -> dict:
        return {**s, "_migrated_v1": True}

    @schema.migration(from_version=2)
    def _v2_to_v3(s: dict) -> dict:
        return {**s, "_migrated_v2": True}

    result, changes = schema.apply({**_DEFAULTS, "_v": 1})
    assert result["_migrated_v1"] is True
    assert result["_migrated_v2"] is True
    assert result["_v"] == 3
    migration_changes = [c for c in changes if "migrated" in c]
    assert len(migration_changes) == 2


# ---------------------------------------------------------------------------
# PluginConfigManager.get_schema() — integration tests (uses real store)
# ---------------------------------------------------------------------------


async def test_get_schema_heals_and_persists(tmp_path: Path) -> None:
    """get_schema() heals a section with missing keys and persists the fix."""
    from easycord.plugins._config_manager import PluginConfigManager

    schema = ConfigSchema(key="myplugin", version=1, defaults=_DEFAULTS)
    manager = PluginConfigManager(str(tmp_path / "store"))

    # Seed an incomplete section (missing count and name)
    await manager.update(1234, "myplugin", enabled=False)

    result = await manager.get_schema(1234, schema)
    assert result["enabled"] is False   # preserved
    assert result["count"] == 0         # backfilled
    assert result["name"] == "default"  # backfilled
    assert result["_v"] == 1

    # Verify the healed section was actually persisted to disk
    raw = await manager.get(1234, "myplugin")
    assert raw.get("count") == 0
    assert raw.get("_v") == 1


async def test_get_schema_fast_path_skips_mutate_when_clean(tmp_path: Path) -> None:
    """get_schema() on an already-healed section never calls store.mutate."""
    from easycord.plugins._config_manager import PluginConfigManager

    schema = ConfigSchema(key="myplugin", version=1, defaults=_DEFAULTS)
    manager = PluginConfigManager(str(tmp_path / "store"))

    # Seed a fully-healed section (all keys + _v stamp present)
    await manager.update(1234, "myplugin", **{**_DEFAULTS, "_v": 1})

    # Patch store.mutate to count calls
    mutate_calls = 0
    original_mutate = manager.store.mutate

    async def _counting_mutate(guild_id: int, fn):  # type: ignore[no-untyped-def]
        nonlocal mutate_calls
        mutate_calls += 1
        return await original_mutate(guild_id, fn)

    manager.store.mutate = _counting_mutate  # type: ignore[method-assign]

    result = await manager.get_schema(1234, schema)
    assert result["enabled"] is True
    assert mutate_calls == 0  # fast path — no write triggered
