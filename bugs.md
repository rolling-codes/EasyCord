# Bug Log

A running record of bugs found and fixed, with root cause and the lesson, so the
same mistakes are not repeated. Newest first. Severity: CRITICAL / HIGH / MEDIUM / LOW.

| ID | Date | Area | Severity | Status | Summary |
|----|------|------|----------|--------|---------|
| B-001 | 2026-06-30 | CI / test gate | HIGH | Fixed | Coverage gate ignored `async def` tests |
| B-002 | 2026-06-30 | CI / test gate | MEDIUM | Fixed | Plugin→test-file name mismatch counted real tests as 0 |
| B-003 | 2026-06-30 | CI / workflows | MEDIUM | Fixed | Invalid `assignees: ['tee']` broke issue-opening automation |
| B-004 | 2026-06-30 | Tests / typing | LOW | Fixed | `embed.footer.text` (`str \| None`) used with `in` without narrowing |
| B-005 | 2026-06-30 | Tests / typing | LOW | Fixed | `plugin._bot` (Optional) member access flagged by Pyright in tests |

---

## B-001 — Coverage gate ignored async test functions
- **Where:** `scripts/verify_plugin_tests.py:11` (`count_test_functions`)
- **Symptom:** PR #71's `Verify plugin test coverage thresholds` step failed on Python
  3.10/3.11/3.12 and cancelled all downstream test jobs. Plugins with many tests
  reported near-zero (e.g. `ai_moderator` showed 1 of 21).
- **Root cause:** The AST walk matched only `ast.FunctionDef`. An `async def test_…`
  parses as `ast.AsyncFunctionDef`, a *separate* node type, so every async test —
  nearly all plugin tests in this asyncio-mode-auto suite — was invisible.
- **Fix:** Count `(ast.FunctionDef, ast.AsyncFunctionDef)`.
- **Lesson:** When walking Python AST for *functions*, always handle both
  `FunctionDef` and `AsyncFunctionDef`. They do not share a common concrete base you
  can `isinstance`-check with one name. This codebase is async-first — assume tests
  are coroutines.

## B-002 — Plugin→test-file name mismatch
- **Where:** `scripts/verify_plugin_tests.py` (`main`)
- **Symptom:** Even after B-001, `levels` and `reminders` counted 0 tests.
- **Root cause:** The checker assumed `test_<plugin>.py`, but the files are
  `test_levels_plugin.py` and `test_reminder.py` (singular). The lookup silently
  treated a missing file as 0 tests instead of erroring.
- **Fix:** Added an explicit `test_file_aliases` map
  (`levels→levels_plugin`, `reminders→reminder`) consulted via a `test_file_for()`
  helper.
- **Lesson:** A "file not found → 0" branch hides configuration drift. Prefer an
  explicit alias map over silent zero; if a mapped file is missing, that should be
  loud. Also exposed a genuine gap (B-002 follow-up below).

### B-002 follow-up — genuine missing coverage
After B-001/B-002 fixes, three real gaps remained and were filled:
- `tests/test_reminder.py`: +2 tests (→20) — `_parse_duration` seconds + invalid-raises.
- `tests/test_tags.py` (new, 15): store CRUD, per-guild isolation, admin/author delete gating.
- `tests/test_starboard.py` (new, 11): config defaults, mutate-guarded archived-map RMW,
  archive/unarchive, NotFound cleanup, threshold/channel gating.

## B-003 — Invalid GitHub assignee in workflows
- **Where:** `.github/workflows/ci-failure-reporter.yml:75`, `nightly.yml:97`,
  `triage.yml:42`.
- **Symptom:** "CI Failure Reporter" run failed with an invalid-assignee error
  (`tee` is not a GitHub user on this repo; it is only the local `git config user.name`).
- **Root cause:** `assignees: ['tee']` hardcoded a local git identity as if it were a
  GitHub login. The repo is under the `rolling-codes` org; no `tee` collaborator exists.
- **Fix:** Removed the `assignees` field from the two `issues.create` calls and the
  `addAssignees` block in `triage.yml`; softened the triage comment accordingly.
- **Lesson:** GitHub assignees must be valid repo-collaborator *logins*, never a local
  git `user.name`. If auto-assignment is wanted later, set the maintainer's real
  GitHub login (or use `context.actor`), and prefer failing soft over hardcoding.

## B-004 — Optional `embed.footer.text` used with `in`
- **Where:** `tests/test_reminder.py:83` (pre-existing).
- **Symptom:** Pyright `reportOperatorIssue` — `in` unsupported for `str` and `None`.
- **Root cause:** `discord.Embed.footer.text` is `str | None`; the test used
  `"unknown time" in embed.footer.text` without narrowing.
- **Fix:** Assert `embed.footer.text is not None` first.
- **Lesson:** discord.py embed accessors are heavily Optional. Narrow before
  membership/index/attribute use in tests too — not just in `easycord/`.

## B-005 — Optional `_bot` member access in tests
- **Where:** `tests/test_starboard.py` (two unarchive tests).
- **Symptom:** Pyright `reportOptionalMemberAccess` on `plugin._bot.get_guild`.
- **Root cause:** `Plugin._bot` is `Optional`; configuring the mock through the
  attribute tripped the Optional check.
- **Fix:** Build a local `bot = MagicMock()`, configure it, then assign `plugin._bot = bot`.
- **Lesson:** Per CLAUDE.md, set `_bot` directly in tests — and configure the mock on a
  local variable to keep the attribute access off the Optional-typed field.
