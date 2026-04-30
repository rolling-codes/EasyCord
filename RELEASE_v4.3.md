# v4.3.0 - EasyCord Helper Utilities and Release Cleanup

**Release Date:** 2026-04-29

## Summary

v4.3.0 re-cuts the current EasyCord package line with the helper utilities and runtime fixes now present in `easycord/`, plus release-governance cleanup for future PRs.

## What's New

- Added `Paginator` for interactive paged embeds and line-based command output.
- Added `EasyEmbed.warning()` alongside the success, error, and info status embeds.
- Added `SecurityManager` and `FrameworkManager` for one-call secure bot setup.
- Added `Composer.secure_defaults()` and `Composer.convenience_framework()` for lower-boilerplate bot construction.
- Added an automatic release-label workflow for pull requests.
- Updated PR governance so pull requests receive a default release label instead of failing immediately.

## Bug Fixes

- Recreates stale cached webhooks once and retries the send instead of failing permanently.
- Validates emoji image paths and rejects files larger than Discord's 256 KiB custom emoji limit before upload.
- Makes SQLite payload decoding tolerate corrupt, invalid, or non-dict JSON by returning an empty mapping.
- Prunes empty middleware rate-limit buckets so long-running bots do not keep dead user entries.
- Runs OpenClaude limiter cleanup before prompt-length rejection so rejected oversized prompts still allow stale bucket cleanup.
- Preserves the `LevelsPlugin` bot-message guard fix already present on `main`.

## Release Notes

- `v4.2.0` was already published from PR #31.
- `v4.3.0` keeps the same package code line and publishes clearer notes for the actual `easycord/` changes, while adding safe release-label automation.
- PR #33 contained additional release-label governance work, but its branch was behind current `main`; 4.3 includes the safe governance pieces without reverting current workflows.

## Testing

- `python -m compileall easycord`
- `python -m build`
