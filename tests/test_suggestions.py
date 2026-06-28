"""Tests for SuggestionsPlugin ID allocation under concurrency.

Pins the duplicate-ID defect: ``_get_next_id`` must allocate distinct,
monotonic IDs even when several ``/suggest`` calls race, because the
read-increment-write now runs under the per-guild lock via ``store.mutate``.
"""
from __future__ import annotations

import asyncio

import pytest

from easycord.plugins._config_manager import PluginConfigManager
from easycord.plugins.suggestions import SuggestionsPlugin


def _make_plugin(tmp_path) -> SuggestionsPlugin:
    plugin = SuggestionsPlugin()
    plugin.config = PluginConfigManager(str(tmp_path / "suggestions"))
    return plugin


@pytest.mark.asyncio
async def test_get_next_id_is_monotonic(tmp_path) -> None:
    plugin = _make_plugin(tmp_path)
    first = await plugin._get_next_id(1)
    second = await plugin._get_next_id(1)
    third = await plugin._get_next_id(1)
    assert [first, second, third] == [1, 2, 3]


@pytest.mark.asyncio
async def test_concurrent_get_next_id_yields_distinct_ids(tmp_path) -> None:
    plugin = _make_plugin(tmp_path)
    ids = await asyncio.gather(*[plugin._get_next_id(1) for _ in range(25)])
    # No duplicates, and the counter advanced exactly once per call.
    assert sorted(ids) == list(range(1, 26))


@pytest.mark.asyncio
async def test_counter_is_isolated_per_guild(tmp_path) -> None:
    plugin = _make_plugin(tmp_path)
    assert await plugin._get_next_id(1) == 1
    assert await plugin._get_next_id(2) == 1
    assert await plugin._get_next_id(1) == 2


@pytest.mark.asyncio
async def test_counter_persists_across_reload(tmp_path) -> None:
    plugin = _make_plugin(tmp_path)
    await plugin._get_next_id(1)
    await plugin._get_next_id(1)
    # Fresh plugin pointed at the same store keeps counting where it left off.
    reopened = SuggestionsPlugin()
    reopened.config = PluginConfigManager(str(tmp_path / "suggestions"))
    assert await reopened._get_next_id(1) == 3
