"""Tests for AI moderation plugin."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from easycord import ServerConfig
from easycord.plugins.ai_moderator import AIModeratorPlugin


@pytest.fixture
def plugin():
    """Create AIModeratorPlugin instance."""
    plugin_inst = AIModeratorPlugin(orchestrator=None)
    return plugin_inst


@pytest.fixture
def mock_guild():
    """Create mock Discord guild."""
    guild = MagicMock()
    guild.id = 12345
    guild.name = "Test Server"
    return guild


@pytest.fixture
def mock_message(mock_guild):
    """Create mock Discord message."""
    message = AsyncMock()
    message.guild = mock_guild
    message.author = MagicMock()
    message.author.id = 999
    message.author.name = "TestUser"
    message.author.bot = False
    message.content = "test message"
    message.delete = AsyncMock()
    return message


@pytest.fixture
def mock_context(mock_guild):
    """Create mock Context."""
    ctx = AsyncMock()
    ctx.guild = mock_guild
    ctx.user = MagicMock()
    ctx.user.id = 111
    ctx.send = AsyncMock()
    return ctx


@pytest.mark.asyncio
async def test_plugin_initializes(plugin):
    """Plugin can be initialized."""
    assert plugin is not None
    assert plugin.config is not None
    assert plugin.conversation_memory is not None


@pytest.mark.asyncio
async def test_default_config(plugin, mock_guild):
    """Default config is created on first access."""
    # Mock ServerConfig
    mock_server_cfg = MagicMock(spec=ServerConfig)
    mock_server_cfg.get_other = MagicMock(return_value=None)
    mock_server_cfg.set_other = MagicMock()

    with patch.object(plugin.config.store, "load", new_callable=AsyncMock, return_value=mock_server_cfg):
        with patch.object(plugin.config.store, "save", new_callable=AsyncMock):
            cfg = await plugin._get_config(mock_guild.id)
            assert cfg["enabled"] is False
            assert cfg["action_level"] == "notify_only"
            assert cfg["confidence_threshold"] == 0.85
            assert "rules" in cfg


@pytest.mark.asyncio
async def test_update_config(plugin, mock_guild):
    """Config can be updated atomically."""
    # Mock ServerConfig with mutable data
    config_data = {}

    def get_other_side_effect(key, default=None):
        return config_data.get(key, default)

    def set_other_side_effect(key, value):
        config_data[key] = value

    mock_server_cfg = MagicMock(spec=ServerConfig)
    mock_server_cfg.get_other = MagicMock(side_effect=get_other_side_effect)
    mock_server_cfg.set_other = MagicMock(side_effect=set_other_side_effect)

    with patch.object(plugin.config.store, "load", new_callable=AsyncMock, return_value=mock_server_cfg):
        with patch.object(plugin.config.store, "save", new_callable=AsyncMock):
            await plugin._update_config(mock_guild.id, enabled=True, action_level="warn")
            cfg = await plugin._get_config(mock_guild.id)
            assert cfg["enabled"] is True
            assert cfg["action_level"] == "warn"


@pytest.mark.asyncio
async def test_on_message_ignores_bots(plugin, mock_guild):
    """Plugin ignores messages from bots."""
    message = AsyncMock()
    message.guild = mock_guild
    message.author = MagicMock()
    message.author.bot = True

    await plugin._on_message(message)
    # Should not attempt analysis


@pytest.mark.asyncio
async def test_on_message_ignores_disabled(plugin, mock_guild, mock_message):
    """Plugin ignores messages when disabled."""
    mock_server_cfg = MagicMock(spec=ServerConfig)
    mock_server_cfg.get_other = MagicMock(return_value=None)
    mock_server_cfg.set_other = MagicMock()

    with patch.object(plugin.config.store, "load", new_callable=AsyncMock, return_value=mock_server_cfg):
        with patch.object(plugin.config.store, "save", new_callable=AsyncMock):
            with patch.object(plugin, "_analyze_message") as mock_analyze:
                await plugin._on_message(mock_message)
                mock_analyze.assert_not_called()


@pytest.mark.asyncio
async def test_analyze_message_without_orchestrator(plugin, mock_guild, mock_message):
    """Analysis fails gracefully without orchestrator."""
    action, confidence, reason = await plugin._analyze_message(mock_guild.id, mock_message)
    assert action is None
    assert confidence == 0.0
    assert "not configured" in reason.lower()


@pytest.mark.asyncio
async def test_warn_rate_limit(plugin, mock_context):
    """Warn action respects rate limit."""
    from easycord import RateLimit

    # First warn should succeed
    allowed1, _ = plugin.warn_limiter.check_limit(mock_context.user.id, "warn", RateLimit(max_calls=1, window_minutes=60))
    assert allowed1 is True

    # Second warn should fail
    allowed2, _ = plugin.warn_limiter.check_limit(mock_context.user.id, "warn", RateLimit(max_calls=1, window_minutes=60))
    assert allowed2 is False


@pytest.mark.asyncio
async def test_timeout_rate_limit(plugin, mock_context):
    """Timeout action respects rate limit."""
    from easycord import RateLimit

    # First timeout should succeed
    allowed1, _ = plugin.timeout_limiter.check_limit(
        mock_context.user.id, "timeout", RateLimit(max_calls=1, window_minutes=60)
    )
    assert allowed1 is True

    # Second timeout should fail
    allowed2, _ = plugin.timeout_limiter.check_limit(
        mock_context.user.id, "timeout", RateLimit(max_calls=1, window_minutes=60)
    )
    assert allowed2 is False


@pytest.mark.asyncio
async def test_add_rule(plugin, mock_guild, mock_context):
    """Admin can add moderation rule."""
    mock_context.guild = mock_guild
    mock_context.send = AsyncMock()

    config_data = {}

    def get_other_side_effect(key, default=None):
        return config_data.get(key, default)

    def set_other_side_effect(key, value):
        config_data[key] = value

    mock_server_cfg = MagicMock(spec=ServerConfig)
    mock_server_cfg.get_other = MagicMock(side_effect=get_other_side_effect)
    mock_server_cfg.set_other = MagicMock(side_effect=set_other_side_effect)

    with patch.object(plugin.config.store, "load", new_callable=AsyncMock, return_value=mock_server_cfg):
        with patch.object(plugin.config.store, "save", new_callable=AsyncMock):
            await plugin.mod_add_rule(mock_context, "spam")

            cfg = await plugin._get_config(mock_guild.id)
            assert "spam" in cfg["rules"]


@pytest.mark.asyncio
async def test_remove_rule(plugin, mock_guild, mock_context):
    """Admin can remove moderation rule."""
    mock_context.guild = mock_guild
    mock_context.send = AsyncMock()

    config_data = {}

    def get_other_side_effect(key, default=None):
        return config_data.get(key, default)

    def set_other_side_effect(key, value):
        config_data[key] = value

    mock_server_cfg = MagicMock(spec=ServerConfig)
    mock_server_cfg.get_other = MagicMock(side_effect=get_other_side_effect)
    mock_server_cfg.set_other = MagicMock(side_effect=set_other_side_effect)

    with patch.object(plugin.config.store, "load", new_callable=AsyncMock, return_value=mock_server_cfg):
        with patch.object(plugin.config.store, "save", new_callable=AsyncMock):
            # Add then remove
            await plugin._update_config(mock_guild.id, rules=["spam", "abuse"])
            await plugin.mod_remove_rule(mock_context, "spam")

            cfg = await plugin._get_config(mock_guild.id)
            assert "spam" not in cfg["rules"]
            assert "abuse" in cfg["rules"]


@pytest.mark.asyncio
async def test_set_threshold(plugin, mock_guild, mock_context):
    """Admin can set confidence threshold."""
    mock_context.guild = mock_guild
    mock_context.send = AsyncMock()

    config_data = {}

    def get_other_side_effect(key, default=None):
        return config_data.get(key, default)

    def set_other_side_effect(key, value):
        config_data[key] = value

    mock_server_cfg = MagicMock(spec=ServerConfig)
    mock_server_cfg.get_other = MagicMock(side_effect=get_other_side_effect)
    mock_server_cfg.set_other = MagicMock(side_effect=set_other_side_effect)

    with patch.object(plugin.config.store, "load", new_callable=AsyncMock, return_value=mock_server_cfg):
        with patch.object(plugin.config.store, "save", new_callable=AsyncMock):
            await plugin.mod_threshold(mock_context, 0.95)

            cfg = await plugin._get_config(mock_guild.id)
            assert cfg["confidence_threshold"] == 0.95


@pytest.mark.asyncio
async def test_set_action_level(plugin, mock_guild, mock_context):
    """Admin can set action level."""
    mock_context.guild = mock_guild
    mock_context.send = AsyncMock()

    config_data = {}

    def get_other_side_effect(key, default=None):
        return config_data.get(key, default)

    def set_other_side_effect(key, value):
        config_data[key] = value

    mock_server_cfg = MagicMock(spec=ServerConfig)
    mock_server_cfg.get_other = MagicMock(side_effect=get_other_side_effect)
    mock_server_cfg.set_other = MagicMock(side_effect=set_other_side_effect)

    with patch.object(plugin.config.store, "load", new_callable=AsyncMock, return_value=mock_server_cfg):
        with patch.object(plugin.config.store, "save", new_callable=AsyncMock):
            await plugin.mod_action_level(mock_context, "auto_delete")

            cfg = await plugin._get_config(mock_guild.id)
            assert cfg["action_level"] == "auto_delete"


@pytest.mark.asyncio
async def test_execute_action_delete(plugin, mock_context, mock_message):
    """Delete action removes message."""
    result = await plugin._execute_action(mock_context, "delete", mock_message.author, "spam", mock_message)
    assert result is True
    mock_message.delete.assert_called_once()


@pytest.mark.asyncio
async def test_execute_action_warn(plugin, mock_context):
    """Warn action sends message."""
    result = await plugin._execute_action(mock_context, "warn", mock_context.user, "spam")
    assert result is True
    mock_context.send.assert_called_once()


def test_conversation_memory_integration(plugin):
    """Plugin uses ConversationMemory for context."""
    assert plugin.conversation_memory is not None
    plugin.conversation_memory.add_user_message(999, "test message", 12345)
    messages = plugin.conversation_memory.get_messages(999, 12345)
    assert len(messages) == 1
    assert messages[0]["role"] == "user"
