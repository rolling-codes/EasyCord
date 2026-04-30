# v4.3.0 - Release Label Automation and Governance Cleanup

**Release Date:** 2026-04-29

## Summary

v4.3.0 packages the unreleased release-governance work found after v4.2.0 and keeps the runtime bug fixes that were already present on `main`.

## What's New

- Added an automatic release-label workflow for pull requests.
- Added default `release:patch`, `release:minor`, and `release:major` label creation when missing.
- Updated PR governance so pull requests receive a default release label instead of failing immediately.
- Normalized duplicate release labels down to a single release label for cleaner release planning.

## Bug Fixes

- Preserved the existing `LevelsPlugin` bot-message guard fix already present on `main`.
- Kept the v4.2 runtime fixes for stale webhooks, emoji upload validation, SQLite payload decoding, middleware cleanup, and AI limiter cleanup in the 4.3 release line.

## Release Notes

- `v4.2.0` was already published from PR #31.
- The post-release `main` commit only cleaned up `v4.2.0` release-note sections.
- PR #33 contained unreleased release-label governance work, but its branch was behind current `main`; 4.3 includes the safe governance pieces without reverting current workflows.

## Testing

- `python -m compileall easycord`
- `python -m build`
