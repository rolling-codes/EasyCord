#!/usr/bin/env python3
"""EasyCord development setup script.

Run this once after cloning to get a working development environment.

Usage:
    python install.py          # interactive
    python install.py --yes    # non-interactive, skip optional prompts
    python install.py --skip-tests  # skip the test run
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

MIN_PYTHON = (3, 10)
VENV_DIR = Path("venv")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _banner() -> None:
    print()
    print("=" * 60)
    print(" EasyCord -- development setup")
    print("=" * 60)


def _step(msg: str) -> None:
    print(f"\n-> {msg}")


def _ok(msg: str) -> None:
    print(f"   OK  {msg}")


def _warn(msg: str) -> None:
    print(f"   !!  {msg}")


def _fail(msg: str) -> None:
    print(f"\nERROR: {msg}")
    sys.exit(1)


def _run(cmd: list[str], *, check: bool = True) -> subprocess.CompletedProcess:
    """Run a subprocess, streaming output, raising on failure."""
    print(f"   $ {' '.join(str(c) for c in cmd)}")
    result = subprocess.run(cmd, check=False)
    if check and result.returncode != 0:
        _fail(f"Command failed with exit code {result.returncode}")
    return result


# ---------------------------------------------------------------------------
# Steps
# ---------------------------------------------------------------------------

def check_python() -> None:
    _step("Checking Python version")
    version = sys.version_info[:2]
    if version < MIN_PYTHON:
        _fail(
            f"Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]}+ is required "
            f"(you have {version[0]}.{version[1]}). "
            "Download a newer release from https://python.org"
        )
    _ok(f"Python {version[0]}.{version[1]} found")


def create_venv() -> None:
    _step("Setting up virtual environment")
    if VENV_DIR.exists():
        _ok(f"{VENV_DIR} already exists -- skipping creation")
        return
    _run([sys.executable, "-m", "venv", str(VENV_DIR)])
    _ok(f"Virtual environment created at {VENV_DIR}/")


def _pip() -> Path:
    """Return the pip executable inside the venv."""
    if os.name == "nt":
        return VENV_DIR / "Scripts" / "pip.exe"
    return VENV_DIR / "bin" / "pip"


def _pytest() -> Path:
    """Return the pytest executable inside the venv."""
    if os.name == "nt":
        return VENV_DIR / "Scripts" / "pytest.exe"
    return VENV_DIR / "bin" / "pytest"


def install_deps() -> None:
    _step("Installing EasyCord in editable mode with dev dependencies")
    pip = _pip()
    _run([str(pip), "install", "--upgrade", "pip"], check=False)
    _run([str(pip), "install", "-e", ".[dev]"])
    _ok("Dependencies installed")


def run_tests(*, yes: bool) -> None:
    _step("Running tests")
    if not yes:
        try:
            answer = input("   Run the test suite now? [y/N] ").strip().lower()
        except EOFError:
            answer = "n"
        if answer != "y":
            print("   Skipped.")
            return
    result = _run([str(_pytest()), "--tb=short", "-q"], check=False)
    if result.returncode == 0:
        _ok("All tests passed")
    else:
        _warn("Some tests failed -- see output above")


def print_next_steps() -> None:
    print()
    print("=" * 60)
    print(" EasyCord is ready!")
    print("=" * 60)
    print()
    print(" Activate your environment:")
    if os.name == "nt":
        print("   .\\venv\\Scripts\\activate")
    else:
        print("   source venv/bin/activate")
    print()
    print(" Create a new bot project:")
    print("   easycord new my-bot")
    print()
    print(" Check your setup at any time:")
    print("   easycord doctor")
    print()
    print(" Full docs:")
    print("   https://github.com/rolling-codes/EasyCord")
    print()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="EasyCord development setup")
    parser.add_argument(
        "--yes", "-y",
        action="store_true",
        help="Non-interactive: skip optional prompts and accept defaults",
    )
    parser.add_argument(
        "--skip-tests",
        action="store_true",
        help="Skip the optional test run at the end",
    )
    args = parser.parse_args()

    _banner()
    check_python()
    create_venv()
    install_deps()

    if not args.skip_tests:
        run_tests(yes=args.yes)

    print_next_steps()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nSetup aborted.")
        sys.exit(0)
