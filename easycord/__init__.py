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

__version__ = "5.60.0"

from .audit import AuditLog
from .bot import Bot
from .embed_cards import EmbedCard, ErrorEmbed, InfoEmbed, SuccessEmbed, WarningEmbed
from .builders import ButtonRowBuilder, EmbedBuilder, ModalBuilder, SelectMenuBuilder
from .composer import Composer
from .context import Context
from .context_builder import ContextBuilder
from .database import DatabaseConfig, EasyCordDatabase, GuildRecord, MemoryDatabase, SQLiteDatabase
from .config import BotConfig
from .decorators import ai_tool, autocomplete, command_error, component, cooldown, deprecated, describe, install_type, message_command, modal, on, premium_required, require_permissions, slash, slash_command, task, user_command, version_introduced
from .event_bus import EventBus
from .hooks import HookRegistry
from .i18n import LocalizationManager, format_number, format_date
from .group import SlashGroup
from .plugin import Plugin
from ._bot_plugins import PluginDependencyError
from .plugin_creator import (
    PluginCheck,
    PluginCheckReport,
    PluginManifest,
    PluginScaffoldOptions,
    PluginScaffoldResult,
    check_plugin_project,
    create_in_project_plugin,
    create_package_plugin,
    create_plugin_scaffold,
    discover_plugins,
    load_entrypoint_plugins,
    load_plugin_manifest,
    validate_plugin_manifest,
)
from .middleware import AnalyticsStore, analytics_middleware
from .server_config import ServerConfig, ServerConfigStore
from .tools import ToolCall, ToolDef, ToolRegistry, ToolResult, ToolSafety, audit_tool_registry
from .orchestrator import FallbackStrategy, Orchestrator, ProviderStrategy, RunContext
from .tool_limits import RateLimit, ToolLimiter
from .conversation_memory import Conversation, ConversationMemory, ConversationTurn
from .helpers import ConfigHelpers, ContextHelpers, RateLimitHelpers, ToolHelpers
from .helpers.channel import SENDABLE_CHANNEL_TYPES
from .managers import FrameworkManager, SecurityManager
from .utils import EasyEmbed, Paginator
from .validators import ChoiceSet, Duration, Range, Regex, Snowflake, URL, ValidationError
from .formatters import format_doctor_report, format_interaction_inventory, format_sync_plan, format_tool_audit
from .security import escape_mentions, safe_regex, strip_injection_prefixes, truncate
from .plugins import SecurityLabPlugin

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
    "AuditLog",
    "audit_tool_registry",
    "ai_tool",
    "autocomplete",
    "Bot",
    "BotConfig",
    "ButtonRowBuilder",
    "ChoiceSet",
    "command_error",
    "Composer",
    "ConfigHelpers",
    "check_plugin_project",
    "Conversation",
    "ConversationMemory",
    "ConversationTurn",
    "Context",
    "ContextBuilder",
    "ContextHelpers",
    "create_in_project_plugin",
    "create_package_plugin",
    "create_plugin_scaffold",
    "deprecated",
    "describe",
    "discover_plugins",
    "Duration",
    "EmbedBuilder",
    "EmbedCard",
    "DatabaseConfig",
    "EasyCordDatabase",
    "EventBus",
    "FallbackStrategy",
    "format_doctor_report",
    "format_interaction_inventory",
    "format_sync_plan",
    "format_tool_audit",
    "component",
    "cooldown",
    "ErrorEmbed",
    "EasyEmbed",
    "FrameworkManager",
    "GuildRecord",
    "HookRegistry",
    "InfoEmbed",
    "install_type",
    "ModalBuilder",
    "message_command",
    "modal",
    "MemoryDatabase",
    "LocalizationManager",
    "format_number",
    "format_date",
    "load_entrypoint_plugins",
    "load_plugin_manifest",
    "Orchestrator",
    "Plugin",
    "PluginCheck",
    "PluginCheckReport",
    "PluginManifest",
    "Paginator",
    "PluginScaffoldOptions",
    "PluginScaffoldResult",
    "ProviderStrategy",
    "premium_required",
    "RateLimit",
    "RateLimitHelpers",
    "Range",
    "Regex",
    "RunContext",
    "require_permissions",
    "SENDABLE_CHANNEL_TYPES",
    "SelectMenuBuilder",
    "SlashGroup",
    "SuccessEmbed",
    "SecurityLabPlugin",
    "SecurityManager",
    "escape_mentions",
    "safe_regex",
    "strip_injection_prefixes",
    "truncate",
    "ToolCall",
    "ToolDef",
    "ToolHelpers",
    "ToolLimiter",
    "ToolRegistry",
    "ToolResult",
    "ToolSafety",
    "slash",
    "slash_command",
    "Snowflake",
    "on",
    "SQLiteDatabase",
    "WarningEmbed",
    "user_command",
    "task",
    "ServerConfig",
    "ServerConfigStore",
    "URL",
    "validate_plugin_manifest",
    "ValidationError",
    "version_introduced",
]
