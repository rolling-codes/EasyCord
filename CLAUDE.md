# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
pip install -e ".[dev]"
pytest tests/
pytest tests/test_middleware.py -v
pytest tests/test_middleware.py::test_name -v
python -m build --no-isolation   # plain `python -m build` needs a working venv module
python scripts/check_release_metadata.py   # version consistency across pyproject/__init__/CHANGELOG
```

`pytest-asyncio` with `asyncio_mode = "auto"` — no manual event loop setup needed.

The `easycord` console script (`easycord/cli.py`) is the dev-facing CLI: `easycord new`, `easycord doctor`, `easycord inspect`, `easycord sync-plan`, `easycord plugin create|check|discover`, `easycord test-template`, `easycord audit-tools`.

## Context

- [Architecture](context/architecture.md) — layers, mixins, module map
- [Conventions](context/conventions.md) — naming rules, key invariants
