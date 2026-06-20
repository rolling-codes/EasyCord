"""Translation validation report helpers."""
from __future__ import annotations


class TranslationValidationReport:
    """Report from translation completeness validation."""

    def __init__(self, base_locale: str):
        self.base_locale = base_locale
        self.results: dict[str, dict] = {}

    def add_locale(
        self,
        locale: str,
        missing_keys: list[str],
        orphaned_keys: list[str],
        coverage: float,
    ) -> None:
        """Add validation results for a locale."""
        self.results[locale] = {
            "missing_keys": sorted(missing_keys),
            "orphaned_keys": sorted(orphaned_keys),
            "coverage": coverage,
            "total_missing": len(missing_keys),
            "total_orphaned": len(orphaned_keys),
        }

    def is_valid(self) -> bool:
        """Check if all locales are fully translated."""
        return all(
            result["total_missing"] == 0 for result in self.results.values()
        )

    def summary(self) -> dict:
        """Return summary statistics."""
        total_locales = len(self.results)
        fully_translated = sum(
            1 for r in self.results.values() if r["total_missing"] == 0
        )
        return {
            "base_locale": self.base_locale,
            "total_locales": total_locales,
            "fully_translated": fully_translated,
            "coverage_by_locale": {
                locale: result["coverage"]
                for locale, result in self.results.items()
            },
        }

    def report_text(self) -> str:
        """Return human-readable report."""
        lines = [f"Translation Validation Report (base: {self.base_locale})"]
        lines.append("")

        for locale in sorted(self.results.keys()):
            result = self.results[locale]
            status = "✓" if result["total_missing"] == 0 else "✗"
            lines.append(
                f"{status} {locale}: {result['coverage']:.1%} coverage "
                f"({result['total_missing']} missing)"
            )
            if result["missing_keys"]:
                lines.append(
                    f"  Missing: {', '.join(result['missing_keys'][:3])}"
                    f"{'...' if len(result['missing_keys']) > 3 else ''}"
                )
            if result["orphaned_keys"]:
                lines.append(
                    f"  Orphaned: {', '.join(result['orphaned_keys'][:3])}"
                    f"{'...' if len(result['orphaned_keys']) > 3 else ''}"
                )
        return "\n".join(lines)
