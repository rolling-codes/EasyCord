# EasyCord v4.5.0 Release Notes

**Release Date:** May 2, 2026  
**Status:** Stable — Production-Ready

## Overview

v4.5.0 is the stable release of the localization hardening line validated in v4.5.0-beta.3. This is a validation-only promotion: no feature changes were added after the release candidate.

---

## Stable Release Highlights

- Production-grade localization fallback chains with deterministic, bounded resolution
- STRICT diagnostics correctness: missing keys always raise in strict mode
- Safe metrics snapshots from `get_metrics()` with isolated locale-frequency data
- BCP 47 locale validation with script subtags such as `zh-Hant-HK` and `sr-Latn-RS`
- Real performance regression enforcement in GitHub Actions
- Release consistency checks for version pins, release notes, and built artifact hygiene
- Clean wheel and source distribution packaging

---

## Validation Summary

| Check | Result |
|-------|--------|
| Full test suite | 691 passed |
| Localization focused suite | 76 passed |
| Release consistency | PASS |
| Source distribution hygiene | PASS |
| Wheel hygiene | PASS |

---

## Installation

```bash
pip install "easycord @ git+https://github.com/rolling-codes/EasyCord.git@v4.5.0"
```

For source installs:

```bash
git clone --branch v4.5.0 https://github.com/rolling-codes/EasyCord.git
cd EasyCord
pip install -e ".[dev]"
```

---

## Compatibility

No breaking changes from v4.5.0-beta.3. Existing v4.5 beta users can upgrade directly to v4.5.0.

---

## Next

Phase 2 localization work can now build on the stable foundation:

- Cache warming and fallback pre-computation
- Expanded auto-translator integrations
- Additional Discord-facing localization features

---

## Release Links

- **GitHub Release:** https://github.com/rolling-codes/EasyCord/releases/tag/v4.5.0
- **Release Candidate:** https://github.com/rolling-codes/EasyCord/releases/tag/v4.5.0-beta.3
