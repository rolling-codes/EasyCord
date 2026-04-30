# v4.2.0 — Helper Utilities and Faster Bot Setup

**Release Date:** 2026-04-29

## Summary

v4.2.0 adds small but high-leverage helpers that make bot setup shorter, common response patterns easier, and repo operations safer to maintain.

## What's New

- Added `Paginator` for fast paged command output from lines or prebuilt embeds.
- Added `EasyEmbed` status helpers for success, error, info, and warning responses.
- Added `SecurityManager` for a reusable middleware safety baseline.
- Added `FrameworkManager.bootstrap()` and `FrameworkManager.build_bot()` for faster one-call bot setup.
- Added `Composer.secure_defaults()` and `Composer.convenience_framework()` to reduce boilerplate in common bot builds.
- Added PR quality, PR governance, issue triage, and PR template helpers to shorten routine repo maintenance.

## Bug Fixes

- Recreate stale cached webhooks automatically and retry once.
- Validate emoji upload paths and reject files over Discord's upload limit before the API call.
- Make SQLite payload decoding tolerate corrupt or non-dict JSON safely.
- Prune empty middleware rate-limit buckets to keep in-memory tracking tidier.
- Ensure AI limiter cleanup still runs when overlong prompts are rejected.

## Release Hardening

- Hardened the auto-fix workflow to allow only the trusted fixer command for manual dispatch.
- Scoped release workflow write permissions to the release job and pinned the release action to an immutable SHA.
- Ignored stray pytest temp/cache folders that were polluting local test collection.

## Testing

- `pytest tests/test_openclaude_plugin.py tests/test_bot.py tests/test_composer.py tests/test_database.py -q`
- `pytest tests -q`
