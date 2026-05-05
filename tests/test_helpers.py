"""Tests for helpers: config, tools, context, ratelimit."""
from __future__ import annotations

import pytest

from easycord.helpers.config import ConfigHelpers
from easycord.helpers.tools import ToolHelpers
from easycord.tools import ToolRegistry, ToolSafety


# ---------------------------------------------------------------------------
# ConfigHelpers
# ---------------------------------------------------------------------------

class TestConfigHelpers:
    @pytest.mark.asyncio
    async def test_load_or_default_creates_config(self, tmp_path) -> None:
        result = await ConfigHelpers.load_or_default(
            1, str(tmp_path / "cfg"), {"x": 10}
        )
        assert result == {"x": 10}

    @pytest.mark.asyncio
    async def test_load_or_default_does_not_overwrite(self, tmp_path) -> None:
        path = str(tmp_path / "cfg")
        await ConfigHelpers.load_or_default(1, path, {"x": 10})
        result = await ConfigHelpers.load_or_default(1, path, {"x": 999})
        assert result["x"] == 10

    @pytest.mark.asyncio
    async def test_update_atomic(self, tmp_path) -> None:
        path = str(tmp_path / "cfg")
        await ConfigHelpers.load_or_default(1, path, {"x": 1})
        result = await ConfigHelpers.update_atomic(1, path, {"x": 42, "y": 7})
        assert result["x"] == 42
        assert result["y"] == 7

    @pytest.mark.asyncio
    async def test_get_or_create(self, tmp_path) -> None:
        path = str(tmp_path / "cfg")
        result = await ConfigHelpers.get_or_create(1, path, "section", {"a": 1})
        assert result == {"a": 1}

    @pytest.mark.asyncio
    async def test_get_or_create_idempotent(self, tmp_path) -> None:
        path = str(tmp_path / "cfg")
        await ConfigHelpers.get_or_create(1, path, "section", {"a": 1})
        result = await ConfigHelpers.get_or_create(1, path, "section", {"a": 999})
        assert result["a"] == 1

    @pytest.mark.asyncio
    async def test_load_all_guilds(self, tmp_path) -> None:
        path = str(tmp_path / "cfg")
        await ConfigHelpers.load_or_default(10, path, {"val": "a"})
        await ConfigHelpers.load_or_default(20, path, {"val": "b"})
        all_guilds = await ConfigHelpers.load_all_guilds(path)
        assert 10 in all_guilds
        assert 20 in all_guilds

    @pytest.mark.asyncio
    async def test_load_all_guilds_empty_dir(self, tmp_path) -> None:
        path = str(tmp_path / "nonexistent")
        result = await ConfigHelpers.load_all_guilds(path)
        assert result == {}


# ---------------------------------------------------------------------------
# ToolHelpers
# ---------------------------------------------------------------------------

class TestToolHelpers:
    def _registry_with_tool(self) -> ToolRegistry:
        registry = ToolRegistry()
        registry.register(
            name="my_tool",
            func=lambda ctx: "ok",
            description="A tool",
            safety=ToolSafety.SAFE,
            require_guild=False,
        )
        return registry

    def test_register_batch(self) -> None:
        registry = ToolRegistry()
        count = ToolHelpers.register_batch(registry, [
            {
                "name": "tool_a",
                "func": lambda ctx: "a",
                "description": "Tool A",
                "safety": ToolSafety.SAFE,
            },
            {
                "name": "tool_b",
                "func": lambda ctx: "b",
                "description": "Tool B",
                "safety": ToolSafety.CONTROLLED,
            },
        ])
        assert count == 2
        assert "tool_a" in registry._tools
        assert "tool_b" in registry._tools

    def test_register_batch_skips_incomplete(self) -> None:
        registry = ToolRegistry()
        count = ToolHelpers.register_batch(registry, [
            {"name": "bad"},  # missing required fields
            {
                "name": "good",
                "func": lambda ctx: "ok",
                "description": "Good tool",
                "safety": ToolSafety.SAFE,
            },
        ])
        assert count == 1

    def test_check_permission_registered_tool(self) -> None:
        registry = self._registry_with_tool()
        assert ToolHelpers.check_permission(registry, "my_tool", 1) is True

    def test_check_permission_missing_tool(self) -> None:
        registry = self._registry_with_tool()
        assert ToolHelpers.check_permission(registry, "nonexistent", 1) is False

    def test_check_permission_disabled_tool(self) -> None:
        registry = self._registry_with_tool()
        registry.disable("my_tool")
        assert ToolHelpers.check_permission(registry, "my_tool", 1) is False

    def test_list_all_tools(self) -> None:
        registry = self._registry_with_tool()
        tools = ToolHelpers.list_all_tools(registry)
        assert "my_tool" in tools

    def test_get_tool_info(self) -> None:
        registry = self._registry_with_tool()
        info = ToolHelpers.get_tool_info(registry, "my_tool")
        assert info is not None
        assert info["name"] == "my_tool"
        assert "safety" in info

    def test_get_tool_info_missing(self) -> None:
        registry = self._registry_with_tool()
        assert ToolHelpers.get_tool_info(registry, "ghost") is None
