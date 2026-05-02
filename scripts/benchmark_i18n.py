#!/usr/bin/env python3
"""
Performance benchmarks for localization infrastructure.

Measures and validates:
- cold cache performance
- warm cache performance
- fallback chain generation
- diagnostics overhead
- metrics overhead
- validator scaling
"""
import sys
import time
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from easycord.i18n import LocalizationManager, DiagnosticMode


def benchmark_cold_cache(iterations: int = 100) -> dict:
    """Measure cold cache lookup performance."""
    i18n = LocalizationManager(
        default_locale="en-US",
        translations={
            "en-US": {f"key_{i}": f"Value {i}" for i in range(1000)},
            "es-ES": {f"key_{i}": f"Valor {i}" for i in range(1000)},
            "fr-FR": {f"key_{i}": f"Valeur {i}" for i in range(1000)},
            "de-DE": {f"key_{i}": f"Wert {i}" for i in range(1000)},
        },
    )

    start = time.perf_counter()
    for i in range(iterations):
        i18n.get(f"key_{i % 1000}", locale="es-ES")
    elapsed = time.perf_counter() - start

    avg_ms = (elapsed / iterations) * 1000
    return {
        "iterations": iterations,
        "total_time_ms": elapsed * 1000,
        "avg_lookup_ms": avg_ms,
        "lookups_per_second": 1000 / avg_ms if avg_ms > 0 else 0,
        "status": "PASS" if elapsed < 0.1 else "FAIL",  # 100ms for 100 lookups
    }


def benchmark_warm_cache(iterations: int = 10000) -> dict:
    """Measure warm cache lookup performance."""
    i18n = LocalizationManager(
        default_locale="en-US",
        translations={
            "en-US": {f"key_{i}": f"Value {i}" for i in range(1000)},
            "es-ES": {f"key_{i}": f"Valor {i}" for i in range(1000)},
        },
    )

    # Warm up
    i18n.get("key_500", locale="es-ES")

    start = time.perf_counter()
    for _ in range(iterations):
        i18n.get("key_500", locale="es-ES")
    elapsed = time.perf_counter() - start

    avg_ms = (elapsed / iterations) * 1000
    return {
        "iterations": iterations,
        "total_time_ms": elapsed * 1000,
        "avg_lookup_ms": avg_ms,
        "lookups_per_second": 1000 / avg_ms if avg_ms > 0 else 0,
        "status": "PASS" if elapsed < 0.5 else "FAIL",  # 500ms for 10k lookups
    }


def benchmark_diagnostics_overhead() -> dict:
    """Measure diagnostics mode overhead (WARN vs SILENT)."""
    catalogs = {
        "en-US": {f"key_{i}": f"Value {i}" for i in range(500)},
        "es-ES": {f"key_{i}": f"Valor {i}" for i in range(500)},
    }

    # Baseline: SILENT mode
    silent_i18n = LocalizationManager(
        default_locale="en-US",
        diagnostic_mode=DiagnosticMode.SILENT,
        translations=catalogs,
    )

    start = time.perf_counter()
    for i in range(1000):
        silent_i18n.get("missing_key", locale="es-ES")
    silent_time = time.perf_counter() - start

    # WARN mode
    warn_i18n = LocalizationManager(
        default_locale="en-US",
        diagnostic_mode=DiagnosticMode.WARN,
        translations=catalogs,
    )

    start = time.perf_counter()
    for i in range(1000):
        warn_i18n.get("missing_key", locale="es-ES")
    warn_time = time.perf_counter() - start

    overhead_percent = ((warn_time - silent_time) / silent_time) * 100 if silent_time > 0 else 0
    return {
        "silent_time_ms": silent_time * 1000,
        "warn_time_ms": warn_time * 1000,
        "overhead_percent": overhead_percent,
        "status": "PASS" if overhead_percent < 50 else "FAIL",  # Max 50% overhead
    }


def benchmark_metrics_overhead() -> dict:
    """Measure metrics tracking overhead."""
    catalogs = {
        "en-US": {f"key_{i}": f"Value {i}" for i in range(500)},
        "es-ES": {f"key_{i}": f"Valor {i}" for i in range(500)},
    }

    # Without metrics
    no_metrics_i18n = LocalizationManager(
        default_locale="en-US",
        track_metrics=False,
        translations=catalogs,
    )

    start = time.perf_counter()
    for i in range(1000):
        no_metrics_i18n.get(f"key_{i % 500}", locale="es-ES")
    no_metrics_time = time.perf_counter() - start

    # With metrics
    with_metrics_i18n = LocalizationManager(
        default_locale="en-US",
        track_metrics=True,
        translations=catalogs,
    )

    start = time.perf_counter()
    for i in range(1000):
        with_metrics_i18n.get(f"key_{i % 500}", locale="es-ES")
    with_metrics_time = time.perf_counter() - start

    overhead_percent = ((with_metrics_time - no_metrics_time) / no_metrics_time) * 100 if no_metrics_time > 0 else 0
    return {
        "no_metrics_time_ms": no_metrics_time * 1000,
        "with_metrics_time_ms": with_metrics_time * 1000,
        "overhead_percent": overhead_percent,
        "status": "PASS" if overhead_percent < 30 else "FAIL",  # Max 30% overhead
    }


def benchmark_validator_scaling() -> dict:
    """Measure validator performance with large catalogs."""
    catalogs = {}
    base_keys = {f"key_{i}": f"Value {i}" for i in range(1000)}

    catalogs["en-US"] = base_keys
    for locale_num in range(20):
        locale = f"locale-{locale_num}"
        # Each locale has ~90% of keys
        keys = {k: v for k, v in base_keys.items() if locale_num % 11 != hash(k) % 11}
        catalogs[locale] = keys

    i18n = LocalizationManager(default_locale="en-US", translations=catalogs)

    start = time.perf_counter()
    report = i18n.validate_completeness()
    elapsed = time.perf_counter() - start

    return {
        "locales": len(catalogs),
        "keys_per_locale": 1000,
        "validation_time_ms": elapsed * 1000,
        "status": "PASS" if elapsed < 1.0 else "FAIL",  # < 1 second for 20 locales
    }


def main():
    """Run all benchmarks and report results."""
    import json

    print("[*] EasyCord Localization Performance Benchmarks\n")

    benchmarks = {
        "Cold Cache (100 lookups)": benchmark_cold_cache,
        "Warm Cache (10k lookups)": benchmark_warm_cache,
        "Diagnostics Overhead": benchmark_diagnostics_overhead,
        "Metrics Overhead": benchmark_metrics_overhead,
        "Validator Scaling (20 locales)": benchmark_validator_scaling,
    }

    all_passed = True
    results = {}

    for name, func in benchmarks.items():
        print(f"[*] {name}...")
        try:
            result = func()
            results[name] = result
            status = result.get("status", "UNKNOWN")
            print(f"  {status}: {result}\n")
            if status != "PASS":
                all_passed = False
        except Exception as e:
            print(f"  ERROR: {e}\n")
            all_passed = False

    # Save results to JSON for CI comparison
    results_file = Path(__file__).parent.parent / "benchmark-results.json"
    with open(results_file, "w") as f:
        json.dump(results, f, indent=2)
    print(f"[*] Results saved to {results_file}")

    print("=" * 60)
    if all_passed:
        print("[PASS] All benchmarks passed")
        return 0
    else:
        print("[FAIL] One or more benchmarks failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
