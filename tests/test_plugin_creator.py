"""Tests for EasyCord plugin creator helpers."""
from __future__ import annotations

import importlib
import json
import sys
from importlib.metadata import EntryPoint
from pathlib import Path

import pytest

from easycord import Bot, Plugin
from easycord.plugin_creator import (
    PluginCheck,
    PluginCheckReport,
    PluginManifest,
    PluginScaffoldOptions,
    PluginScaffoldResult,
    check_plugin_project,
    create_in_project_plugin,
    create_package_plugin,
    create_plugin_scaffold,
    discover_plugins,
    load_entrypoint_plugins,
    load_plugin_manifest,
    validate_plugin_manifest,
)
from easycord.testing import invoke


class EntryPointPlugin(Plugin):
    pass


def _manifest_data(**overrides) -> dict:
    data = {
        "schema_version": 1,
        "name": "greetings",
        "version": "0.1.0",
        "description": "Greeting commands",
        "author": "EasyCord Tests",
        "module": "plugins.greetings",
        "class": "GreetingsPlugin",
        "easycord": ">=5.40.2",
        "python": ">=3.10",
        "commands": [{"name": "hello", "type": "slash"}],
    }
    data.update(overrides)
    return data


def _write_manifest(target: Path, **overrides) -> Path:
    path = target / "easycord-plugin.json"
    path.write_text(json.dumps(_manifest_data(**overrides)), encoding="utf-8")
    return path


def test_manifest_loads_and_validates_valid_file(tmp_path: Path) -> None:
    manifest_path = _write_manifest(tmp_path)

    manifest = load_plugin_manifest(manifest_path)
    report = validate_plugin_manifest(manifest)

    assert isinstance(manifest, PluginManifest)
    assert manifest.name == "greetings"
    assert manifest.version == "0.1.0"
    assert manifest.module == "plugins.greetings"
    assert manifest.class_name == "GreetingsPlugin"
    assert manifest.class_target == "plugins.greetings:GreetingsPlugin"
    assert isinstance(report, PluginCheckReport)
    assert report.ok is True
    assert all(isinstance(check, PluginCheck) for check in report.checks)


@pytest.mark.parametrize(
    ("overrides", "expected_code"),
    [
        ({"name": ""}, "manifest.name"),
        ({"module": ""}, "manifest.module"),
        ({"class": "not-a-class"}, "manifest.class"),
        ({"version": "soon"}, "manifest.version.format"),
    ],
)
def test_manifest_validation_reports_invalid_files(
    tmp_path: Path,
    overrides: dict,
    expected_code: str,
) -> None:
    manifest_path = _write_manifest(tmp_path, **overrides)

    report = validate_plugin_manifest(load_plugin_manifest(manifest_path))

    assert report.ok is False
    assert any(check.code == expected_code and check.ok is False for check in report.checks)


def test_in_project_scaffold_creates_local_safe_plugin(tmp_path: Path) -> None:
    result = create_in_project_plugin("greetings", tmp_path)

    assert isinstance(result, PluginScaffoldResult)
    assert result.mode == "in-project"
    assert result.manifest.name == "greetings"
    assert tmp_path / "plugins" / "greetings.py" in result.written
    assert tmp_path / "plugins" / "greetings.easycord-plugin.json" in result.written
    assert tmp_path / "tests" / "test_greetings.py" in result.written

    plugin_source = (tmp_path / "plugins" / "greetings.py").read_text(encoding="utf-8")
    test_source = (tmp_path / "tests" / "test_greetings.py").read_text(encoding="utf-8")

    assert "class GreetingsPlugin(Plugin):" in plugin_source
    assert '@slash_command(description="Say hello")' in plugin_source
    assert "ctx.respond" in plugin_source
    assert 'Bot(auto_sync=False, db_backend="memory")' in test_source
    assert "DISCORD_TOKEN" not in test_source


def test_package_scaffold_declares_easycord_plugin_entry_point(tmp_path: Path) -> None:
    result = create_package_plugin("greetings", tmp_path)

    pyproject = (tmp_path / "pyproject.toml").read_text(encoding="utf-8")
    assert result.mode == "package"
    assert result.manifest.class_target == "easycord_greetings.plugin:GreetingsPlugin"
    assert tmp_path / "easycord_greetings" / "plugin.py" in result.written
    assert '[project.entry-points."easycord.plugins"]' in pyproject
    assert 'greetings = "easycord_greetings.plugin:GreetingsPlugin"' in pyproject
    assert 'Bot(auto_sync=False, db_backend="memory")' in (
        tmp_path / "tests" / "test_greetings.py"
    ).read_text(encoding="utf-8")


def test_create_plugin_scaffold_dispatches_by_mode(tmp_path: Path) -> None:
    in_project = create_plugin_scaffold(
        PluginScaffoldOptions("utility pack", tmp_path / "app", mode="in-project")
    )
    package = create_plugin_scaffold(
        PluginScaffoldOptions("utility pack", tmp_path / "dist", mode="package")
    )

    assert in_project.mode == "in-project"
    assert tmp_path / "app" / "plugins" / "utility_pack.py" in in_project.written
    assert package.mode == "package"
    assert tmp_path / "dist" / "easycord_utility_pack" / "plugin.py" in package.written


async def test_generated_in_project_plugin_registers_and_invokes(
    tmp_path: Path,
    monkeypatch,
) -> None:
    create_in_project_plugin("greetings", tmp_path)
    monkeypatch.syspath_prepend(str(tmp_path))
    importlib.invalidate_caches()

    module = importlib.import_module("plugins.greetings")
    plugin_cls = getattr(module, "GreetingsPlugin")
    bot = Bot(auto_sync=False, db_backend="memory")
    try:
        bot.add_plugin(plugin_cls())
        ctx = await invoke(bot, "hello")
        assert ctx.response_count == 1
        assert "Hello" in (ctx.last_response or "")
    finally:
        await bot.close()
        sys.modules.pop("plugins.greetings", None)
        sys.modules.pop("plugins", None)
        importlib.invalidate_caches()


def test_check_plugin_project_reports_generated_layout(tmp_path: Path) -> None:
    create_in_project_plugin("greetings", tmp_path)

    report = check_plugin_project(tmp_path)

    assert report.ok is True
    assert {check.code for check in report.checks} >= {
        "manifest.name",
        "manifest.module",
        "manifest.class",
        "project.module",
    }


def test_check_plugin_project_reports_missing_manifest(tmp_path: Path) -> None:
    report = check_plugin_project(tmp_path)

    assert report.ok is False
    assert any(check.code == "project.manifest" and check.ok is False for check in report.checks)


def test_check_plugin_project_reports_malformed_manifest(tmp_path: Path) -> None:
    (tmp_path / "easycord-plugin.json").write_text("{not-json", encoding="utf-8")

    report = check_plugin_project(tmp_path)

    assert report.ok is False
    assert any(check.code == "manifest.load" and check.ok is False for check in report.checks)


def test_discover_plugins_uses_mocked_metadata_entry_points(
    monkeypatch,
    fake_entry_points,
) -> None:
    entry_point = EntryPoint(
        name="entrypoint-plugin",
        value=f"{__name__}:EntryPointPlugin",
        group="easycord.plugins",
    )

    monkeypatch.setattr(
        "easycord.plugin_creator.metadata.entry_points",
        fake_entry_points(entry_point),
    )

    discovered = discover_plugins()

    assert discovered == [
        {
            "name": "entrypoint-plugin",
            "value": f"{__name__}:EntryPointPlugin",
            "group": "easycord.plugins",
            "distribution": None,
        }
    ]


def test_load_entrypoint_plugins_uses_mocked_metadata_entry_points(
    monkeypatch,
    fake_entry_points,
) -> None:
    entry_point = EntryPoint(
        name="entrypoint-plugin",
        value=f"{__name__}:EntryPointPlugin",
        group="easycord.plugins",
    )

    monkeypatch.setattr(
        "easycord.plugin_creator.metadata.entry_points",
        fake_entry_points(entry_point),
    )

    loaded = load_entrypoint_plugins()

    assert len(loaded) == 1
    assert isinstance(loaded[0], EntryPointPlugin)


def test_scaffold_refuses_to_overwrite_existing_files(tmp_path: Path) -> None:
    create_in_project_plugin("greetings", tmp_path)

    with pytest.raises(FileExistsError):
        create_in_project_plugin("greetings", tmp_path)


def test_scaffold_result_has_serializable_fields(tmp_path: Path) -> None:
    result = create_in_project_plugin("greetings", tmp_path)

    payload = {
        "mode": result.mode,
        "target": str(result.target),
        "manifest": result.manifest.to_dict(),
        "written": [str(path) for path in result.written],
    }

    assert json.loads(json.dumps(payload))["manifest"]["name"] == "greetings"
