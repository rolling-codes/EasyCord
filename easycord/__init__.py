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

__all__ = [
    "AuditLog",
    "ai_tool",
    "Bot",
    "ButtonRowBuilder",
    "Composer",
    "Context",
    "ContextBuilder",
    "EmbedBuilder",
    "EmbedCard",
    "DatabaseConfig",
    "EasyCordDatabase",
    "FallbackStrategy",
    "component",
    "ErrorEmbed",
    "GuildRecord",
    "InfoEmbed",
    "ModalBuilder",
    "message_command",
    "modal",
    "MemoryDatabase",
    "LocalizationManager",
    "Orchestrator",
    "Plugin",
    "ProviderStrategy",
    "RunContext",
    "SelectMenuBuilder",
    "SlashGroup",
    "SuccessEmbed",
    "ToolCall",
    "ToolDef",
    "ToolRegistry",
    "ToolResult",
    "ToolSafety",
    "slash",
    "on",
    "SQLiteDatabase",
    "WarningEmbed",
    "user_command",
    "task",
    "ServerConfig",
    "ServerConfigStore",
]
