"""Decorators for marking Plugin methods as slash commands or event handlers."""
from __future__ import annotations

from typing import Callable


def slash(
    name: str | None = None,
    *,
    description: str = "No description provided.",
    guild_id: int | None = None,
    guild_only: bool = False,
    ephemeral: bool = False,
    permissions: list[str] | None = None,
    cooldown: float | None = None,
    autocomplete: dict[str, Callable] | None = None,
    choices: dict[str, list] | None = None,
    aliases: list[str] | None = None,
    rate_limit: tuple[int, int] | None = None,
) -> Callable:
    """Mark a Plugin method as a slash command.

    Parameters
    ----------
    name:
        The command name shown in Discord. Defaults to the method name.
    description:
        Short description shown in the Discord command picker.
    guild_id:
        Register to one specific server only (instant; global takes up to 1 hour).
    permissions:
        List of ``discord.Permissions`` attribute names required to run the command
        (e.g. ``["kick_members"]``). Responds ephemerally and skips the command if
        any are missing.
    cooldown:
        Per-user cooldown in seconds. Blocks the command ephemerally until the
        window expires.

    Example::

        class MyPlugin(Plugin):

            @slash(description="Kick a member", permissions=["kick_members"])
            async def kick(self, ctx, member: discord.Member):
                await member.kick()
                await ctx.respond(f"Kicked {member.display_name}.")

            @slash(description="Roll a dice", cooldown=5)
            async def roll(self, ctx, sides: int = 6):
                import random
                await ctx.respond(f"You rolled {random.randint(1, sides)}!")
    """

    def decorator(func: Callable) -> Callable:
        func._is_slash = True
        func._slash_name = name or func.__name__
        func._slash_desc = description
        func._slash_guild = guild_id
        func._slash_guild_only = guild_only
        func._slash_ephemeral = ephemeral
        func._slash_permissions = permissions
        func._slash_cooldown = cooldown
        func._slash_autocomplete = autocomplete or {}
        func._slash_choices = choices or {}
        func._slash_aliases = aliases or []
        func._slash_rate_limit = rate_limit
        return func

    return decorator


def task(
    *,
    seconds: float = 0,
    minutes: float = 0,
    hours: float = 0,
) -> Callable:
    """Mark a Plugin method as a repeating background task.

    The task starts automatically when the plugin is loaded and stops when
    the plugin is unloaded. The interval is the sum of the time arguments.

    Example::

        class StatusPlugin(Plugin):

            @task(minutes=5)
            async def update_status(self):
                await self.bot.change_presence(activity=discord.Game("Running..."))
    """
    interval = seconds + minutes * 60.0 + hours * 3600.0
    if interval <= 0:
        raise ValueError("task interval must be greater than zero")

    def decorator(func: Callable) -> Callable:
        func._is_task = True
        func._task_interval = interval
        return func

    return decorator


def on(event: str, *, on_cleanup: Callable | None = None) -> Callable:
    """Mark a Plugin method as an event handler.

    Use the event name without the ``on_`` prefix. Any arguments that
    discord.py normally passes to ``on_<event>`` are forwarded to your method.

    Parameters
    ----------
    event:
        Event name without the ``on_`` prefix (e.g., "member_join", "message").
    on_cleanup:
        Optional async function called when the plugin is unloaded.
        Useful for cleanup like closing connections or removing event listeners.

    Example::

        class MyPlugin(Plugin):

            @on("member_join")
            async def welcome(self, member):
                await member.send(f"Welcome to {member.guild.name}!")

            async def cleanup_resources(self):
                # Called on plugin unload
                pass

            @on("ready", on_cleanup=cleanup_resources)
            async def on_ready(self):
                print("Bot is ready!")
    """

    def decorator(func: Callable) -> Callable:
        func._is_event = True
        func._event_name = event
        func._event_cleanup = on_cleanup
        return func

    return decorator


def user_command(
    name: str | None = None,
    *,
    guild_id: int | None = None,
) -> Callable:
    """Mark a Plugin method as a right-click User context menu command."""
    def decorator(func: Callable) -> Callable:
        func._is_user_command = True
        func._context_menu_name = name or func.__name__
        func._context_menu_guild = guild_id
        return func
    return decorator


def message_command(
    name: str | None = None,
    *,
    guild_id: int | None = None,
) -> Callable:
    """Mark a Plugin method as a right-click Message context menu command."""
    def decorator(func: Callable) -> Callable:
        func._is_message_command = True
        func._context_menu_name = name or func.__name__
        func._context_menu_guild = guild_id
        return func
    return decorator


def component(id_or_func=None, *, scoped: bool = True) -> Callable:
    """Mark a Plugin method as a persistent component (button / select-menu) handler."""
    def _apply(func: Callable, custom_id: str | None) -> Callable:
        func._is_component = True
        func._component_id = custom_id or func.__name__
        func._component_scoped = scoped
        return func

    if callable(id_or_func):
        return _apply(id_or_func, None)

    def decorator(func: Callable) -> Callable:
        return _apply(func, id_or_func)

    return decorator


def modal(id_or_func=None, *, scoped: bool = True) -> Callable:
    """Mark a Plugin method as a modal submission handler."""
    def _apply(func: Callable, custom_id: str | None) -> Callable:
        func._is_modal = True
        func._modal_id = custom_id or func.__name__
        func._modal_scoped = scoped
        return func

    if callable(id_or_func):
        return _apply(id_or_func, None)

    def decorator(func: Callable) -> Callable:
        return _apply(func, id_or_func)

    return decorator


def ai_tool(
    description: str = "No description provided.",
    parameters: dict | None = None,
    rate_limit: tuple[int, int] | None = None,
    permissions: list[str] | None = None,
) -> Callable:
    """Mark a Plugin method as an AI-callable function tool.

    The method will be registered as an available function that the AI can invoke
    during conversation. The method receives the command context and can return
    a string response that the AI includes in its next message.

    Parameters
    ----------
    description:
        Description of what this tool does, shown to the AI.
    parameters:
        JSON schema describing the tool's parameters (if any).
    rate_limit:
        Tuple of (max_calls, window_minutes) to rate limit this tool per user.
    permissions:
        List of Discord permission names required to execute this tool
        (e.g., ["kick_members", "ban_members"]). The AI will check these before invoking.

    Example::

        class MyPlugin(Plugin):

            @ai_tool(description="Get the current member count")
            async def get_member_count(self, ctx):
                return f"Guild has {len(ctx.guild.members)} members"

            @ai_tool(
                description="Ban a user (max 3/hour)",
                parameters={...},
                rate_limit=(3, 60)
            )
            async def ban_user(self, ctx, user_id: int):
                ...
    """

    def decorator(func: Callable) -> Callable:
        func._is_ai_tool = True
        func._ai_tool_name = func.__name__
        func._ai_tool_description = description
        func._ai_tool_parameters = parameters or {}
        func._ai_tool_rate_limit = rate_limit
        func._ai_tool_permissions = permissions or []
        return func

    return decorator
