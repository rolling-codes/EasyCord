"""Registration helpers for Discord application commands."""
from __future__ import annotations

import inspect
import logging
from typing import Callable, Union

import discord
from discord import app_commands

from ._command_callbacks import build_context_menu_callback

logger = logging.getLogger("easycord")


def register_slash(
    bot: object,
    func: Callable,
    *,
    callback_builder: Callable[..., Callable],
    context_factory: Callable[[discord.Interaction], object],
    name: str,
    description: str,
    guild_id: int | None,
    guild_only: bool = False,
    require_admin: bool = False,
    ephemeral: bool = False,
    permissions: list[str] | None = None,
    cooldown: float | None = None,
    cooldown_rate: int = 1,
    cooldown_bucket: str = "user",
    premium_required: bool = False,
    autocomplete: dict[str, Callable] | None = None,
    choices: dict[str, list] | None = None,
    nsfw: bool = False,
    allowed_contexts: app_commands.AppCommandContext | None = None,
    allowed_installs: app_commands.AppInstallationType | None = None,
    parent: app_commands.Group | None = None,
    source_plugin: str | None = None,
) -> None:
    """Register a callable as a slash command."""
    guild = discord.Object(id=guild_id) if guild_id else None
    callback = callback_builder(
        func,
        guild_only=guild_only,
        require_admin=require_admin,
        ephemeral=ephemeral,
        permissions=permissions,
        cooldown=cooldown,
        cooldown_rate=cooldown_rate,
        cooldown_bucket=cooldown_bucket,
        premium_required=premium_required,
        command_name=name,
    )
    autocomplete_handlers: dict[str, Callable] = {
        **(autocomplete or {}),
        **getattr(func, "_slash_autocomplete_handlers", {}),
    }
    if choices:
        inject_choices(callback, choices)
    cmd = app_commands.Command(
        name=name,
        description=description,
        callback=callback,
        nsfw=nsfw,
        allowed_contexts=allowed_contexts,
        allowed_installs=allowed_installs,
    )
    for param_name, handler in autocomplete_handlers.items():
        _register_autocomplete_handler(
            bot,
            cmd,
            name=name,
            param_name=param_name,
            handler=handler,
            source_plugin=source_plugin,
            guild_id=guild_id,
            context_factory=context_factory,
        )
    if parent is not None:
        parent.add_command(cmd)
    else:
        bot.tree.add_command(cmd, guild=guild)
    registry_name = f"{parent.name} {name}" if parent is not None else name
    bot.registry.register_slash_command(
        registry_name,
        func,
        source_plugin=source_plugin,
        guild_id=guild_id,
        metadata={
            "description": description,
            "guild_only": guild_only,
            "permissions": permissions,
            "cooldown": cooldown,
            "cooldown_rate": cooldown_rate,
            "cooldown_bucket": cooldown_bucket,
            "premium_required": premium_required,
            "allowed_contexts": allowed_contexts,
            "allowed_installs": allowed_installs,
            "parent": getattr(parent, "name", None),
        },
    )


def _register_autocomplete_handler(
    bot: object,
    cmd: app_commands.Command,
    *,
    name: str,
    param_name: str,
    handler: Callable,
    source_plugin: str | None,
    guild_id: int | None,
    context_factory: Callable[[discord.Interaction], object],
) -> None:
    sig = inspect.signature(handler)
    params = list(sig.parameters.values())
    param_count = len(params)

    if param_count not in (1, 3):
        plugin_info = f" in plugin {source_plugin}" if source_plugin else ""
        raise TypeError(
            f"Invalid autocomplete signature for option {param_name!r} "
            f"of command {name!r}{plugin_info}. "
            f"Expected (current) or (ctx, current, options), got {sig}."
        )

    expects_options = param_count == 3

    def _make_autocomplete(_h: Callable, _expects_options: bool) -> Callable:
        async def _ac(
            interaction: discord.Interaction,
            current: str,
        ) -> list[app_commands.Choice]:
            ctx = context_factory(interaction)
            options = autocomplete_options(interaction)
            try:
                if _expects_options:
                    results = await _h(ctx, current, options)
                else:
                    results = await _h(current)
                return [app_commands.Choice(name=r, value=r) for r in results]
            except Exception as exc:
                plugin_instance = getattr(_h, "__self__", None)
                if plugin_instance is None and source_plugin:
                    plugin_instance = next(
                        (
                            p
                            for p in bot._plugins
                            if getattr(p, "_instance_id", type(p).__name__)
                            == source_plugin
                        ),
                        None,
                    )
                await bot._dispatch_framework_error(
                    exc,
                    ctx=ctx,
                    plugin_instance=plugin_instance,
                )
                return []

        return _ac

    ac_callback = _make_autocomplete(handler, expects_options)
    cmd.autocomplete(param_name)(ac_callback)
    bot.registry.register_autocomplete(
        name,
        param_name,
        handler,
        source_plugin=source_plugin,
        guild_id=guild_id,
    )


def register_context_menu(
    bot: object,
    func: Callable,
    *,
    context_factory: Callable[[discord.Interaction], object],
    chain_builder: Callable,
    name: str,
    menu_type: discord.AppCommandType,
    guild_id: int | None,
    nsfw: bool = False,
    allowed_contexts: app_commands.AppCommandContext | None = None,
    allowed_installs: app_commands.AppInstallationType | None = None,
    source_plugin: str | None = None,
) -> None:
    """Build and register an app_commands.ContextMenu."""
    guild = discord.Object(id=guild_id) if guild_id else None
    sig = inspect.signature(func)
    params = list(sig.parameters.values())
    target_name = params[1].name if len(params) > 1 else "target"

    if menu_type == discord.AppCommandType.user:
        target_annotation: type = Union[discord.Member, discord.User]  # type: ignore[assignment]
    else:
        target_annotation = discord.Message

    interaction_param = inspect.Parameter(
        "interaction",
        inspect.Parameter.POSITIONAL_OR_KEYWORD,
        annotation=discord.Interaction,
    )
    target_param = inspect.Parameter(
        target_name,
        inspect.Parameter.POSITIONAL_OR_KEYWORD,
        annotation=target_annotation,
    )

    callback = build_context_menu_callback(
        bot,
        func,
        context_factory=context_factory,
        chain_builder=chain_builder,
    )
    callback.__signature__ = inspect.Signature(
        parameters=[interaction_param, target_param]
    )
    menu = app_commands.ContextMenu(
        name=name,
        callback=callback,
        type=menu_type,
        nsfw=nsfw,
        allowed_contexts=allowed_contexts,
        allowed_installs=allowed_installs,
    )
    bot.tree.add_command(menu, guild=guild)
    bot.registry.register_context_menu(
        name,
        func,
        source_plugin=source_plugin,
        guild_id=guild_id,
        metadata={
            "menu_type": menu_type.name,
            "nsfw": nsfw,
            "allowed_contexts": allowed_contexts,
            "allowed_installs": allowed_installs,
        },
    )
    logger.debug("Registered context menu %r (type=%s)", name, menu_type.name)


def inject_choices(callback: Callable, choices: dict[str, list]) -> None:
    """Stamp discord.py's internal choices attribute onto a command callback."""
    if not hasattr(callback, "__discord_app_commands_param_choices__"):
        callback.__discord_app_commands_param_choices__ = {}
    for param_name, values in choices.items():
        callback.__discord_app_commands_param_choices__[param_name] = [
            app_commands.Choice(name=str(v), value=v) for v in values
        ]


def autocomplete_options(interaction: discord.Interaction) -> dict[str, object]:
    """Extract current autocomplete option values from a Discord interaction."""
    namespace = getattr(interaction, "namespace", None)
    if namespace is not None:
        try:
            return dict(vars(namespace))
        except TypeError:
            pass
    data = getattr(interaction, "data", None) or {}
    options: dict[str, object] = {}
    for item in data.get("options", []):
        if "name" in item and "value" in item:
            options[item["name"]] = item["value"]
    return options
