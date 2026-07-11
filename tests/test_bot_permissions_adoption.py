"""Phase 1 (01-01) regression net: bot_permissions adoption.

Locks the current adoption state of ``bot_permissions`` across the built-in
plugins.  Two categories of guards:

*Denial tests* — commands that declare ``bot_permissions`` must respond with
the localised "I'm missing the following permission(s)" message and must NOT
execute their handler body when the bot lacks a declared permission.

*Structural tests* — config-setter commands (welcome, starboard, auto_role)
must NOT declare ``bot_permissions``; they write guild config, not privileged
Discord API, so adding ``bot_permissions`` would trigger false denials on
configured-channel sends made by event handlers (B-021 misleading-preflight
lesson).

Permission checks fire in ``build_slash_callback`` before the handler body,
so denial tests do not need to supply all required kwargs — the abort fires
first and the handler body is never reached.
"""
from __future__ import annotations

from unittest.mock import MagicMock

from easycord import Bot
from easycord.testing import invoke

_MISSING_MSG = "missing the following permission"


def _bot(*plugins) -> Bot:
    bot = Bot(auto_sync=False, db_backend="memory")
    for p in plugins:
        bot.add_plugin(p)
    return bot


# ---------------------------------------------------------------------------
# Tickets — create_private_threads / manage_threads
# ---------------------------------------------------------------------------

class TestTicketsBotPermissions:
    """Ticket commands declare bot_permissions; absent perms must deny fast."""

    async def test_ticket_open_denied_without_create_private_threads(self) -> None:
        from easycord.plugins.tickets import TicketsPlugin

        ctx = await invoke(
            _bot(TicketsPlugin()),
            "ticket_open",
            permissions={"create_private_threads": False},
        )
        assert ctx.last_response is not None
        assert _MISSING_MSG in ctx.last_response.lower()
        assert "create_private_threads" in ctx.last_response

    async def test_ticket_open_not_denied_when_perm_granted(self) -> None:
        from easycord.plugins.tickets import TicketsPlugin

        ctx = await invoke(
            _bot(TicketsPlugin()),
            "ticket_open",
            permissions={"create_private_threads": True},
        )
        assert _MISSING_MSG not in (ctx.last_response or "").lower()

    async def test_ticket_close_denied_without_manage_threads(self) -> None:
        from easycord.plugins.tickets import TicketsPlugin

        ctx = await invoke(
            _bot(TicketsPlugin()),
            "ticket_close",
            permissions={"manage_threads": False},
        )
        assert ctx.last_response is not None
        assert _MISSING_MSG in ctx.last_response.lower()
        assert "manage_threads" in ctx.last_response

    async def test_ticket_add_denied_without_manage_threads(self) -> None:
        from easycord.plugins.tickets import TicketsPlugin

        ctx = await invoke(
            _bot(TicketsPlugin()),
            "ticket_add",
            permissions={"manage_threads": False},
            user=MagicMock(),
        )
        assert ctx.last_response is not None
        assert _MISSING_MSG in ctx.last_response.lower()
        assert "manage_threads" in ctx.last_response


# ---------------------------------------------------------------------------
# Giveaway — send_messages
# ---------------------------------------------------------------------------

class TestGiveawayBotPermissions:
    async def test_giveaway_denied_without_send_messages(self) -> None:
        from easycord.plugins.giveaway import GiveawayPlugin

        ctx = await invoke(
            _bot(GiveawayPlugin()),
            "giveaway",
            permissions={"send_messages": False},
            prize="Prize",
            duration="1m",
            winners=1,
        )
        assert ctx.last_response is not None
        assert _MISSING_MSG in ctx.last_response.lower()
        assert "send_messages" in ctx.last_response

    async def test_giveaway_not_denied_when_perm_granted(self) -> None:
        from easycord.plugins.giveaway import GiveawayPlugin

        ctx = await invoke(
            _bot(GiveawayPlugin()),
            "giveaway",
            permissions={"send_messages": True},
            prize="Prize",
            duration="1m",
            winners=1,
        )
        assert _MISSING_MSG not in (ctx.last_response or "").lower()


# ---------------------------------------------------------------------------
# Polls — send_messages
# ---------------------------------------------------------------------------

class TestPollsBotPermissions:
    async def test_poll_denied_without_send_messages(self) -> None:
        from easycord.plugins.polls import PollsPlugin

        ctx = await invoke(
            _bot(PollsPlugin()),
            "poll",
            permissions={"send_messages": False},
            question="Best?",
            option1="A",
            option2="B",
        )
        assert ctx.last_response is not None
        assert _MISSING_MSG in ctx.last_response.lower()
        assert "send_messages" in ctx.last_response

    async def test_poll_not_denied_when_perm_granted(self) -> None:
        from easycord.plugins.polls import PollsPlugin

        ctx = await invoke(
            _bot(PollsPlugin()),
            "poll",
            permissions={"send_messages": True},
            question="Best?",
            option1="A",
            option2="B",
        )
        assert _MISSING_MSG not in (ctx.last_response or "").lower()


# ---------------------------------------------------------------------------
# Word filter — manage_messages
# ---------------------------------------------------------------------------

class TestWordFilterBotPermissions:
    async def test_filter_action_denied_without_manage_messages(self) -> None:
        from easycord.plugins.word_filter import WordFilterPlugin

        ctx = await invoke(
            _bot(WordFilterPlugin()),
            "filter_action",
            permissions={"manage_messages": False, "manage_guild": True},
            action="delete",
        )
        assert ctx.last_response is not None
        assert _MISSING_MSG in ctx.last_response.lower()
        assert "manage_messages" in ctx.last_response

    async def test_filter_action_not_denied_when_perm_granted(self) -> None:
        from easycord.plugins.word_filter import WordFilterPlugin

        ctx = await invoke(
            _bot(WordFilterPlugin()),
            "filter_action",
            permissions={"manage_messages": True, "manage_guild": True},
            action="delete",
        )
        assert _MISSING_MSG not in (ctx.last_response or "").lower()


# ---------------------------------------------------------------------------
# Moderation — kick_members / ban_members
# ---------------------------------------------------------------------------

class TestModerationBotPermissions:
    async def test_kick_denied_without_kick_members(self) -> None:
        from easycord.plugins.moderation import ModerationPlugin

        ctx = await invoke(
            _bot(ModerationPlugin()),
            "kick",
            permissions={"kick_members": False},
            user=MagicMock(),
            reason="test",
        )
        assert ctx.last_response is not None
        assert _MISSING_MSG in ctx.last_response.lower()
        assert "kick_members" in ctx.last_response

    async def test_ban_denied_without_ban_members(self) -> None:
        from easycord.plugins.moderation import ModerationPlugin

        ctx = await invoke(
            _bot(ModerationPlugin()),
            "ban",
            permissions={"ban_members": False},
            user=MagicMock(),
            reason="test",
        )
        assert ctx.last_response is not None
        assert _MISSING_MSG in ctx.last_response.lower()
        assert "ban_members" in ctx.last_response


# ---------------------------------------------------------------------------
# Structural check: config-setters must NOT declare bot_permissions (B-021)
# ---------------------------------------------------------------------------

class TestConfigSettersNoBotPermissions:
    """Commands that only write guild config must not declare bot_permissions.

    The B-021 lesson: ``bot_permissions`` validates the INVOCATION channel, not
    a configured target channel.  Adding it to config-setters or event handlers
    would cause false denials when the bot sends to a different (configured)
    channel that it actually has access to.
    """

    def _slash_fns(self, plugin_cls) -> list:
        return [
            fn
            for fn in vars(plugin_cls).values()
            if callable(fn) and getattr(fn, "_is_slash", False)
        ]

    def test_welcome_config_setters_have_no_bot_permissions(self) -> None:
        from easycord.plugins.welcome import WelcomePlugin

        for fn in self._slash_fns(WelcomePlugin):
            bp = getattr(fn, "_slash_bot_permissions", None)
            assert bp is None, (
                f"WelcomePlugin.{fn.__name__} declares bot_permissions={bp!r}. "
                f"Config-setters must not have bot_permissions preflights (B-021)."
            )

    def test_starboard_config_setters_have_no_bot_permissions(self) -> None:
        from easycord.plugins.starboard import StarboardPlugin

        for fn in self._slash_fns(StarboardPlugin):
            bp = getattr(fn, "_slash_bot_permissions", None)
            assert bp is None, (
                f"StarboardPlugin.{fn.__name__} declares bot_permissions={bp!r}. "
                f"Config-setters must not have bot_permissions preflights (B-021)."
            )

    def test_auto_role_config_setters_have_no_bot_permissions(self) -> None:
        from easycord.plugins.auto_role import AutoRolePlugin

        for fn in self._slash_fns(AutoRolePlugin):
            bp = getattr(fn, "_slash_bot_permissions", None)
            assert bp is None, (
                f"AutoRolePlugin.{fn.__name__} declares bot_permissions={bp!r}. "
                f"Config-setters must not have bot_permissions preflights (B-021)."
            )

    def test_member_logging_commands_have_no_bot_permissions(self) -> None:
        from easycord.plugins.member_logging import MemberLoggingPlugin

        for fn in self._slash_fns(MemberLoggingPlugin):
            bp = getattr(fn, "_slash_bot_permissions", None)
            assert bp is None, (
                f"MemberLoggingPlugin.{fn.__name__} declares bot_permissions={bp!r}. "
                f"Config-setters must not have bot_permissions preflights (B-021)."
            )
