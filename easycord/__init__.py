"""
A developer-friendly framework for building Discord bots.

Quick start::

    from easycord import Bot
    from easycord.middleware import log_middleware

    bot = Bot()
    bot.use(log_middleware())

    @bot.slash(description="Ping the bot")
    async def ping(ctx):
        await ctx.respond("Pong!")

    bot.run("YOUR_TOKEN")
"""

__version__ = "5.1.1"

from .audit import AuditLog
from .bot import Bot
from .embed_cards import EmbedCard, ErrorEmbed, InfoEmbed, SuccessEmbed, WarningEmbed
from .builders import ButtonRowBuilder, EmbedBuilder, ModalBuilder, SelectMenuBuilder
from .composer import Composer
from .context import Context
from .context_builder import ContextBuilder
from .database import DatabaseConfig, EasyCordDatabase, GuildRecord, MemoryDatabase, SQLiteDatabase
from .decorators import ai_tool, component, message_command, modal, on, slash, task, user_command
from .i18n import LocalizationManager
from .group import SlashGroup
from .plugin import Plugin
from .server_config import ServerConfig, ServerConfigStore
from .tools import ToolCall, ToolDef, ToolRegistry, ToolResult, ToolSafety
from .orchestrator import FallbackStrategy, Orchestrator, ProviderStrategy, RunContext
from .tool_limits import RateLimit, ToolLimiter
from .conversation_memory import Conversation, ConversationMemory, ConversationTurn
from .helpers import ConfigHelpers, ContextHelpers, RateLimitHelpers, ToolHelpers
from .managers import FrameworkManager, SecurityManager
from .utils import EasyEmbed, Paginator

_PROVIDER_NAMES = frozenset({
    "AIProvider",
    "AnthropicProvider",
    "GeminiProvider",
    "GroqProvider",
    "HuggingFaceProvider",
    "LiteLLMProvider",
    "MistralProvider",
    "OllamaProvider",
    "OpenAIProvider",
    "TogetherAIProvider",
})


def __getattr__(name: str):
    if name in _PROVIDER_NAMES:
        from easycord.plugins import _ai_providers as _m
        return getattr(_m, name)
    raise AttributeError(f"module 'easycord' has no attribute {name!r}")


__all__ = [
    "__version__",
    "AIProvider",
    "AnthropicProvider",
    "AuditLog",
    "ai_tool",
    "Bot",
    "ButtonRowBuilder",
    "Composer",
    "ConfigHelpers",
    "Conversation",
    "ConversationMemory",
    "ConversationTurn",
    "Context",
    "ContextBuilder",
    "ContextHelpers",
    "EmbedBuilder",
    "EmbedCard",
    "DatabaseConfig",
    "EasyCordDatabase",
    "FallbackStrategy",
    "GeminiProvider",
    "GroqProvider",
    "HuggingFaceProvider",
    "LiteLLMProvider",
    "MistralProvider",
    "OllamaProvider",
    "OpenAIProvider",
    "component",
    "ErrorEmbed",
    "EasyEmbed",
    "FrameworkManager",
    "GuildRecord",
    "InfoEmbed",
    "ModalBuilder",
    "message_command",
    "modal",
    "MemoryDatabase",
    "LocalizationManager",
    "Orchestrator",
    "Plugin",
    "Paginator",
    "ProviderStrategy",
    "RateLimit",
    "RateLimitHelpers",
    "RunContext",
    "SelectMenuBuilder",
    "SlashGroup",
    "SuccessEmbed",
    "SecurityManager",
    "ToolCall",
    "ToolDef",
    "ToolHelpers",
    "ToolLimiter",
    "ToolRegistry",
    "ToolResult",
    "ToolSafety",
    "TogetherAIProvider",
    "slash",
    "on",
    "SQLiteDatabase",
    "WarningEmbed",
    "user_command",
    "task",
    "ServerConfig",
    "ServerConfigStore",
]
