"""Tests for Orchestrator logging — provider selection and fallback events."""
from __future__ import annotations

import logging
from unittest.mock import AsyncMock, MagicMock

import pytest

from easycord.orchestrator import (
    FallbackStrategy,
    FinalResponse,
    Orchestrator,
    RunContext,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_provider(name: str, response: str | Exception) -> MagicMock:
    """Return a mock AIProvider whose query() returns *response* or raises it."""
    provider = MagicMock()
    provider.__class__.__name__ = name
    type(provider).__name__ = name  # type(provider).__name__ used in logging
    if isinstance(response, Exception):
        provider.query = AsyncMock(side_effect=response)
    else:
        provider.query = AsyncMock(return_value=response)
    # Ensure signature inspection finds no "tools" param
    provider._cached_supports_tools = False
    return provider


def _make_run_ctx(messages: list[dict] | None = None) -> RunContext:
    return RunContext(
        messages=messages or [{"role": "user", "content": "Hello"}],
        ctx=None,
    )


def _make_tools() -> MagicMock:
    tools = MagicMock()
    tools.to_provider_schema = MagicMock(return_value=[])
    return tools


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestOrchestratorLogging:
    @pytest.mark.asyncio
    async def test_fallback_warning_logged_when_provider_raises(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """When a provider raises, a WARNING is emitted with provider name and exception info."""
        failing = _make_provider("FailingProvider", RuntimeError("API timeout"))
        succeeding = _make_provider("SucceedingProvider", "Hello from backup")

        strategy = FallbackStrategy([failing, succeeding])
        orchestrator = Orchestrator(strategy=strategy, tools=_make_tools())

        with caplog.at_level(logging.WARNING, logger="easycord.orchestrator"):
            result = await orchestrator.run(_make_run_ctx())

        assert result.text == "Hello from backup"

        warning_records = [
            r for r in caplog.records
            if r.levelno == logging.WARNING and "falling back" in r.message
        ]
        assert warning_records, "Expected a fallback WARNING but none was emitted"
        msg = warning_records[0].message
        assert "FailingProvider" in msg
        assert "RuntimeError" in msg
        assert "API timeout" in msg

    @pytest.mark.asyncio
    async def test_success_debug_logged_when_provider_handles_request(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """When a provider returns successfully, a DEBUG message names the provider."""
        provider = _make_provider("MyProvider", "Response text")
        strategy = FallbackStrategy([provider])
        orchestrator = Orchestrator(strategy=strategy, tools=_make_tools())

        with caplog.at_level(logging.DEBUG, logger="easycord.orchestrator"):
            result = await orchestrator.run(_make_run_ctx())

        assert result.text == "Response text"

        debug_records = [
            r for r in caplog.records
            if r.levelno == logging.DEBUG and "handled by provider" in r.message
        ]
        assert debug_records, "Expected a success DEBUG but none was emitted"
        assert "MyProvider" in debug_records[0].message

    @pytest.mark.asyncio
    async def test_all_providers_exhausted_logs_error(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """When all providers fail, an ERROR is logged before returning the fallback response."""
        failing = _make_provider("BadProvider", RuntimeError("always fails"))
        strategy = FallbackStrategy([failing])
        orchestrator = Orchestrator(strategy=strategy, tools=_make_tools())

        with caplog.at_level(logging.ERROR, logger="easycord.orchestrator"):
            result = await orchestrator.run(_make_run_ctx())

        assert result.text == "All providers exhausted"

        error_records = [
            r for r in caplog.records
            if r.levelno == logging.ERROR and "exhausted" in r.message
        ]
        assert error_records, "Expected an exhaustion ERROR but none was emitted"

    @pytest.mark.asyncio
    async def test_trying_provider_debug_logged_before_query(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """A DEBUG message is emitted before each provider is queried."""
        provider = _make_provider("EarlyProvider", "ok")
        strategy = FallbackStrategy([provider])
        orchestrator = Orchestrator(strategy=strategy, tools=_make_tools())

        with caplog.at_level(logging.DEBUG, logger="easycord.orchestrator"):
            await orchestrator.run(_make_run_ctx())

        trying_records = [
            r for r in caplog.records
            if r.levelno == logging.DEBUG and "trying provider" in r.message
        ]
        assert trying_records, "Expected a 'trying provider' DEBUG but none was emitted"
        assert "EarlyProvider" in trying_records[0].message
