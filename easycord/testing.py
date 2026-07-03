"""Testing helpers for EasyCord commands.

These helpers let tests exercise registered commands without connecting to
Discord.  They intentionally model only the interaction attributes EasyCord
uses during command dispatch.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import discord

from .context import Context


class _FakePermissions:
    """Permission object that defaults unknown permissions to ``False``."""

    def __init__(self, **values: bool) -> None:
        self.administrator = False
        for name, value in values.items():
            setattr(self, name, bool(value))

    def __getattr__(self, name: str) -> bool:
        return False


@dataclass
class _CapturedResponse:
    content: str | None = None
    ephemeral: bool = False
    embed: discord.Embed | None = None
    kwargs: dict[str, Any] = field(default_factory=dict)


class _FakeResponder:
    def __init__(self, interaction: "FakeInteraction") -> None:
        self._interaction = interaction
        self.send_message = AsyncMock(side_effect=self._send_message)
        self.defer = AsyncMock(side_effect=self._defer)

    async def _send_message(
        self,
        content: str | None = None,
        *,
        ephemeral: bool = False,
        embed: discord.Embed | None = None,
        **kwargs: Any,
    ) -> None:
        self._interaction._responses.append(
            _CapturedResponse(content, ephemeral, embed, dict(kwargs))
        )

    async def _defer(self, *, ephemeral: bool = False, **_: Any) -> None:
        self._interaction._deferred = True
        self._interaction._deferred_ephemeral = ephemeral


class _FakeFollowup:
    def __init__(self, interaction: "FakeInteraction") -> None:
        self._interaction = interaction
        self.send = AsyncMock(side_effect=self._send)

    async def _send(
        self,
        content: str | None = None,
        *,
        ephemeral: bool = False,
        embed: discord.Embed | None = None,
        **kwargs: Any,
    ) -> None:
        self._interaction._responses.append(
            _CapturedResponse(content, ephemeral, embed, dict(kwargs))
        )


class FakeInteraction:
    """Small fake ``discord.Interaction`` for command unit tests."""

    def __init__(
        self,
        *,
        client: Any | None = None,
        command: Any | None = None,
        user_id: int = 1,
        guild_id: int | None = 100,
        is_admin: bool = False,
        entitlements: list[Any] | None = None,
        locale: str | None = None,
        guild_locale: str | None = None,
        permissions: dict[str, bool] | None = None,
        roles: list[int] | None = None,
        message_id: int = 900000000000000001,
    ) -> None:
        permission_values = dict(permissions or {})
        permission_values.setdefault("administrator", is_admin)
        guild_permissions = _FakePermissions(**permission_values)
        role_mocks = []
        for role_id in roles or []:
            role = MagicMock(spec=discord.Role)
            role.id = role_id
            role.name = f"Role {role_id}"
            role_mocks.append(role)

        self.user = MagicMock(spec=discord.Member if guild_id is not None else discord.User)
        self.user.id = user_id
        self.user.name = f"user-{user_id}"
        self.user.display_name = f"User {user_id}"
        self.user.guild_permissions = guild_permissions
        self.user.roles = role_mocks
        self.user.voice = None

        self.guild = None
        if guild_id is not None:
            self.guild = MagicMock(spec=discord.Guild)
            self.guild.id = guild_id
            self.guild.name = f"Guild {guild_id}"
            self.guild.get_member.return_value = self.user
            self.guild.fetch_member = AsyncMock(return_value=self.user)
            self.guild.me = MagicMock()
            self.guild.roles = role_mocks

        self.channel = MagicMock()
        self.channel.send = AsyncMock()
        self.channel.permissions_for = MagicMock(return_value=guild_permissions)
        self.command = command
        self.data: dict[str, Any] = {}
        self.locale = locale
        self.guild_locale = guild_locale
        self.context = None
        self.entitlements = entitlements or []
        self.client = client or SimpleNamespace(
            localization=None,
            i18n=None,
            ai_provider=None,
            conversation_memory=None,
            get_channel=lambda _channel_id: None,
            fetch_channel=AsyncMock(return_value=None),
        )

        self._responses: list[_CapturedResponse] = []
        self._deferred = False
        self._deferred_ephemeral = False
        self.response = _FakeResponder(self)
        self.followup = _FakeFollowup(self)
        self.edit_original_response = AsyncMock()

        self._message = SimpleNamespace(id=message_id, edit=AsyncMock())
        self.original_response = AsyncMock(return_value=self._message)


class FakeContext(Context):
    """``Context`` with response capture helpers for assertions."""

    @classmethod
    def make(
        cls,
        *,
        client: Any | None = None,
        command: Any | None = None,
        user_id: int = 1,
        guild_id: int | None = 100,
        is_admin: bool = False,
        entitlements: list[Any] | None = None,
        permissions: dict[str, bool] | None = None,
        roles: list[int] | None = None,
    ) -> "FakeContext":
        interaction = FakeInteraction(
            client=client,
            command=command,
            user_id=user_id,
            guild_id=guild_id,
            is_admin=is_admin,
            entitlements=entitlements,
            permissions=permissions,
            roles=roles,
        )
        return cls(interaction)  # type: ignore[arg-type]

    @property
    def member(self) -> discord.Member | None:
        return self.guild.get_member(self.user.id) if self.guild else None

    @property
    def responses(self) -> list[_CapturedResponse]:
        return self.interaction._responses  # type: ignore[attr-defined]

    @property
    def response_count(self) -> int:
        return len(self.responses)

    @property
    def last_response(self) -> str | None:
        return self.responses[-1].content if self.responses else None

    @property
    def was_ephemeral(self) -> bool:
        return self.responses[-1].ephemeral if self.responses else False

    def assert_content(self, expected: str) -> None:
        assert self.last_response == expected

    def assert_contains(self, expected: str) -> None:
        assert self.last_response is not None
        assert expected in self.last_response


class FakeContextBuilder:
    """Fluent builder for offline ``Context`` objects in command tests."""

    def __init__(self) -> None:
        self._client: Any | None = None
        self._command: Any | None = None
        self._user_id = 1
        self._user_name: str | None = None
        self._display_name: str | None = None
        self._guild_id: int | None = 100
        self._guild_name: str | None = None
        self._is_admin = False
        self._entitlements: list[Any] | None = None
        self._locale: str | None = None
        self._guild_locale: str | None = None
        self._permissions: dict[str, bool] = {}
        self._roles: list[int] = []
        self._data: dict[str, Any] = {}

    def with_client(self, client: Any) -> "FakeContextBuilder":
        self._client = client
        return self

    def with_command(self, command: Any) -> "FakeContextBuilder":
        self._command = command
        return self

    def with_user(
        self,
        user_id: int,
        *,
        name: str | None = None,
        display_name: str | None = None,
    ) -> "FakeContextBuilder":
        self._user_id = user_id
        self._user_name = name
        self._display_name = display_name
        return self

    def in_guild(
        self,
        guild_id: int = 100,
        *,
        name: str | None = None,
    ) -> "FakeContextBuilder":
        self._guild_id = guild_id
        self._guild_name = name
        return self

    def in_dm(self) -> "FakeContextBuilder":
        self._guild_id = None
        self._guild_name = None
        return self

    def as_admin(self, value: bool = True) -> "FakeContextBuilder":
        self._is_admin = value
        return self

    def with_permissions(
        self,
        **permissions: bool,
    ) -> "FakeContextBuilder":
        self._permissions.update({name: bool(value) for name, value in permissions.items()})
        return self

    def with_roles(self, *role_ids: int) -> "FakeContextBuilder":
        self._roles = list(role_ids)
        return self

    def with_entitlements(self, *entitlements: Any) -> "FakeContextBuilder":
        self._entitlements = list(entitlements)
        return self

    def with_locale(
        self,
        locale: str | None = None,
        *,
        guild_locale: str | None = None,
    ) -> "FakeContextBuilder":
        self._locale = locale
        self._guild_locale = guild_locale
        return self

    def with_data(self, **data: Any) -> "FakeContextBuilder":
        self._data.update(data)
        return self

    def build_interaction(self) -> FakeInteraction:
        interaction = FakeInteraction(
            client=self._client,
            command=self._command,
            user_id=self._user_id,
            guild_id=self._guild_id,
            is_admin=self._is_admin,
            entitlements=self._entitlements,
            locale=self._locale,
            guild_locale=self._guild_locale,
            permissions=self._permissions,
            roles=self._roles,
        )
        if self._user_name is not None:
            interaction.user.name = self._user_name
        if self._display_name is not None:
            interaction.user.display_name = self._display_name
        if interaction.guild is not None and self._guild_name is not None:
            interaction.guild.name = self._guild_name
        if self._data:
            interaction.data.update(self._data)
        return interaction

    def build(self) -> FakeContext:
        return FakeContext(self.build_interaction())  # type: ignore[arg-type]


async def invoke(
    bot: Any,
    command_name: str,
    *,
    user_id: int = 1,
    guild_id: int | None = 100,
    is_admin: bool = True,
    entitlements: list[Any] | None = None,
    permissions: dict[str, bool] | None = None,
    **kwargs: Any,
) -> FakeContext:
    """Invoke a registered slash command and return a captured context."""

    command = bot.tree.get_command(command_name)
    if command is None:
        available = ", ".join(sorted(cmd.name for cmd in bot.tree.walk_commands()))
        raise LookupError(f"Command {command_name!r} is not registered. Available: {available}")

    interaction = FakeInteraction(
        client=bot,
        command=command,
        user_id=user_id,
        guild_id=guild_id,
        is_admin=is_admin,
        entitlements=entitlements,
        permissions=permissions,
    )
    await command.callback(interaction, **kwargs)
    return FakeContext(interaction)  # type: ignore[arg-type]


async def invoke_autocomplete(
    bot: Any,
    command_name: str,
    option_name: str,
    current: str,
    *,
    user_id: int = 1,
    guild_id: int | None = 100,
    options: dict[str, Any] | None = None,
) -> list[Any]:
    """Invoke a registered autocomplete callback without Discord."""

    for entry in bot.registry.autocomplete_callbacks.values():
        if (
            entry.metadata.get("command_name") == command_name
            and entry.metadata.get("option_name") == option_name
        ):
            interaction = FakeInteraction(
                client=bot,
                command=bot.tree.get_command(command_name),
                user_id=user_id,
                guild_id=guild_id,
            )
            interaction.namespace = SimpleNamespace(**(options or {}))  # type: ignore[attr-defined]
            ctx = FakeContext(interaction)  # type: ignore[arg-type]
            try:
                return list(await entry.callback(ctx, current, options or {}))
            except TypeError:
                return list(await entry.callback(current))
    raise LookupError(
        f"Autocomplete for {command_name!r}.{option_name!r} is not registered."
    )


async def invoke_component(
    bot: Any,
    custom_id: str,
    *,
    user_id: int = 1,
    guild_id: int | None = 100,
    **data: Any,
) -> FakeContext:
    """Invoke a registered component handler without Discord."""

    entry, _ = bot.registry.resolve_component(custom_id)
    if entry is None:
        legacy_match = any(
            registered_id.endswith("_") and custom_id.startswith(registered_id)
            for registered_id in bot.registry.components
        )
        if not legacy_match:
            raise LookupError(f"Component {custom_id!r} is not registered.")

    interaction = FakeInteraction(
        client=bot,
        user_id=user_id,
        guild_id=guild_id,
    )
    interaction.data = {"custom_id": custom_id, **data}
    await bot._dispatch_component(interaction)
    return FakeContext(interaction)  # type: ignore[arg-type]


async def invoke_modal(
    bot: Any,
    custom_id: str,
    *,
    user_id: int = 1,
    guild_id: int | None = 100,
    **fields: Any,
) -> FakeContext:
    """Invoke a registered modal handler without Discord."""

    if custom_id not in bot.registry.modals:
        raise LookupError(f"Modal {custom_id!r} is not registered.")

    interaction = FakeInteraction(
        client=bot,
        user_id=user_id,
        guild_id=guild_id,
    )
    interaction.data = {
        "custom_id": custom_id,
        "components": [
            {
                "components": [
                    {"custom_id": key, "value": value}
                    for key, value in fields.items()
                ]
            }
        ],
    }
    await bot._dispatch_modal(interaction)
    return FakeContext(interaction)  # type: ignore[arg-type]


def _find_context_menu(bot: Any, name: str, menu_type: discord.AppCommandType) -> Any:
    command = bot.tree.get_command(name, type=menu_type)
    if command is None:
        available = ", ".join(
            sorted(cmd.name for cmd in bot.tree.get_commands(type=menu_type))
        )
        raise LookupError(
            f"Context menu {name!r} is not registered. Available: {available}"
        )
    return command


async def invoke_user_command(
    bot: Any,
    command_name: str,
    *,
    target: discord.Member | discord.User | None = None,
    target_id: int = 2,
    user_id: int = 1,
    guild_id: int | None = 100,
    is_admin: bool = True,
    permissions: dict[str, bool] | None = None,
) -> FakeContext:
    """Invoke a registered User context menu command without Discord."""

    command = _find_context_menu(bot, command_name, discord.AppCommandType.user)
    interaction = FakeInteraction(
        client=bot,
        command=command,
        user_id=user_id,
        guild_id=guild_id,
        is_admin=is_admin,
        permissions=permissions,
    )
    if target is None:
        target = MagicMock(spec=discord.Member if guild_id is not None else discord.User)
        target.id = target_id
        target.name = f"target-{target_id}"
        target.display_name = f"Target {target_id}"
        target.guild = interaction.guild

    await command.callback(interaction, target)
    return FakeContext(interaction)  # type: ignore[arg-type]


async def invoke_message_command(
    bot: Any,
    command_name: str,
    *,
    target: discord.Message | None = None,
    content: str = "message content",
    target_id: int = 10,
    user_id: int = 1,
    guild_id: int | None = 100,
    is_admin: bool = True,
    permissions: dict[str, bool] | None = None,
) -> FakeContext:
    """Invoke a registered Message context menu command without Discord."""

    command = _find_context_menu(bot, command_name, discord.AppCommandType.message)
    interaction = FakeInteraction(
        client=bot,
        command=command,
        user_id=user_id,
        guild_id=guild_id,
        is_admin=is_admin,
        permissions=permissions,
    )
    if target is None:
        target = MagicMock(spec=discord.Message)
        target.id = target_id
        target.content = content
        target.author = interaction.user
        target.guild = interaction.guild
        target.channel = interaction.channel

    await command.callback(interaction, target)
    return FakeContext(interaction)  # type: ignore[arg-type]


class PluginTestSuite:
    """Base class for plugin tests.

    Provides a pre-wired in-memory bot, a ``make_plugin`` factory that follows
    the EasyCord ``__new__`` / ``Plugin.__init__`` construction pattern, and a
    set of assertion helpers that mirror ``FakeContext``'s own methods.

    Usage (pytest)::

        from easycord import Plugin, slash
        from easycord.testing import PluginTestSuite

        class PingPlugin(Plugin):
            @slash(description="Ping")
            async def ping(self, ctx):
                await ctx.respond("Pong!")

        class TestPingPlugin(PluginTestSuite):
            def setup_method(self):
                super().setup_method()
                self.plugin = self.make_plugin(PingPlugin)

            async def test_ping_responds_pong(self):
                ctx = await self.invoke_command("ping")
                self.assert_last_response(ctx, "Pong!")

    The class also works as a ``unittest.TestCase`` base — override
    ``setUp`` instead of ``setup_method``, calling ``super().setUp()``.
    """

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def setup_method(self) -> None:
        """pytest lifecycle hook — creates a fresh in-memory bot."""
        from easycord import Bot

        self.bot = Bot(auto_sync=False, db_backend="memory")

    # unittest.TestCase compat alias
    setUp = setup_method  # type: ignore[assignment]

    # ------------------------------------------------------------------
    # Plugin factory
    # ------------------------------------------------------------------

    def make_plugin(self, cls: "type[Any]", *init_args: Any, **init_kwargs: Any) -> Any:
        """Construct *cls* and register it with the test bot.

        If the plugin's __init__ accepts arguments, pass them as *init_args / **init_kwargs.
        For zero-argument plugins, uses ``cls.__new__(cls)`` + ``Plugin.__init__`` for direct control.
        The plugin is registered via ``self.bot.add_plugin()``, which wires ``_bot``.

        Example::

            # Simple plugin with no constructor args
            plugin = self.make_plugin(MyPlugin)

            # Plugin with constructor args
            plugin = self.make_plugin(WelcomePlugin, data_dir=".easycord/welcome")
        """
        from .plugin import Plugin as _Plugin

        if init_args or init_kwargs:
            # Plugin has custom constructor args — call normally
            plugin = cls(*init_args, **init_kwargs)
        else:
            # Zero-arg plugin — use __new__ + Plugin.__init__ for clarity
            plugin: _Plugin = object.__new__(cls)  # type: ignore[arg-type]
            _Plugin.__init__(plugin)
        self.bot.add_plugin(plugin)  # type: ignore[arg-type]
        return plugin

    # ------------------------------------------------------------------
    # Command invocation shorthand
    # ------------------------------------------------------------------

    async def invoke_command(
        self,
        command_name: str,
        *,
        user_id: int = 1,
        guild_id: int | None = 100,
        is_admin: bool = True,
        **options: Any,
    ) -> "FakeContext":
        """Invoke a registered slash command and return the ``FakeContext``."""
        return await invoke(
            self.bot,
            command_name,
            user_id=user_id,
            guild_id=guild_id,
            is_admin=is_admin,
            **options,
        )

    # ------------------------------------------------------------------
    # Assertion helpers
    # ------------------------------------------------------------------

    def assert_last_response(self, ctx: "FakeContext", expected: str) -> None:
        """Assert that *ctx.last_response* equals *expected*."""
        assert ctx.last_response == expected, (
            f"Expected {expected!r}, got {ctx.last_response!r}"
        )

    def assert_response_contains(self, ctx: "FakeContext", substring: str) -> None:
        """Assert that *ctx.last_response* contains *substring*."""
        assert substring in (ctx.last_response or ""), (
            f"Expected {substring!r} in response, got {ctx.last_response!r}"
        )

    def assert_ephemeral(self, ctx: "FakeContext") -> None:
        """Assert that the last response was sent as ephemeral."""
        assert ctx.was_ephemeral, "Expected last response to be ephemeral, but it was not."

    def assert_response_count(self, ctx: "FakeContext", count: int) -> None:
        """Assert the exact number of responses captured on *ctx*."""
        assert ctx.response_count == count, (
            f"Expected {count} response(s), got {ctx.response_count}"
        )


__all__ = [
    "FakeContext",
    "FakeContextBuilder",
    "FakeInteraction",
    "invoke",
    "invoke_autocomplete",
    "invoke_component",
    "invoke_message_command",
    "invoke_modal",
    "invoke_user_command",
    "PluginTestSuite",
]
