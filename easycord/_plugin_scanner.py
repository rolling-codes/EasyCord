"""Plugin method scanning and registration helpers."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, cast

import discord

from .tool_limits import RateLimit
from .tools import ToolSafety

if TYPE_CHECKING:
    from .plugin import Plugin


def scan_plugin_methods(
    bot: "_BotBase",
    plugin: "Plugin",
    *,
    iter_methods: Callable[[object], list[tuple[str, Any]]],
    parent=None,
) -> None:
    """Register decorated plugin methods on *bot*."""
    plugin_name = getattr(plugin, "_instance_id", str(id(plugin)))
    methods = iter_methods(plugin)
    standalone_autocomplete = _collect_standalone_autocomplete(methods)

    for _, method in methods:
        if getattr(method, "_is_slash", False):
            _register_slash_methods(
                bot,
                method,
                plugin_name=plugin_name,
                standalone_autocomplete=standalone_autocomplete,
                parent=parent,
            )
        if getattr(method, "_is_command_error", False):
            bot._command_error_handlers[method._command_error_for] = method
        if getattr(method, "_is_event", False):
            bot._event_handlers.setdefault(method._event_name, []).append(method)
        if getattr(method, "_is_user_command", False):
            _register_context_menu(
                bot,
                method,
                plugin_name=plugin_name,
                menu_type=discord.AppCommandType.user,
            )
        if getattr(method, "_is_message_command", False):
            _register_context_menu(
                bot,
                method,
                plugin_name=plugin_name,
                menu_type=discord.AppCommandType.message,
            )
        if getattr(method, "_is_component", False):
            custom_id = method._component_id
            if getattr(method, "_component_scoped", True):
                custom_id = plugin.id(custom_id)
            bot._register_component_handler(
                custom_id,
                method,
                source_plugin=plugin_name,
                ttl=getattr(method, "_component_ttl", None),
            )
        if getattr(method, "_is_modal", False):
            custom_id = method._modal_id
            if getattr(method, "_modal_scoped", True):
                custom_id = plugin.id(custom_id)
            bot._register_modal_handler(custom_id, method, source_plugin=plugin_name)
        if getattr(method, "_is_ai_tool", False):
            _register_ai_tool(bot, method)
        if getattr(method, "_is_subscription", False):
            bot.event_bus.subscribe(method._subscription_event, method)


def _collect_standalone_autocomplete(
    methods: list[tuple[str, Any]],
) -> dict[str, dict[str, Callable]]:
    standalone_autocomplete: dict[str, dict[str, Callable]] = {}
    for _, method in methods:
        if getattr(method, "_is_autocomplete", False):
            standalone_autocomplete.setdefault(
                method._autocomplete_command,
                {},
            )[method._autocomplete_option] = method
    return standalone_autocomplete


def _register_slash_methods(
    bot: "_BotBase",
    method: Callable,
    *,
    plugin_name: str,
    standalone_autocomplete: dict[str, dict[str, Callable]],
    parent,
) -> None:
    autocomplete_handlers = {
        **getattr(method, "_slash_autocomplete", {}),
        **standalone_autocomplete.get(method._slash_name, {}),
    }
    for command_name in [method._slash_name] + list(
        getattr(method, "_slash_aliases", [])
    ):
        bot._register_slash(
            method,
            name=command_name,
            description=method._slash_desc,
            guild_id=method._slash_guild,
            guild_only=getattr(method, "_slash_guild_only", False),
            require_admin=getattr(method, "_slash_require_admin", False),
            ephemeral=getattr(method, "_slash_ephemeral", False),
            permissions=getattr(method, "_slash_permissions", None),
            bot_permissions=getattr(method, "_slash_bot_permissions", None),
            cooldown=getattr(method, "_slash_cooldown", None),
            cooldown_rate=getattr(method, "_slash_cooldown_rate", 1),
            cooldown_bucket=getattr(method, "_slash_cooldown_bucket", "user"),
            premium_required=getattr(method, "_slash_premium_required", False),
            autocomplete=autocomplete_handlers,
            choices=getattr(method, "_slash_choices", None),
            nsfw=getattr(method, "_slash_nsfw", False),
            allowed_contexts=getattr(method, "_slash_allowed_contexts", None),
            allowed_installs=getattr(method, "_slash_allowed_installs", None),
            parent=parent,
            source_plugin=plugin_name,
        )


def _register_context_menu(
    bot: "_BotBase",
    method: Callable,
    *,
    plugin_name: str,
    menu_type: discord.AppCommandType,
) -> None:
    bot._register_context_menu(
        method,
        name=method._context_menu_name,
        menu_type=menu_type,
        guild_id=method._context_menu_guild,
        nsfw=getattr(method, "_context_menu_nsfw", False),
        allowed_contexts=getattr(method, "_context_menu_allowed_contexts", None),
        allowed_installs=getattr(method, "_context_menu_allowed_installs", None),
        source_plugin=plugin_name,
    )


def _register_ai_tool(bot: "_BotBase", method: Callable) -> None:
    tool_name = cast(str, getattr(method, "_ai_tool_name"))
    description = cast(str, getattr(method, "_ai_tool_description"))
    parameters = cast(dict[str, Any], getattr(method, "_ai_tool_parameters"))
    rate_limit = getattr(method, "_ai_tool_rate_limit", None)
    rate_limit_obj = (
        RateLimit(max_calls=rate_limit[0], window_minutes=rate_limit[1])
        if rate_limit
        else None
    )
    safety = cast(ToolSafety, getattr(method, "_ai_tool_safety", ToolSafety.SAFE))
    bot.ai_tools[tool_name] = {
        "name": tool_name,
        "description": description,
        "func": method,
        "parameters": parameters,
        "safety": safety,
        "require_guild": getattr(method, "_ai_tool_require_guild", True),
        "require_admin": getattr(method, "_ai_tool_require_admin", False),
        "allowed_roles": getattr(method, "_ai_tool_allowed_roles", []),
        "allowed_users": getattr(method, "_ai_tool_allowed_users", []),
        "timeout_ms": getattr(method, "_ai_tool_timeout_ms", 5000),
        "rate_limit": rate_limit_obj,
    }
    if tool_name not in bot.tool_registry._tools:
        bot.tool_registry.register(
            name=tool_name,
            func=method,
            description=description,
            safety=safety,
            parameters=parameters,
            require_guild=getattr(method, "_ai_tool_require_guild", True),
            require_admin=getattr(method, "_ai_tool_require_admin", False),
            allowed_roles=getattr(method, "_ai_tool_allowed_roles", []),
            allowed_users=getattr(method, "_ai_tool_allowed_users", []),
            permissions=getattr(method, "_ai_tool_permissions", []),
            timeout_ms=getattr(method, "_ai_tool_timeout_ms", 5000),
            rate_limit=rate_limit_obj,
        )
    if safety is ToolSafety.RESTRICTED:
        bot.tool_registry.disable(tool_name)
