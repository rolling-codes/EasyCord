#!/usr/bin/env python3
"""
Release consistency validator for EasyCord.

Checks:
- No stale version references
- Install commands are consistent
- No development files in distribution
- Package metadata aligned
- Release documentation complete

Usage:
  python check_release_consistency.py          # uses version from pyproject.toml
  python check_release_consistency.py --version 4.5.0-beta.1
"""
import argparse
import re
import sys
import tarfile
import zipfile
from pathlib import Path


def read_version_from_pyproject(repo_root: Path) -> str | None:
    """Extract version from pyproject.toml."""
    pyproject = repo_root / "pyproject.toml"
    if not pyproject.exists():
        return None

    content = pyproject.read_text(encoding="utf-8", errors="replace")
    match = re.search(r'version\s*=\s*"([^"]+)"', content)
    if match:
        return match.group(1)
    return None


def check_version_consistency(repo_root: Path, expected_version: str) -> list[str]:
    """Verify all version references match expected version."""
    errors = []

    # Check pyproject.toml
    pyproject = repo_root / "pyproject.toml"
    content = pyproject.read_text(encoding="utf-8", errors="replace")
    if f'version = "{expected_version}"' not in content:
        errors.append(f"pyproject.toml: version not set to {expected_version}")

    # Check README
    readme = repo_root / "README.md"
    if readme.exists():
        content = readme.read_text(encoding="utf-8", errors="replace")
        if f"v{expected_version}" not in content:
            errors.append(f"README.md: missing v{expected_version} reference")
        if "@v4.3" in content or "@v4.2" in content:
            errors.append(f"README.md: contains stale version tags (@v4.3, @v4.2)")

    # Check docs (only install-related docs require specific version)
    docs_dir = repo_root / "docs"
    for doc in docs_dir.glob("*.md"):
        if doc.name in ["getting-started.md", "quickstart-production.md"]:
            content = doc.read_text(encoding="utf-8", errors="replace")
            if f"v{expected_version}" not in content:
                errors.append(f"{doc.name}: missing v{expected_version} reference")

    return errors


def check_distribution_hygiene(archive_path: Path) -> list[str]:
    """Verify release archive doesn't contain development files."""
    errors = []

    excluded_names = {
        "CLAUDE.md",
        "AGENTS.md",
        "MODEL_CONTEXT.md",
        ".coderabbit.yaml",
        ".claude",
        ".worktrees",
        ".github",
        ".git",
        "tests",
    }

    try:
        with tarfile.open(archive_path, "r:gz") as tar:
            for member in tar.getmembers():
                parts = Path(member.name).parts
                basename = parts[-1] if parts else member.name
                if basename in excluded_names or any(part in excluded_names for part in parts):
                    errors.append(
                        f"Distribution archive contains development file: {member.name}"
                    )
    except Exception as e:
        errors.append(f"Could not read archive {archive_path}: {e}")

    return errors


def check_wheel_hygiene(wheel_path: Path) -> list[str]:
    """Verify release wheel contains package/runtime files only."""
    errors = []
    excluded_prefixes = (
        ".github/",
        ".worktrees/",
        ".claude/",
        "tests/",
    )
    excluded_names = {
        "CLAUDE.md",
        "AGENTS.md",
        "MODEL_CONTEXT.md",
        ".coderabbit.yaml",
    }

    try:
        with zipfile.ZipFile(wheel_path) as wheel:
            for name in wheel.namelist():
                normalized = name.replace("\\", "/")
                basename = Path(normalized).name
                if basename in excluded_names or normalized.startswith(excluded_prefixes):
                    errors.append(f"Wheel contains development file: {name}")
    except Exception as e:
        errors.append(f"Could not read wheel {wheel_path}: {e}")

    return errors


def check_manifest_in(repo_root: Path) -> list[str]:
    """Verify MANIFEST.in excludes development files."""
    errors = []
    manifest = repo_root / "MANIFEST.in"
    content = manifest.read_text(encoding="utf-8", errors="replace")

    required_excludes = [
        "exclude .claude",
        "exclude .worktrees",
        "exclude .coderabbit.yaml",
        "exclude CLAUDE.md",
        "exclude AGENTS.md",
        "prune tests",
    ]

    for exclude in required_excludes:
        if exclude not in content:
            errors.append(f"MANIFEST.in: missing '{exclude}'")

    # Check that CLAUDE.md is not in include list
    if "include CLAUDE.md" in content:
        errors.append("MANIFEST.in: CLAUDE.md should be excluded, not included")

    return errors


def check_release_notes(repo_root: Path, expected_version: str) -> list[str]:
    """Verify release notes for the expected version exist and are packaged."""
    errors = []
    release_note = f"RELEASE_v{expected_version}.md"
    manifest = repo_root / "MANIFEST.in"
    releases = repo_root / "RELEASES.md"
    changelog = repo_root / "CHANGELOG.md"

    if not (repo_root / release_note).exists():
        errors.append(f"{release_note}: missing release notes file")

    manifest_content = manifest.read_text(encoding="utf-8", errors="replace")
    if f"include {release_note}" not in manifest_content:
        errors.append(f"MANIFEST.in: missing 'include {release_note}'")

    if releases.exists():
        content = releases.read_text(encoding="utf-8", errors="replace")
        if f"v{expected_version}" not in content or release_note not in content:
            errors.append(f"RELEASES.md: missing v{expected_version} entry/link")

    if changelog.exists():
        content = changelog.read_text(encoding="utf-8", errors="replace")
        if f"[{expected_version}]" not in content:
            errors.append(f"CHANGELOG.md: missing [{expected_version}] entry")

    return errors


def check_install_commands(repo_root: Path, expected_version: str) -> list[str]:
    """Verify install commands reference correct version."""
    errors = []

    expected_git = f"@v{expected_version}"
    stale_git_pin = re.compile(r"git\+https://github\.com/rolling-codes/EasyCord\.git@v([0-9][^\s\"'`)]+)")

    files_to_check = [
        repo_root / "README.md",
        repo_root / "docs" / "getting-started.md",
        repo_root / "docs" / "quickstart-production.md",
    ]

    for file in files_to_check:
        if not file.exists():
            continue

        content = file.read_text(encoding="utf-8", errors="replace")

        for match in stale_git_pin.finditer(content):
            version = match.group(1)
            if f"@v{version}" != expected_git:
                errors.append(
                    f"{file.relative_to(repo_root)}: git install command "
                    f"references @v{version}, expected {expected_git}"
                )

    return errors


def main():
    """Run all validation checks."""
    parser = argparse.ArgumentParser(description="Release consistency validator")
    parser.add_argument(
        "--version",
        default=None,
        help="Expected version (defaults to version in pyproject.toml)"
    )
    args = parser.parse_args()

    repo_root = Path(__file__).parent.parent

    # Determine expected version
    expected_version = args.version
    if not expected_version:
        expected_version = read_version_from_pyproject(repo_root)
        if not expected_version:
            print("[!] ERROR: Could not determine version from pyproject.toml or --version")
            return 1

    all_errors = []

    print("[*] Checking release consistency...\n")

    # Check version consistency
    print("[*] Version consistency...")
    errors = check_version_consistency(repo_root, expected_version)
    if errors:
        print(f"  [!] {len(errors)} version issues found:")
        for error in errors:
            print(f"     - {error}")
        all_errors.extend(errors)
    else:
        print("  [OK] All version references consistent")

    # Check MANIFEST.in
    print("\n[*] MANIFEST.in checks...")
    errors = check_manifest_in(repo_root)
    if errors:
        print(f"  [!] {len(errors)} issues found:")
        for error in errors:
            print(f"     - {error}")
        all_errors.extend(errors)
    else:
        print("  [OK] MANIFEST.in properly configured")

    # Check release notes
    print("\n[*] Release notes...")
    errors = check_release_notes(repo_root, expected_version)
    if errors:
        print(f"  [!] {len(errors)} release note issues found:")
        for error in errors:
            print(f"     - {error}")
        all_errors.extend(errors)
    else:
        print("  [OK] Release notes complete")

    # Check install commands
    print("\n[*] Install command consistency...")
    errors = check_install_commands(repo_root, expected_version)
    if errors:
        print(f"  [!] {len(errors)} install issues found:")
        for error in errors:
            print(f"     - {error}")
        all_errors.extend(errors)
    else:
        print("  [OK] All install commands consistent")

    # Check distribution hygiene (if archive exists)
    dist_dir = repo_root / "dist"
    if dist_dir.exists():
        print("\n[*] Distribution archive hygiene...")
        normalized_version = expected_version.replace("-beta.", "b")
        archives = sorted(dist_dir.glob(f"easycord-{normalized_version}.tar.gz"))
        wheels = sorted(dist_dir.glob(f"easycord-{normalized_version}-*.whl"))
        if archives:
            errors = check_distribution_hygiene(archives[-1])
            if errors:
                print(f"  [!] {len(errors)} distribution issues found:")
                for error in errors:
                    print(f"     - {error}")
                all_errors.extend(errors)
            else:
                print("  [OK] Source distribution is clean")
        else:
            print(f"  [SKIP] No source distribution found for {expected_version}")

        if wheels:
            errors = check_wheel_hygiene(wheels[-1])
            if errors:
                print(f"  [!] {len(errors)} wheel issues found:")
                for error in errors:
                    print(f"     - {error}")
                all_errors.extend(errors)
            else:
                print("  [OK] Wheel is clean")
        else:
            print(f"  [SKIP] No wheel found for {expected_version}")

    # Summary
    print("\n" + "=" * 60)
    if all_errors:
        print(f"[FAIL] {len(all_errors)} issues found")
        return 1
    else:
        print("[PASS] All release consistency checks passed")
        return 0


if __name__ == "__main__":
    sys.exit(main())
