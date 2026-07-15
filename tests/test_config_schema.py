"""Tests for ConfigSchema.apply(), PluginConfigManager.get_schema(), and
_apply_schema_fixes() + _doctor_report() config-health checks."""
from __future__ import annotations

import copy
import json
import warnings
from pathlib import Path
from types import SimpleNamespace

import pytest

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


def test_apply_resets_non_int_v_and_migrates() -> None:
    schema = ConfigSchema(key="test", version=2, defaults=_DEFAULTS)

    @schema.migration(from_version=1)
    def _v1_to_v2(s: dict) -> dict:
        return {**s, "migrated": True}

    result, changes = schema.apply({**_DEFAULTS, "_v": "2"})
    assert result["migrated"] is True
    assert result["_v"] == 2
    assert any("invalid _v stamp" in c for c in changes)


def test_apply_warns_on_missing_migration_step(caplog: pytest.LogCaptureFixture) -> None:
    import logging
    schema = ConfigSchema(key="test", version=3, defaults={**_DEFAULTS, "extra": True})

    @schema.migration(from_version=2)
    def _v2_to_v3(s: dict) -> dict:
        return {**s, "extra": True}

    with caplog.at_level(logging.WARNING, logger="easycord"):
        result, _ = schema.apply({**_DEFAULTS, "_v": 1})

    assert result["_v"] == 3
    assert any("no migration registered" in r.message for r in caplog.records)


def test_apply_ignores_forward_version() -> None:
    schema = ConfigSchema(key="test", version=2, defaults=_DEFAULTS)

    @schema.migration(from_version=1)
    def _v1_to_v2(s: dict) -> dict:
        return {**s, "should_not_run": True}

    original = {**_DEFAULTS, "_v": 5, "future_key": "keep_me"}
    result, changes = schema.apply(copy.deepcopy(original))
    assert result == original
    assert changes == []


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


async def test_get_returns_empty_dict_without_overwriting(tmp_path: Path) -> None:
    """get() must not overwrite an explicitly-stored {} with defaults."""
    from easycord.plugins._config_manager import PluginConfigManager

    manager = PluginConfigManager(str(tmp_path / "store"))
    await manager.update(1234, "mykey")  # stores {} (no kwargs)

    result = await manager.get(1234, "mykey", defaults={"enabled": True})
    assert result == {}  # should return the stored {}, NOT the defaults


# ---------------------------------------------------------------------------
# _apply_schema_fixes() — unit tests
# ---------------------------------------------------------------------------


def _make_plugin(store_base: Path | None) -> SimpleNamespace:
    """Minimal fake plugin: config.store._base = store_base (or config=None)."""
    if store_base is None:
        return SimpleNamespace(config=None)
    return SimpleNamespace(config=SimpleNamespace(store=SimpleNamespace(_base=str(store_base))))


def test_apply_schema_fixes_heals_dirty_guilds(tmp_path: Path) -> None:
    from easycord.cli import _apply_schema_fixes

    schema = ConfigSchema(key="myplugin", version=1, defaults=_DEFAULTS)
    store_dir = tmp_path / "store"
    store_dir.mkdir()
    # Section missing 'count' and 'name' — schema.apply will backfill both
    (store_dir / "1234.json").write_text(
        json.dumps({"guild_id": 1234, "other": {"myplugin": {"enabled": False, "_v": 1}}}),
        encoding="utf-8",
    )

    fixed = _apply_schema_fixes([(_make_plugin(store_dir), schema)])

    assert fixed == 1
    healed = json.loads((store_dir / "1234.json").read_text(encoding="utf-8"))
    assert healed["other"]["myplugin"]["count"] == 0
    assert healed["other"]["myplugin"]["name"] == "default"
    assert healed["other"]["myplugin"]["_v"] == 1


def test_apply_schema_fixes_skips_clean_guilds(tmp_path: Path) -> None:
    from easycord.cli import _apply_schema_fixes

    schema = ConfigSchema(key="myplugin", version=1, defaults=_DEFAULTS)
    store_dir = tmp_path / "store"
    store_dir.mkdir()
    (store_dir / "5678.json").write_text(
        json.dumps({"guild_id": 5678, "other": {"myplugin": {**_DEFAULTS, "_v": 1}}}),
        encoding="utf-8",
    )

    fixed = _apply_schema_fixes([(_make_plugin(store_dir), schema)])
    assert fixed == 0


def test_apply_schema_fixes_skips_plugin_without_store() -> None:
    from easycord.cli import _apply_schema_fixes

    schema = ConfigSchema(key="myplugin", version=1, defaults=_DEFAULTS)
    fixed = _apply_schema_fixes([(_make_plugin(None), schema)])
    assert fixed == 0


def test_apply_schema_fixes_warns_on_corrupt_json(tmp_path: Path) -> None:
    from easycord.cli import _apply_schema_fixes

    schema = ConfigSchema(key="myplugin", version=1, defaults=_DEFAULTS)
    store_dir = tmp_path / "store"
    store_dir.mkdir()
    (store_dir / "bad.json").write_text("not valid json", encoding="utf-8")

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        fixed = _apply_schema_fixes([(_make_plugin(store_dir), schema)])

    assert fixed == 0
    assert any(issubclass(warning.category, RuntimeWarning) for warning in w)


# ---------------------------------------------------------------------------
# _doctor_report() config-health checks — filesystem level, no bot target
# ---------------------------------------------------------------------------


def test_doctor_report_detects_leftover_tmp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    ec_root = tmp_path / ".easycord"
    ec_root.mkdir()
    (ec_root / "1234.tmp").write_text("residue", encoding="utf-8")

    from easycord.cli import _doctor_report

    report = _doctor_report()
    assert isinstance(report["checks"], list)
    codes = [c["code"] for c in report["checks"]]
    assert "config.leftover_tmp" in codes
    check = next(c for c in report["checks"] if c["code"] == "config.leftover_tmp")
    assert check["ok"] is False
    assert check["severity"] == "warning"


def test_doctor_report_detects_corrupt_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    ec_root = tmp_path / ".easycord"
    ec_root.mkdir()
    (ec_root / "bad.json").write_text("{ not json", encoding="utf-8")

    from easycord.cli import _doctor_report

    report = _doctor_report()
    assert isinstance(report["checks"], list)
    codes = [c["code"] for c in report["checks"]]
    assert "config.corrupt_json" in codes
    check = next(c for c in report["checks"] if c["code"] == "config.corrupt_json")
    assert check["ok"] is False
    assert check["severity"] == "error"


def test_doctor_report_healthy_config_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    ec_root = tmp_path / ".easycord"
    ec_root.mkdir()
    (ec_root / "1234.json").write_text(json.dumps({"guild_id": 1234}), encoding="utf-8")

    from easycord.cli import _doctor_report

    report = _doctor_report()
    assert isinstance(report["checks"], list)
    codes = [c["code"] for c in report["checks"]]
    assert "config.health" in codes
    check = next(c for c in report["checks"] if c["code"] == "config.health")
    assert check["ok"] is True


def test_doctor_report_no_easycord_dir_omits_config_health(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)  # no .easycord dir here

    from easycord.cli import _doctor_report

    report = _doctor_report()
    assert isinstance(report["checks"], list)
    codes = [c["code"] for c in report["checks"]]
    assert "config.health" not in codes
    assert "config.leftover_tmp" not in codes
    assert "config.corrupt_json" not in codes
