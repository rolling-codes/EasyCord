# v4.1.1 — Security and Release Automation Hardening

**Release Date:** 2026-04-28

## Summary

v4.1.1 focuses on security hardening, safer automation behavior, and release reliability.

## What Changed

### Workflow security hardening

- Added stricter validation for `workflow_dispatch` fix commands in `.github/workflows/auto-fix-issues.yml`.
- Restricted `/fix-issues` issue-comment trigger execution to trusted collaborators with `admin`, `maintain`, or `write` access.

### AI plugin safety improvements

- Added a maximum prompt length guard in `OpenClaudePlugin`/`AIPlugin` to reduce abuse from oversized prompts.
- Added stale rate-limit bucket pruning to prevent unbounded in-memory growth over long runtimes.

### Release automation

- Added `.github/workflows/release.yml` to automatically publish GitHub Releases from `vX.Y.Z` tags.
- Added `release.ps1` to create and push tags from PowerShell in one command.

## Testing

- `pytest tests/test_openclaude_plugin.py`
- `pytest`
