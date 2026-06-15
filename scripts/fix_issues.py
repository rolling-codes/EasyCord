"""Auto-fix script called by auto-fix-issues.yml.

Applies safe automated fixes:
  1. ruff check --fix  — fix auto-fixable lint violations
  2. ruff format       — enforce consistent formatting
  3. check_release_metadata.py — validate version consistency

Exits 0 on success (fixes applied or nothing to fix).
Exits 1 if metadata check fails after fixes.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent


def _run(cmd: list[str], *, label: str) -> bool:
    print(f"\n=== {label} ===")
    result = subprocess.run(cmd, cwd=ROOT)
    if result.returncode == 0:
        print(f"✓ {label} passed")
    else:
        print(f"✗ {label} exited {result.returncode}")
    return result.returncode == 0


def main() -> int:
    _run(["ruff", "check", "--fix", "."], label="ruff lint fix")
    _run(["ruff", "format", "."], label="ruff format")

    meta_ok = _run(
        [sys.executable, str(ROOT / "scripts" / "check_release_metadata.py")],
        label="release metadata check",
    )

    if not meta_ok:
        print("\nRelease metadata check failed — fix version files before merging.")
        return 1

    print("\n✓ All fixes applied successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
