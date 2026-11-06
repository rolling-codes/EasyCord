"""Process boundaries shared by starter scenarios; expectations stay in the tests."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_REPLIES = {
    "minimal": "Pong!", "plugin": "Hello,", "community": "members",
    "ai": "No AI provider", "database": "No note saved.",
}


def starter_env(*, pythonpath: Path = ROOT, **settings: str) -> dict[str, str]:
    environment = {
        key: value for key, value in os.environ.items()
        if not key.startswith(("DISCORD_", "EASYCORD_")) and key != "PYTHONPATH"
    }
    environment.update(settings)
    environment["PYTHONPATH"] = str(pythonpath)
    return environment


def run_command(project: Path, command: list[str], *, env=None, check=True, timeout=30):
    result = subprocess.run(
        command, cwd=project, env=env, capture_output=True, text=True,
        timeout=timeout, check=False,
    )
    if check:
        assert result.returncode == 0, result.stdout + result.stderr
    return result


def run_python(project: Path, code: str, *, check=True, isolated=False, **settings: str):
    return run_command(
        project, [sys.executable, *(["-I"] if isolated else []), "-c", code],
        env=starter_env(**settings), check=check,
    )


def clean_source_copy(dest: Path) -> Path:
    """Copy the framework without build output so stale files cannot enter a wheel."""
    shutil.copytree(ROOT, dest, ignore=shutil.ignore_patterns(
        ".git", "build", "dist", "*.egg-info", "__pycache__", ".venv", ".pytest_cache"))
    return dest


def install_wheels(projects: list[Path], wheels: Path, target: Path) -> None:
    """Build local artifacts without resolving dependencies over the network."""
    run_command(wheels.parent, [
        sys.executable, "-m", "pip", "wheel", "--no-index", "--no-deps",
        "--no-build-isolation", "--wheel-dir", str(wheels), *map(str, projects),
    ], timeout=60)
    run_command(wheels.parent, [
        sys.executable, "-m", "pip", "install", "--no-index", "--no-deps",
        "--target", str(target), *map(str, sorted(wheels.glob("*.whl"))),
    ])
