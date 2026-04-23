"""Shared pytest fixtures for the test suite."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from easycord import Bot


@pytest.fixture(autouse=True)
def _test_database_backend(monkeypatch):
    monkeypatch.setenv("EASYCORD_DB_BACKEND", "memory")
    monkeypatch.delenv("EASYCORD_DB_PATH", raising=False)


@pytest.fixture
def bot():
    """Bot instance with discord.Client internals mocked out."""
    mock_tree = MagicMock()
    mock_tree.add_command = MagicMock()
    mock_tree.remove_command = MagicMock()
    mock_tree.sync = AsyncMock()

    with patch("discord.Client.__init__", return_value=None), \
         patch("easycord.bot.app_commands.CommandTree", return_value=mock_tree):
        b = Bot(intents=MagicMock(), auto_sync=False, db_backend="memory")
        b.is_ready = MagicMock(return_value=False)
        return b
