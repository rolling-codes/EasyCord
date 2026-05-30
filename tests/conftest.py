from __future__ import annotations

from collections.abc import Callable
from importlib.metadata import EntryPoint

import pytest


class FakeEntryPoints(list):
    def select(self, *, group):
        return [entry_point for entry_point in self if entry_point.group == group]


@pytest.fixture
def fake_entry_points() -> Callable[..., Callable[[], FakeEntryPoints]]:
    def factory(*entry_points: EntryPoint) -> Callable[[], FakeEntryPoints]:
        return lambda: FakeEntryPoints(entry_points)

    return factory
