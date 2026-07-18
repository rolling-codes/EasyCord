---
phase: 01-verified-bug-fixes
plan: 02
subsystem: cli
tags: [cli, scaffold, pytest, pyproject, testpaths]

# Dependency graph
requires: []
provides:
  - "_module_name() collision guard: test_*/*_test slugs renamed (bot_ prefix / _plugin suffix) with a UserWarning naming original and renamed module"
  - "Generated pyproject [tool.pytest.ini_options] now includes testpaths = [\"tests\"]"
  - "Regression file tests/test_cli_scaffold.py (7 tests, TestBugs docstring convention)"
affects: [04-collection-hygiene, cli, scaffold]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Scaffold module names are sanitized against pytest collection patterns after the digit guard, never before"

key-files:
  created:
    - tests/test_cli_scaffold.py
  modified:
    - easycord/cli.py

key-decisions:
  - "bot_ prefix fixes test_* names but cannot fix *_test suffixes (bot_my_test still matches *_test.py); a _plugin suffix rule handles that case, applied independently so test_my_test resolves too"
  - "Collision guard runs after the leading-digit guard because the old early return let plugin_1_test through as a *_test collision"
  - "warnings.warn(UserWarning) chosen over print-to-stderr so the rename is assertable via pytest.warns and visible in any caller"

patterns-established:
  - "Regression tests use TestBugs class with BUG:/Fixed: docstrings per tests/test_stress.py convention"

requirements-completed: [REQ-02]

coverage:
  - id: D1
    description: "Project names slugging to test_*/*_test are renamed so the generated plugins/<module>.py is never pytest-collectable, including via the leading-digit path"
    requirement: "REQ-02"
    verification:
      - kind: unit
        ref: "tests/test_cli_scaffold.py#test_module_name_renames_test_prefix_and_warns"
        status: pass
      - kind: unit
        ref: "tests/test_cli_scaffold.py#test_module_name_renames_test_suffix_and_warns"
        status: pass
      - kind: unit
        ref: "tests/test_cli_scaffold.py#test_module_name_digit_guard_path_cannot_collide"
        status: pass
      - kind: unit
        ref: "tests/test_cli_scaffold.py#test_colliding_scaffold_produces_no_pytest_collectable_plugin_module"
        status: pass
    human_judgment: false
  - id: D2
    description: "Generated pyproject.toml scopes pytest to the tests directory via testpaths, aligned after textwrap.dedent"
    requirement: "REQ-02"
    verification:
      - kind: unit
        ref: "tests/test_cli_scaffold.py#test_generated_pyproject_scopes_pytest_to_tests_dir"
        status: pass
    human_judgment: false
  - id: D3
    description: "A UserWarning names the original and renamed module when a collision rename occurs; non-colliding names pass through unchanged and silent"
    requirement: "REQ-02"
    verification:
      - kind: unit
        ref: "tests/test_cli_scaffold.py#test_normal_name_is_unchanged_and_emits_no_warning"
        status: pass
      - kind: unit
        ref: "tests/test_cli_scaffold.py#test_module_name_renames_test_prefix_and_warns"
        status: pass
    human_judgment: false

# Metrics
duration: 12min
completed: 2026-07-11
status: complete
---

# Phase 1 Plan 02: CLI Scaffold Pytest Collision Fix Summary

**`easycord new` scaffolds can no longer emit a pytest-collectable plugin module — `_module_name` renames `test_*`/`*_test` slugs with a warning, and the generated pyproject scopes pytest via `testpaths = ["tests"]`**

## Performance

- **Duration:** ~12 min
- **Completed:** 2026-07-11
- **Tasks:** 2/2
- **Files modified:** 2 (1 created, 1 modified)

## Accomplishments
- `_module_name` (easycord/cli.py) gains a collision guard: `test_*` slugs get a `bot_` prefix, `*_test` slugs get a `_plugin` suffix, each rename emitting a `UserWarning` naming both the original and renamed module
- The leading-digit guard no longer returns early, so `"1 test"` → `plugin_1_test` can no longer slip through as a `*_test.py` collision
- Generated pyproject `[tool.pytest.ini_options]` now carries `testpaths = ["tests"]` alongside `asyncio_mode = "auto"`, aligned correctly after `textwrap.dedent`
- New regression file `tests/test_cli_scaffold.py` (7 tests, TestBugs docstring convention); `tests/test_plugin_creator.py` stays green (22 passed combined)

## Task Commits

1. **Task 1: Verify the finding** — analysis only, no code change (both sub-findings confirmed open: no `testpaths` anywhere in cli.py; `_module_name` had only empty-name/digit guards)
2. **Task 2: TDD fix (RED then GREEN)** — `c311be1` (fix)

## Files Created/Modified
- `easycord/cli.py` — `_module_name` collision rename + warning; pyproject template gains `testpaths`
- `tests/test_cli_scaffold.py` — regression tests for REQ-02 (rename rules, digit-guard path, testpaths dedent alignment, non-collecting scaffold output, silent pass-through for normal names)

## Decisions Made
- The plan's suggested `bot_` prefix alone cannot fix `*_test` suffix collisions (`bot_my_test` still matches `*_test.py`), so a `_plugin` suffix rule was added; the two rules apply independently, covering `test_my_test`-style double collisions
- Collision guard placed after the digit guard (the old early return was itself a latent collision path)
- `warnings.warn(UserWarning, stacklevel=2)` used for the rename warning — testable via `pytest.warns`, surfaces to any caller including `easycord new`

## Deviations from Plan

None - plan executed exactly as written. (The `_plugin` suffix rule and digit-guard reordering are within the plan's stated behavior contract — "result no longer matches pytest collection" — and the Claude's-discretion latitude on the exact rename rule.)

## Issues Encountered
None.

## Known Stubs
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Scaffold collection hygiene done; Phase 4's broader pytest collection-hygiene sweep (deferred item) can build on `testpaths` now being emitted
- Verification gate green: `python -m pytest tests/test_cli_scaffold.py tests/test_plugin_creator.py -q` → 22 passed

## Self-Check: PASSED

- FOUND: tests/test_cli_scaffold.py
- FOUND: commit c311be1
- Verification gate: 22 passed

---
*Phase: 01-verified-bug-fixes*
*Completed: 2026-07-11*
