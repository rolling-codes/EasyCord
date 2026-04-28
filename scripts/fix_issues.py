"""Repository hook for the Auto-fix Issues workflow.

Keep this script deterministic: it should apply mechanical fixes that are safe
to run in CI, then leave semantic changes to normal pull requests.
"""
from __future__ import annotations


def main() -> None:
    print("No repository-local mechanical issue fixes are configured.")


if __name__ == "__main__":
    main()
