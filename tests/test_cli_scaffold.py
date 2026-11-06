"""Regression tests for the ``easycord new`` project scaffold (REQ-02)."""
from __future__ import annotations

import re
import shlex
import sys
import warnings
from pathlib import Path

import pytest
from starter_helpers import EXPECTED_REPLIES, run_command, run_python, starter_env

from easycord.cli import _module_name, _write_new_project

# pytest's default collection patterns for test files: test_*.py and *_test.py.
_PYTEST_COLLECT_PATTERN = re.compile(r"^test_.*|.*_test$")


@pytest.mark.parametrize("template", ["minimal", "plugin", "community", "ai", "database"])
def test_starter_documented_offline_workflow(tmp_path, template):
    """Exercise the generated README command and tests in a fresh process."""
    project = tmp_path / "starter"
    _write_new_project(project, "starter", template=template)
    readme = (project / "README.md").read_text()
    command = re.search(r"^easycord try (.+)$", readme, re.MULTILINE).group(1)
    result = run_command(project,
        [sys.executable, "-c", "from easycord.cli import main; raise SystemExit(main())",
         "try", *shlex.split(command)], env=starter_env(),
    )
    assert EXPECTED_REPLIES[template] in result.stdout
    assert not (project / "data").exists()
    run_command(project, [sys.executable, "-m", "pytest", "-q"], env=starter_env())
    assert not (project / "data").exists()


@pytest.mark.parametrize("template", ["minimal", "plugin", "community", "ai", "database"])
def test_starter_live_launch_uses_guild_sync_and_sqlite(tmp_path, template):
    """Intercept run() to verify launch configuration without contacting Discord."""
    project = tmp_path / "starter"
    _write_new_project(project, "starter", template=template)
    code = '''
import asyncio
from pathlib import Path
from easycord import Bot, MemoryDatabase, SQLiteDatabase
import bot
assert isinstance(bot.bot.db, MemoryDatabase)
assert not bot.bot._auto_sync
launches = []

def fake_run(instance, token):
    launches.append(token)
    assert token == "offline-test-token"
    assert instance._auto_sync
    assert instance._sync_guild_id == 123456789
    assert isinstance(instance.db, SQLiteDatabase)
    assert Path(instance.db.path) == Path("data/bot.db")
    def command_names(app):
        return {item["name"] for item in app.inspect_interactions()["slash"]}
    assert command_names(instance) == command_names(bot.bot)
    asyncio.run(instance.close())

Bot.run = fake_run
bot.main()
assert launches == ["offline-test-token"], "the starter must launch exactly once"
asyncio.run(bot.bot.close())
'''
    run_python(project, code, DISCORD_TOKEN="offline-test-token", DISCORD_GUILD_ID="123456789")


@pytest.mark.parametrize(
    ("settings", "message"),
    [({}, "DISCORD_TOKEN"), ({"DISCORD_TOKEN": "test"}, "DISCORD_GUILD_ID"),
     ({"DISCORD_TOKEN": "test", "DISCORD_GUILD_ID": "oops"}, "must be an integer")],
)
def test_starter_launch_explains_missing_configuration(tmp_path, settings, message):
    project = tmp_path / "starter"
    _write_new_project(project, "starter", template="minimal")
    result = run_command(
        project, [sys.executable, "bot.py"], env=starter_env(**settings), check=False,
    )
    assert result.returncode != 0
    assert message in result.stderr
    assert "Traceback" not in result.stderr
    assert not (project / "data").exists()


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
