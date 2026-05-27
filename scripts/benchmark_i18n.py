"""Benchmark EasyCord localization hot paths for CI regression checks."""
from __future__ import annotations

import json
import statistics
import time
from pathlib import Path
from typing import Callable

from easycord.i18n import DiagnosticMode, LocalizationManager


def _time_ms(fn: Callable[[], None], *, rounds: int = 5) -> float:
    samples: list[float] = []
    for _ in range(rounds):
        start = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - start) * 1000)
    return statistics.median(samples)


def _manager(*, track_metrics: bool = False, diagnostic_mode: DiagnosticMode = DiagnosticMode.SILENT) -> LocalizationManager:
    translations = {
        "en-US": {
            "command.ping": "Pong",
            "command.hello": "Hello {name}",
            "error.missing": "Missing value",
        },
        "fr-FR": {
            "command.ping": "Pong FR",
            "command.hello": "Bonjour {name}",
        },
        "pt-BR": {
            "command.ping": "Pong BR",
        },
    }
    return LocalizationManager(
        translations=translations,
        diagnostic_mode=diagnostic_mode,
        track_metrics=track_metrics,
    )


def _lookup_benchmark(iterations: int, *, warm: bool = False) -> tuple[float, float]:
    manager = _manager()
    locales = ("fr-FR", "pt-BR", "en-US", "es-ES")
    keys = ("command.ping", "command.hello", "error.missing")

    if warm:
        for locale in locales:
            for key in keys:
                manager.get(key, locale=locale)

    def run() -> None:
        for index in range(iterations):
            manager.get(keys[index % len(keys)], locale=locales[index % len(locales)])

    total_ms = _time_ms(run)
    return total_ms, total_ms / iterations


def _overhead_percent(
    baseline: Callable[[], None],
    measured: Callable[[], None],
    *,
    rounds: int = 7,
) -> float:
    baseline_ms = _time_ms(baseline, rounds=rounds)
    measured_ms = _time_ms(measured, rounds=rounds)
    if baseline_ms <= 0:
        return 0.0
    return max(0.0, ((measured_ms - baseline_ms) / baseline_ms) * 100)


def _diagnostics_overhead() -> float:
    silent = _manager()
    warn = _manager(diagnostic_mode=DiagnosticMode.WARN)

    def baseline() -> None:
        for index in range(5000):
            silent.get("command.ping", locale="fr-FR" if index % 2 else "pt-BR")

    def measured() -> None:
        for index in range(5000):
            warn.get("command.ping", locale="fr-FR" if index % 2 else "pt-BR")

    return _overhead_percent(baseline, measured)


def _metrics_overhead() -> float:
    plain = _manager()
    tracked = _manager(track_metrics=True)

    def baseline() -> None:
        for index in range(5000):
            plain.get("command.ping", locale="fr-FR" if index % 2 else "pt-BR")

    def measured() -> None:
        for index in range(5000):
            tracked.get("command.ping", locale="fr-FR" if index % 2 else "pt-BR")

    return _overhead_percent(baseline, measured)


def _validator_scaling_ms() -> float:
    base = {f"key.{index}": f"Value {index}" for index in range(200)}
    translations = {"en-US": base}
    for locale_index in range(20):
        translations[f"x{locale_index:02d}-US"] = {
            key: value for offset, (key, value) in enumerate(base.items())
            if offset % (locale_index + 2) != 0
        }
    manager = LocalizationManager(translations=translations)
    return _time_ms(lambda: manager.validate_completeness(), rounds=5)


def main() -> None:
    cold_total_ms, cold_avg_ms = _lookup_benchmark(100)
    warm_total_ms, warm_avg_ms = _lookup_benchmark(10_000, warm=True)

    results = {
        "Cold Cache (100 lookups)": {
            "total_time_ms": round(cold_total_ms, 4),
            "avg_lookup_ms": round(cold_avg_ms, 6),
        },
        "Warm Cache (10k lookups)": {
            "total_time_ms": round(warm_total_ms, 4),
            "avg_lookup_ms": round(warm_avg_ms, 6),
        },
        "Diagnostics Overhead": {
            "overhead_percent": round(_diagnostics_overhead(), 4),
        },
        "Metrics Overhead": {
            "overhead_percent": round(_metrics_overhead(), 4),
        },
        "Validator Scaling (20 locales)": {
            "validation_time_ms": round(_validator_scaling_ms(), 4),
        },
    }

    output = Path("benchmark-results.json")
    output.write_text(json.dumps(results, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(results, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
