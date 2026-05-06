# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
pip install -e ".[dev]"
pytest tests/
pytest tests/test_middleware.py -v
pytest tests/test_middleware.py::test_name -v
python -m build
```

`pytest-asyncio` with `asyncio_mode = "auto"` — no manual event loop setup needed.

## Context

- [Architecture](context/architecture.md) — layers, mixins, module map
- [Conventions](context/conventions.md) — naming rules, key invariants
