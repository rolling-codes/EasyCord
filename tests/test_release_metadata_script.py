"""Tests for the standalone release metadata checker."""
from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CHECKER_PATH = ROOT / "scripts" / "check_release_metadata.py"
SPEC = importlib.util.spec_from_file_location("check_release_metadata", CHECKER_PATH)
assert SPEC is not None and SPEC.loader is not None
CHECKER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECKER)
collect_errors = CHECKER.collect_errors


def _write_release_tree(root: Path, *, version: str = "1.2.3") -> None:
    (root / "easycord").mkdir()
    (root / "docs").mkdir()
    (root / f"release_v{version}").mkdir()
    (root / "easycord" / "__init__.py").write_text(
        f'__version__ = "{version}"\n',
        encoding="utf-8",
    )
    (root / "pyproject.toml").write_text(
        f"""
        [project]
        name = "easycord"
        version = "{version}"

        [project.urls]
        Download = "https://github.com/rolling-codes/EasyCord/releases/download/v{version}/easycord-{version}-py3-none-any.whl"
        Release = "https://github.com/rolling-codes/EasyCord/releases/tag/v{version}"
        """,
        encoding="utf-8",
    )
    (root / "README.md").write_text(
        f"""
        # EasyCord
        ![Version](https://img.shields.io/badge/v-{version}-blue)
        Install from https://github.com/rolling-codes/EasyCord/releases/download/v{version}/easycord-{version}-py3-none-any.whl
        Release: https://github.com/rolling-codes/EasyCord/releases/tag/v{version}
        """,
        encoding="utf-8",
    )
    (root / "CHANGELOG.md").write_text(
        f"# Changelog\n\n## EasyCord v{version} - Test\n",
        encoding="utf-8",
    )
    (root / "docs" / "getting-started.md").write_text(
        f"https://github.com/rolling-codes/EasyCord/releases/download/v{version}/easycord-{version}-py3-none-any.whl\n",
        encoding="utf-8",
    )
    (root / f"release_v{version}" / "notes.md").write_text(
        f"""
        https://github.com/rolling-codes/EasyCord/releases/download/v{version}/easycord-{version}-py3-none-any.whl
        https://github.com/rolling-codes/EasyCord/releases/download/v{version}/easycord-{version}.tar.gz
        """,
        encoding="utf-8",
    )


def test_release_metadata_checker_passes_consistent_tree(tmp_path) -> None:
    _write_release_tree(tmp_path)

    assert collect_errors(tmp_path) == []


def test_release_metadata_checker_reports_drift(tmp_path) -> None:
    _write_release_tree(tmp_path)
    (tmp_path / "easycord" / "__init__.py").write_text(
        '__version__ = "9.9.9"\n',
        encoding="utf-8",
    )

    errors = collect_errors(tmp_path)

    assert any("easycord.__version__" in error for error in errors)
