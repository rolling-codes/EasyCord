"""Bump EasyCord's version across all files that check_release_metadata.py validates.

Usage:
    python scripts/bump_version.py 5.50.0
    python scripts/bump_version.py 5.50.0 --dry-run
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

VERSION_RE = re.compile(r"^\d+\.\d+\.\d+(?:[-.][A-Za-z0-9.]+)?$")
ROOT = Path(__file__).resolve().parents[1]
GITHUB_REPO = "https://github.com/rolling-codes/EasyCord"


def _asset_urls(version: str) -> dict[str, str]:
    tag = f"v{version}"
    base = f"{GITHUB_REPO}/releases/download/{tag}"
    wheel = f"easycord-{version}-py3-none-any.whl"
    sdist = f"easycord-{version}.tar.gz"
    return {
        "tag": tag,
        "wheel": wheel,
        "sdist": sdist,
        "wheel_url": f"{base}/{wheel}",
        "sdist_url": f"{base}/{sdist}",
        "release_url": f"{GITHUB_REPO}/releases/tag/{tag}",
    }


def _current_version() -> str:
    pyproject = ROOT / "pyproject.toml"
    for line in pyproject.read_text(encoding="utf-8").splitlines():
        m = re.match(r'^version\s*=\s*"([^"]+)"', line.strip())
        if m:
            return m.group(1)
    raise RuntimeError("Could not find version in pyproject.toml")


def _replace_all(text: str, old: str, new: str) -> str:
    return text.replace(old, new)


def bump(new_version: str, *, dry_run: bool = False) -> int:
    if not VERSION_RE.fullmatch(new_version):
        print(f"Error: {new_version!r} is not a valid semver string.", file=sys.stderr)
        return 1

    old_version = _current_version()
    if old_version == new_version:
        print(f"Already at {new_version}; nothing to do.")
        return 0

    old = _asset_urls(old_version)
    new = _asset_urls(new_version)

    substitutions: list[tuple[str, str]] = [
        (old_version, new_version),
        (old["tag"], new["tag"]),
        (old["wheel"], new["wheel"]),
        (old["sdist"], new["sdist"]),
        (old["wheel_url"], new["wheel_url"]),
        (old["sdist_url"], new["sdist_url"]),
        (old["release_url"], new["release_url"]),
    ]

    targets = [
        ROOT / "pyproject.toml",
        ROOT / "easycord" / "__init__.py",
        ROOT / "README.md",
        ROOT / "docs" / "getting-started.md",
    ]

    changed: list[tuple[Path, str]] = []
    for path in targets:
        original = path.read_text(encoding="utf-8")
        updated = original
        for old_str, new_str in substitutions:
            updated = _replace_all(updated, old_str, new_str)
        if updated != original:
            changed.append((path, updated))

    if not changed:
        print(f"No version strings found for {old_version!r} in tracked files.")
        return 1

    if dry_run:
        for path, _ in changed:
            print(f"  would update: {path.relative_to(ROOT)}")
        return 0

    for path, content in changed:
        path.write_text(content, encoding="utf-8")
        print(f"  updated: {path.relative_to(ROOT)}")

    # Validate immediately so the caller knows if anything was missed
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "check_release_metadata.py")],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print("\ncheck_release_metadata.py found issues after bump:", file=sys.stderr)
        print(result.stderr, file=sys.stderr)
        return result.returncode

    print(f"\nBumped {old_version} → {new_version}. Metadata check passed.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("version", help="New version string, e.g. 5.50.0")
    parser.add_argument("--dry-run", action="store_true", help="Show what would change without writing")
    args = parser.parse_args(argv)
    return bump(args.version, dry_run=args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
