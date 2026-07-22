from __future__ import annotations

import sys
from collections.abc import Callable
from importlib.metadata import EntryPoint
from pathlib import Path

import pytest

# Make the tests/ directory importable as a plain package so helper modules
# like plugin_test_helpers can be imported without a package prefix.
sys.path.insert(0, str(Path(__file__).parent))


class FakeEntryPoints(list):
    def select(self, *, group):
        return [entry_point for entry_point in self if entry_point.group == group]


@pytest.fixture
def fake_entry_points() -> Callable[..., Callable[[], FakeEntryPoints]]:
    def factory(*entry_points: EntryPoint) -> Callable[[], FakeEntryPoints]:
        return lambda: FakeEntryPoints(entry_points)

    return factory
