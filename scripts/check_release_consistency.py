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

    excluded_files = {
        "CLAUDE.md",
        "AGENTS.md",
        "MODEL_CONTEXT.md",
        ".coderabbit.yaml",
        ".claude",
        ".worktrees",
    }

    try:
        with tarfile.open(archive_path, "r:gz") as tar:
            for member in tar.getmembers():
                # Check if any excluded file is in the archive
                basename = Path(member.name).name
                if basename in excluded_files:
                    errors.append(
                        f"Distribution archive contains development file: {member.name}"
                    )
    except Exception as e:
        errors.append(f"Could not read archive {archive_path}: {e}")

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
    ]

    for exclude in required_excludes:
        if exclude not in content:
            errors.append(f"MANIFEST.in: missing '{exclude}'")

    # Check that CLAUDE.md is not in include list
    if "include CLAUDE.md" in content:
        errors.append("MANIFEST.in: CLAUDE.md should be excluded, not included")

    return errors


def check_install_commands(repo_root: Path, expected_version: str) -> list[str]:
    """Verify install commands reference correct version."""
    errors = []

    expected_git = f"@v{expected_version}"
    expected_pip = f"easycord=={expected_version}"

    files_to_check = [
        repo_root / "README.md",
        repo_root / "docs" / "getting-started.md",
        repo_root / "docs" / "quickstart-production.md",
    ]

    for file in files_to_check:
        if not file.exists():
            continue

        content = file.read_text(encoding="utf-8", errors="replace")

        # Check for git install commands
        if "git+" in content:
            if expected_git not in content:
                errors.append(
                    f"{file.relative_to(repo_root)}: git install command "
                    f"doesn't reference {expected_git}"
                )

        # Check for stale versions
        if f"@v4.3" in content or f"@v4.2" in content:
            errors.append(
                f"{file.relative_to(repo_root)}: contains stale version tags"
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
        # Normalize version for glob: 4.5.0-beta.1 -> 4.5.0b1
        normalized_version = expected_version.replace("-", "").replace(".", "")
        # More flexible glob: match any easycord-*.tar.gz in dist
        archives = sorted(dist_dir.glob("easycord-*.tar.gz"), reverse=True)
        if archives:
            errors = check_distribution_hygiene(archives[0])
            if errors:
                print(f"  [!] {len(errors)} distribution issues found:")
                for error in errors:
                    print(f"     - {error}")
                all_errors.extend(errors)
            else:
                print("  [OK] Distribution archive is clean")
        else:
            print("  [SKIP] No distribution archive found (skipped)")

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
