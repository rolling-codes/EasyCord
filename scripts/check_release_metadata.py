"""Check EasyCord release/version metadata for drift.

This script treats ``pyproject.toml`` as the canonical version source and
verifies that public release references agree with it.
"""
from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path
from typing import Any

try:
    import tomllib
except ImportError:  # Python < 3.11
    import tomli as tomllib  # type: ignore[import-not-found,no-redef]


VERSION_RE = re.compile(r"^\d+\.\d+\.\d+(?:[-.][A-Za-z0-9.]+)?$")


def read_text(root: Path, relative: str) -> str:
    return (root / relative).read_text(encoding="utf-8")


def load_pyproject(root: Path) -> dict[str, Any]:
    return tomllib.loads(read_text(root, "pyproject.toml"))


def load_easycord_version(root: Path) -> str:
    init_path = root / "easycord" / "__init__.py"
    tree = ast.parse(init_path.read_text(encoding="utf-8"), filename=str(init_path))
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(target, ast.Name) and target.id == "__version__" for target in node.targets):
            continue
        if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            return node.value.value
    return ""


def changelog_top_heading(changelog: str) -> str | None:
    for line in changelog.splitlines():
        if line.startswith("## "):
            return line.strip()
    return None


def expected_assets(version: str) -> tuple[str, str, str]:
    tag = f"v{version}"
    wheel = f"easycord-{version}-py3-none-any.whl"
    sdist = f"easycord-{version}.tar.gz"
    return tag, wheel, sdist


def collect_errors(root: Path) -> list[str]:
    root = root.resolve()
    errors: list[str] = []
    pyproject = load_pyproject(root)
    project = pyproject.get("project", {})
    version = str(project.get("version", ""))
    urls = project.get("urls", {})
    tag, wheel, sdist = expected_assets(version)
    release_path = f"releases/download/{tag}"
    wheel_url = f"https://github.com/rolling-codes/EasyCord/{release_path}/{wheel}"
    sdist_url = f"https://github.com/rolling-codes/EasyCord/{release_path}/{sdist}"
    release_url = f"https://github.com/rolling-codes/EasyCord/releases/tag/{tag}"

    if not VERSION_RE.fullmatch(version):
        errors.append(f"pyproject.toml project.version is not semver-like: {version!r}")

    easycord_version = load_easycord_version(root)
    if easycord_version != version:
        errors.append(
            f"easycord.__version__ is {easycord_version!r}, expected {version!r}"
        )

    readme = read_text(root, "README.md")
    changelog = read_text(root, "CHANGELOG.md")
    getting_started = read_text(root, "docs/getting-started.md")
    release_notes_path = root / f"release_{tag}" / "notes.md"
    release_notes = (
        release_notes_path.read_text(encoding="utf-8")
        if release_notes_path.exists()
        else ""
    )

    badge = f"![Version](https://img.shields.io/badge/v-{version}-blue)"
    if badge not in readme:
        errors.append(f"README.md version badge must be {badge!r}")
    if release_url not in readme:
        errors.append(f"README.md must link to {release_url}")
    if wheel_url not in readme and f"{release_path}/{wheel}" not in readme:
        errors.append(f"README.md must mention the wheel install URL for {wheel}")
    if wheel_url not in getting_started and f"{release_path}/{wheel}" not in getting_started:
        errors.append(f"docs/getting-started.md must mention the wheel install URL for {wheel}")

    expected_heading = f"## EasyCord {tag}"
    top_heading = changelog_top_heading(changelog)
    if top_heading is None or not top_heading.startswith(expected_heading):
        errors.append(
            f"CHANGELOG.md top release heading is {top_heading!r}, expected to start with {expected_heading!r}"
        )

    if urls.get("Release") != release_url:
        errors.append(
            f"pyproject.toml project.urls.Release is {urls.get('Release')!r}, expected {release_url!r}"
        )
    if urls.get("Download") != wheel_url:
        errors.append(
            f"pyproject.toml project.urls.Download is {urls.get('Download')!r}, expected {wheel_url!r}"
        )

    if not release_notes:
        errors.append(f"Missing release notes file: release_{tag}/notes.md")
    else:
        for asset_url, asset in ((wheel_url, wheel), (sdist_url, sdist)):
            if asset_url not in release_notes and asset not in release_notes:
                errors.append(f"release_{tag}/notes.md must mention {asset}")

    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        default=Path(__file__).resolve().parents[1],
        type=Path,
        help="Repository root to check.",
    )
    args = parser.parse_args(argv)

    errors = collect_errors(args.root)
    if errors:
        print("Release metadata check failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print("Release metadata check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
