"""Exercise starter projects as users modify, name, and distribute them."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from starter_helpers import (
    EXPECTED_REPLIES,
    ROOT,
    install_wheels,
    run_command,
    run_python,
    starter_env,
)

from easycord.cli import _write_new_project, main


@pytest.mark.parametrize("template", ["plugin", "ai", "database"])
@pytest.mark.parametrize("name", ["class", "await", "my bot", "123-bot", "test bot", "__init__"])
def test_accepted_project_names_produce_invokable_commands(tmp_path, template, name):
    """A successful scaffold must run, even when its name needs normalization."""
    project = tmp_path / name
    _write_new_project(project, name, template=template)
    command, kwargs = {
        "plugin": ("hello", {}),
        "ai": ("ask", {"prompt": "hello"}),
        "database": ("get_note", {}),
    }[template]
    run_python(project, f'''
import asyncio
from bot import create_bot
from easycord.testing import invoke

async def check():
    bot = create_bot()
    try:
        response = await invoke(bot, {command!r}, **{kwargs!r})
        response.assert_contains({EXPECTED_REPLIES[template]!r})
    finally:
        await bot.close()

asyncio.run(check())
''')


def test_documented_user_command_edit_reaches_every_bot_instance(tmp_path):
    """The guide's edit must affect behavior in both offline and live factories."""
    project = tmp_path / "edited"
    _write_new_project(project, "edited", template="minimal")
    path = project / "bot.py"
    path.write_text(path.read_text().replace("    return bot", '''
    @bot.slash(description="Say hello")
    async def hello(ctx):
        await ctx.respond(f"Hello, {ctx.user.display_name}!")

    return bot''', 1))
    run_python(project, '''
import asyncio
from bot import bot, create_bot
from easycord.testing import invoke

async def check():
    configured = create_bot(auto_sync=True, sync_guild_id=123456789)
    try:
        for instance in (bot, configured):
            reply = await invoke(instance, "hello")
            reply.assert_contains("Hello,")
            original = await invoke(instance, "ping")
            original.assert_content("Pong!")
    finally:
        await bot.close()
        await configured.close()

asyncio.run(check())
''')


@pytest.mark.skipif(os.name == "nt", reason="Checks the emitted POSIX shell command")
def test_printed_next_step_enters_project_with_spaces(tmp_path, capsys):
    """A working project still needs copyable instructions for its actual path."""
    project = tmp_path / "my community bot"
    assert main(["new", str(project), "--template", "minimal"]) == 0
    output = capsys.readouterr().out
    enter = next(line.strip() for line in output.splitlines() if line.startswith("  cd "))
    result = run_command(tmp_path,
        ["sh", "-c", enter + " && pwd -P"], timeout=10,
    )
    assert Path(result.stdout.strip()) == project.resolve()


@pytest.mark.parametrize("template", ["minimal", "plugin", "community", "ai", "database"])
def test_installed_wheel_runs_outside_generated_source_tree(tmp_path, template):
    """Source imports can hide missing wheel files; invoke only installed files."""
    project = tmp_path / "source"
    _write_new_project(project, "distributed", template=template)
    installed = tmp_path / "installed"
    install_wheels([project], tmp_path / "wheels", installed)
    outside = tmp_path / "outside"
    outside.mkdir()
    command, kwargs = {
        "minimal": ("ping", {}), "plugin": ("hello", {}), "community": ("info", {}),
        "ai": ("ask", {"prompt": "hello"}), "database": ("get_note", {}),
    }[template]
    code = f'''
import asyncio
import sys
from pathlib import Path
sys.path.insert(0, {str(installed)!r})
import bot
from easycord.testing import invoke
assert Path(bot.__file__).parent == Path({str(installed)!r})

async def check():
    try:
        response = await invoke(bot.bot, {command!r}, **{kwargs!r})
        response.assert_contains({EXPECTED_REPLIES[template]!r})
    finally:
        await bot.bot.close()

asyncio.run(check())
'''
    # Isolated mode prevents the source directory/PYTHONPATH masking wheel omissions.
    run_python(outside, code, isolated=True)


@pytest.mark.skipif(os.name == "nt", reason="Checks the installed POSIX console script")
def test_installed_framework_console_script_invokes_installed_bot(tmp_path):
    """Install both wheels and run the shipped entrypoint without checkout imports."""
    project = tmp_path / "source"
    _write_new_project(project, "distributed", template="minimal")
    site = tmp_path / "site"
    install_wheels([ROOT, project], tmp_path / "wheels", site)
    outside = tmp_path / "outside"
    outside.mkdir()
    env = starter_env(pythonpath=site)
    run_command(outside,
        [sys.executable, "-c", f'''
from pathlib import Path
import easycord
import bot
site = Path({str(site)!r})
assert Path(easycord.__file__).is_relative_to(site)
assert Path(bot.__file__).is_relative_to(site)
'''],
        env=env,
    )
    result = run_command(outside,
        [str(site / "bin" / "easycord"), "try", "bot:bot", "ping"], env=env,
    )
    assert "Pong!" in result.stdout
