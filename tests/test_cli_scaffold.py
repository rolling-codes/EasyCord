"""Regression tests for the ``easycord new`` project scaffold (REQ-02)."""
from __future__ import annotations

import re
import warnings
from pathlib import Path

import pytest

from easycord.cli import _module_name, _write_new_project

# pytest's default collection patterns for test files: test_*.py and *_test.py.
_PYTEST_COLLECT_PATTERN = re.compile(r"^test_.*|.*_test$")


class TestBugs:
    """Regression tests for confirmed bugs — each test names the bug it guards."""

    def test_module_name_renames_test_prefix_and_warns(self) -> None:
        """BUG: _module_name slugged the project name with only a leading-digit
        guard, so a name like "test bot" produced the module ``test_bot`` and the
        scaffold wrote ``plugins/test_bot.py`` — a file pytest collects as a test
        module. Fixed: names matching ``test_*`` are renamed with a clear prefix
        and a warning names both the original and the renamed module.
        """
        with pytest.warns(UserWarning, match=r"test_bot"):
            result = _module_name("test bot")

        assert not _PYTEST_COLLECT_PATTERN.match(result)

    def test_module_name_renames_test_suffix_and_warns(self) -> None:
        """BUG: the same missing guard let ``*_test`` names through — "my test"
        became ``my_test``, matching pytest's ``*_test.py`` collection pattern.
        Fixed: renamed so the result no longer matches, with a warning.
        """
        with pytest.warns(UserWarning, match=r"my_test"):
            result = _module_name("my test")

        assert not _PYTEST_COLLECT_PATTERN.match(result)

    def test_module_name_digit_guard_path_cannot_collide(self) -> None:
        """BUG: the leading-digit guard returned early (``plugin_<slug>``), so a
        name like "1 test" produced ``plugin_1_test`` — still matching pytest's
        ``*_test.py`` pattern. Fixed: the collision guard runs after the digit
        guard.
        """
        with pytest.warns(UserWarning):
            result = _module_name("1 test")

        assert result.startswith("plugin_1")
        assert not _PYTEST_COLLECT_PATTERN.match(result)

    def test_generated_pyproject_scopes_pytest_to_tests_dir(self, tmp_path: Path) -> None:
        """BUG: the generated pyproject's [tool.pytest.ini_options] table only
        set asyncio_mode, so pytest run from the project root collected the
        plugins/ tree too. Fixed: the template gains ``testpaths = ["tests"]``.
        """
        _write_new_project(tmp_path / "proj", "my cool bot", template="plugin")

        pyproject = (tmp_path / "proj" / "pyproject.toml").read_text(encoding="utf-8")

        assert "[tool.pytest.ini_options]" in pyproject
        assert 'asyncio_mode = "auto"' in pyproject
        # Anchored at column 0: proves the added line survives textwrap.dedent
        # with the same indentation as the rest of the template.
        assert re.search(r'^testpaths = \["tests"\]$', pyproject, re.MULTILINE), (
            "testpaths line missing or misaligned after dedent:\n" + pyproject
        )


class TestScaffoldBehavior:
    """Behavioral guarantees for the scaffold beyond the direct bug fixes."""

    def test_normal_name_is_unchanged_and_emits_no_warning(self) -> None:
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            assert _module_name("my cool bot") == "my_cool_bot"

    def test_colliding_scaffold_produces_no_pytest_collectable_plugin_module(
        self, tmp_path: Path
    ) -> None:
        with pytest.warns(UserWarning):
            _write_new_project(tmp_path / "proj", "test bot", template="plugin")

        plugin_files = [
            path
            for path in (tmp_path / "proj" / "plugins").glob("*.py")
            if path.stem != "__init__"
        ]

        assert plugin_files, "scaffold wrote no plugin module"
        for path in plugin_files:
            assert not _PYTEST_COLLECT_PATTERN.match(path.stem), (
                f"generated plugin module {path.name} matches pytest's "
                "test-file collection pattern"
            )
