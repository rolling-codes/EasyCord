"""Unit tests for eight untested built-in plugins.

Each class instantiates the plugin with a real temp-backed config store
(never writing to the project directory) and drives the internal methods
directly via mocked discord objects.
"""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest

from easycord.plugins._config_manager import PluginConfigManager
from easycord.plugins.member_logging import MemberLoggingPlugin
from easycord.plugins.moderation import ModerationPlugin
from easycord.plugins.polls import (
    PollsPlugin,
    _bar,
    _format_option_line,
    _is_valid_duration,
    _poll_options,
    _PollView,
    _tally,
    build_poll_embed,
)
from easycord.plugins.reaction_roles import ReactionRolesPlugin
from easycord.plugins.starboard import StarboardPlugin
from easycord.plugins.suggestions import SuggestionsPlugin
from easycord.plugins.tags import TagsPlugin, TagsStore
from easycord.server_config import ServerConfigStore
from easycord.tool_limits import ToolLimiter


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_ctx(*, user_id: int = 1, guild_id: int = 100, is_admin: bool = False) -> MagicMock:
    ctx = MagicMock()
    ctx.user = MagicMock(spec=discord.Member)
    ctx.user.id = user_id
    ctx.user.name = "TestUser"
    ctx.user.avatar = None
    ctx.user.discriminator = "0001"
    ctx.user.mention = f"<@{user_id}>"
    perms = MagicMock(spec=discord.Permissions)
    perms.manage_guild = is_admin
    perms.manage_roles = is_admin
    perms.kick_members = is_admin
    perms.ban_members = is_admin
    perms.moderate_members = is_admin
    perms.administrator = is_admin
    ctx.user.guild_permissions = perms
    ctx.guild = MagicMock(spec=discord.Guild)
    ctx.guild.id = guild_id
    ctx.guild_id = guild_id
    ctx.respond = AsyncMock()
    ctx.t = lambda key, default="", **kw: default.format(**kw) if kw else default
    ctx.paginate = AsyncMock()
    return ctx


def _make_member(*, user_id: int = 1, guild_id: int = 100) -> MagicMock:
    m = MagicMock(spec=discord.Member)
    m.id = user_id
    m.name = f"User{user_id}"
    m.discriminator = "0001"
    m.mention = f"<@{user_id}>"
    m.avatar = None
    m.joined_at = datetime.now(timezone.utc)
    m.created_at = datetime.now(timezone.utc)
    m.timed_out_until = None
    m.roles = []
    m.nick = None
    m.guild = MagicMock(spec=discord.Guild)
    m.guild.id = guild_id
    return m


# ---------------------------------------------------------------------------
# StarboardPlugin
# ---------------------------------------------------------------------------

class TestStarboardPlugin:

    def _make_plugin(self, tmp_path) -> StarboardPlugin:
        p = StarboardPlugin.__new__(StarboardPlugin)
        p.config = PluginConfigManager(str(tmp_path / "starboard"))
        p._bot = MagicMock()
        return p

    @pytest.mark.asyncio
    async def test_get_archived_empty(self, tmp_path) -> None:
        """_get_archived returns an empty dict when nothing is stored."""
        p = self._make_plugin(tmp_path)
        result = await p._get_archived(999)
        assert result == {}

    @pytest.mark.asyncio
    async def test_set_and_get_archived(self, tmp_path) -> None:
        """_set_archived stores a message_id → post_id mapping."""
        p = self._make_plugin(tmp_path)
        await p._set_archived(100, message_id=1111, post_id=2222)
        result = await p._get_archived(100)
        assert result["1111"] == 2222

    @pytest.mark.asyncio
    async def test_remove_archived(self, tmp_path) -> None:
        """_remove_archived deletes the mapping."""
        p = self._make_plugin(tmp_path)
        await p._set_archived(100, message_id=5555, post_id=6666)
        await p._remove_archived(100, message_id=5555)
        result = await p._get_archived(100)
        assert "5555" not in result

    @pytest.mark.asyncio
    async def test_remove_archived_missing_id_no_error(self, tmp_path) -> None:
        """_remove_archived on a non-existent id does not raise."""
        p = self._make_plugin(tmp_path)
        await p._remove_archived(100, message_id=9999)  # should not raise

    @pytest.mark.asyncio
    async def test_get_config_defaults(self, tmp_path) -> None:
        """_get_config returns the default threshold of 3."""
        p = self._make_plugin(tmp_path)
        cfg = await p._get_config(guild_id=100)
        assert cfg.get("threshold") == 3
        assert cfg.get("emoji") == "⭐"
        assert cfg.get("enabled") is True

    @pytest.mark.asyncio
    async def test_update_config_persists(self, tmp_path) -> None:
        """_update_config writes and reads back the new value."""
        p = self._make_plugin(tmp_path)
        await p._update_config(100, threshold=10)
        cfg = await p._get_config(100)
        assert cfg.get("threshold") == 10


# ---------------------------------------------------------------------------
# SuggestionsPlugin
# ---------------------------------------------------------------------------

class TestSuggestionsPlugin:

    def _make_plugin(self, tmp_path) -> SuggestionsPlugin:
        p = SuggestionsPlugin.__new__(SuggestionsPlugin)
        p.config = PluginConfigManager(str(tmp_path / "suggestions"))
        p.suggestion_counter = {}
        p._bot = MagicMock()
        return p

    @pytest.mark.asyncio
    async def test_get_config_defaults(self, tmp_path) -> None:
        p = self._make_plugin(tmp_path)
        cfg = await p._get_config(100)
        assert cfg.get("enabled") is True
        assert cfg.get("suggestions_channel") is None

    @pytest.mark.asyncio
    async def test_suggest_without_channel_responds_error(self, tmp_path) -> None:
        """suggest() responds with error when no channel is configured."""
        p = self._make_plugin(tmp_path)
        ctx = _make_ctx()
        await p.suggest(ctx, idea="Make the bot faster")
        ctx.respond.assert_called_once()
        args, kwargs = ctx.respond.call_args
        assert "not configured" in (args[0] if args else "") or kwargs.get("ephemeral")

    @pytest.mark.asyncio
    async def test_suggestions_list_empty(self, tmp_path) -> None:
        """suggestions() responds with 'No pending suggestions' when empty."""
        p = self._make_plugin(tmp_path)
        ctx = _make_ctx()
        await p.suggestions(ctx)
        ctx.respond.assert_called_once_with("No pending suggestions")

    @pytest.mark.asyncio
    async def test_suggestion_approve_not_found(self, tmp_path) -> None:
        """suggestion_approve() responds with error for non-existent ID."""
        p = self._make_plugin(tmp_path)
        ctx = _make_ctx(is_admin=True)
        await p.suggestion_approve(ctx, suggestion_id=9999)
        ctx.respond.assert_called_once()
        args, _ = ctx.respond.call_args
        assert "not found" in args[0].lower()

    @pytest.mark.asyncio
    async def test_suggestion_reject_not_found(self, tmp_path) -> None:
        p = self._make_plugin(tmp_path)
        ctx = _make_ctx(is_admin=True)
        await p.suggestion_reject(ctx, suggestion_id=1234)
        ctx.respond.assert_called_once()
        args, _ = ctx.respond.call_args
        assert "not found" in args[0].lower()

    @pytest.mark.asyncio
    async def test_suggestion_approve_no_permission(self, tmp_path) -> None:
        """suggestion_approve() blocks users without manage_guild."""
        p = self._make_plugin(tmp_path)
        ctx = _make_ctx(is_admin=False)
        await p.suggestion_approve(ctx, suggestion_id=1)
        ctx.respond.assert_called_once()
        args, kwargs = ctx.respond.call_args
        text = args[0] if args else ""
        assert "lack" in text.lower() or kwargs.get("ephemeral")


# ---------------------------------------------------------------------------
# ReactionRolesPlugin
# ---------------------------------------------------------------------------

class TestReactionRolesPlugin:

    def _make_plugin(self, tmp_path) -> ReactionRolesPlugin:
        p = ReactionRolesPlugin.__new__(ReactionRolesPlugin)
        p.config_store = ServerConfigStore(str(tmp_path / "reaction-roles"))
        p._bot = MagicMock()
        return p

    @pytest.mark.asyncio
    async def test_get_mappings_empty(self, tmp_path) -> None:
        p = self._make_plugin(tmp_path)
        result = await p._get_mappings(guild_id=100, message_id=5555)
        assert result == {}

    @pytest.mark.asyncio
    async def test_set_and_get_mapping(self, tmp_path) -> None:
        p = self._make_plugin(tmp_path)
        await p._set_mapping(100, 5555, "⭐", role_id=777)
        mappings = await p._get_mappings(100, 5555)
        assert mappings.get("⭐") == 777

    @pytest.mark.asyncio
    async def test_remove_mapping(self, tmp_path) -> None:
        p = self._make_plugin(tmp_path)
        await p._set_mapping(100, 5555, "❤️", role_id=888)
        await p._remove_mapping(100, 5555, "❤️")
        mappings = await p._get_mappings(100, 5555)
        assert "❤️" not in mappings

    @pytest.mark.asyncio
    async def test_on_reaction_add_assigns_role(self, tmp_path) -> None:
        """_on_reaction_add calls member.add_roles when mapping exists."""
        p = self._make_plugin(tmp_path)
        await p._set_mapping(guild_id=100, message_id=9000, emoji="⭐", role_id=555)

        guild = MagicMock(spec=discord.Guild)
        guild.id = 100
        role = MagicMock(spec=discord.Role)
        role.name = "Star Role"
        guild.get_role = MagicMock(return_value=role)
        member = MagicMock(spec=discord.Member)
        member.add_roles = AsyncMock()
        guild.get_member = MagicMock(return_value=member)
        mock_bot = MagicMock()
        mock_bot.get_guild = MagicMock(return_value=guild)
        mock_bot.user.id = 999
        p._bot = mock_bot  # type: ignore[assignment]

        emoji = MagicMock()
        emoji.__str__ = MagicMock(return_value="⭐")
        payload = MagicMock(spec=discord.RawReactionActionEvent)
        payload.guild_id = 100
        payload.user_id = 1
        payload.message_id = 9000
        payload.emoji = emoji

        await p._on_reaction_add(payload)
        member.add_roles.assert_called_once_with(role, reason="ReactionRolesPlugin")

    @pytest.mark.asyncio
    async def test_on_role_delete_cleans_mappings(self, tmp_path) -> None:
        """_on_role_delete removes all emoji mappings for the deleted role."""
        p = self._make_plugin(tmp_path)
        await p._set_mapping(100, 1000, "🎖", role_id=42)
        await p._set_mapping(100, 1000, "🏆", role_id=99)  # different role

        role = MagicMock(spec=discord.Role)
        role.id = 42
        role.name = "Old Role"
        guild = MagicMock(spec=discord.Guild)
        guild.id = 100
        role.guild = guild

        await p._on_role_delete(role)

        mappings = await p._get_mappings(100, 1000)
        assert "🎖" not in mappings
        assert mappings.get("🏆") == 99  # unrelated role survives

    @pytest.mark.asyncio
    async def test_on_message_delete_cleans_all_emoji(self, tmp_path) -> None:
        """_on_message_delete removes all mappings for the deleted message."""
        p = self._make_plugin(tmp_path)
        await p._set_mapping(100, 7777, "🌟", role_id=11)
        await p._set_mapping(100, 7777, "💫", role_id=22)

        payload = MagicMock(spec=discord.RawMessageDeleteEvent)
        payload.guild_id = 100
        payload.message_id = 7777

        await p._on_message_delete(payload)

        mappings = await p._get_mappings(100, 7777)
        assert mappings == {}


# ---------------------------------------------------------------------------
# ModerationPlugin
# ---------------------------------------------------------------------------

class TestModerationPlugin:

    def _make_plugin(self, tmp_path) -> ModerationPlugin:
        p = ModerationPlugin.__new__(ModerationPlugin)
        p.config = PluginConfigManager(str(tmp_path / "moderation"))
        p.warn_limiter = ToolLimiter()
        p.ban_limiter = ToolLimiter()
        p._bot = MagicMock()
        return p

    @pytest.mark.asyncio
    async def test_get_config_defaults(self, tmp_path) -> None:
        p = self._make_plugin(tmp_path)
        cfg = await p._get_config(100)
        assert cfg.get("auto_warn_threshold") == 3
        assert cfg.get("enable_warnings") is True

    @pytest.mark.asyncio
    async def test_kick_no_permission(self, tmp_path) -> None:
        """kick() responds with error when moderator lacks permission."""
        p = self._make_plugin(tmp_path)
        ctx = _make_ctx(is_admin=False)
        user = MagicMock(spec=discord.User)
        user.id = 5
        user.mention = "<@5>"
        await p.kick(ctx, user=user)
        ctx.respond.assert_called_once()
        args, _ = ctx.respond.call_args
        assert "lack" in args[0].lower()

    @pytest.mark.asyncio
    async def test_kick_user_not_in_server(self, tmp_path) -> None:
        """kick() responds with error when target not in guild."""
        p = self._make_plugin(tmp_path)
        ctx = _make_ctx(is_admin=True)
        ctx.guild.get_member = MagicMock(return_value=None)
        user = MagicMock(spec=discord.User)
        user.id = 5
        user.mention = "<@5>"
        await p.kick(ctx, user=user)
        ctx.respond.assert_called_once()
        args, _ = ctx.respond.call_args
        assert "not in" in args[0].lower()

    @pytest.mark.asyncio
    async def test_warn_increments_count(self, tmp_path) -> None:
        """warn() stores a warning entry for the target user."""
        p = self._make_plugin(tmp_path)
        ctx = _make_ctx(is_admin=True)
        user = MagicMock(spec=discord.User)
        user.id = 77
        user.mention = "<@77>"
        ctx.guild.get_member = MagicMock(return_value=None)

        await p.warn(ctx, user=user, reason="spamming")
        ctx.respond.assert_called()

        cfg_obj = await p.config.store.load(100)
        warnings = cfg_obj.get_other("warnings", {})
        assert len(warnings.get("77", [])) == 1

    @pytest.mark.asyncio
    async def test_warn_no_permission(self, tmp_path) -> None:
        p = self._make_plugin(tmp_path)
        ctx = _make_ctx(is_admin=False)
        user = MagicMock(spec=discord.User)
        user.id = 2
        await p.warn(ctx, user=user)
        ctx.respond.assert_called_once()
        args, _ = ctx.respond.call_args
        assert "lack" in args[0].lower()

    @pytest.mark.asyncio
    async def test_warnings_no_entries(self, tmp_path) -> None:
        """warnings() responds cleanly when user has no warnings."""
        p = self._make_plugin(tmp_path)
        ctx = _make_ctx()
        user = MagicMock(spec=discord.User)
        user.id = 42
        user.mention = "<@42>"
        await p.warnings(ctx, user=user)
        ctx.respond.assert_called_once()
        args, _ = ctx.respond.call_args
        assert "no warnings" in args[0].lower()

    @pytest.mark.asyncio
    async def test_unban_not_banned_responds_not_banned(self, tmp_path) -> None:
        """unban() handles discord.NotFound gracefully."""
        p = self._make_plugin(tmp_path)
        ctx = _make_ctx(is_admin=True)
        ctx.guild.unban = AsyncMock(side_effect=discord.NotFound(MagicMock(), "not banned"))
        user = MagicMock(spec=discord.User)
        user.id = 9
        user.mention = "<@9>"
        await p.unban(ctx, user=user)
        ctx.respond.assert_called_once()
        args, _ = ctx.respond.call_args
        assert "not banned" in args[0].lower()


# ---------------------------------------------------------------------------
# PollsPlugin — _PollView tests (no Plugin needed)
# ---------------------------------------------------------------------------

class TestPollView:

    def test_poll_options_filters_blank(self) -> None:
        """_poll_options strips empty/whitespace-only entries."""
        result = _poll_options("A", "", "  ", "B")
        assert result == ["A", "B"]

    def test_is_valid_duration_minimum(self) -> None:
        assert _is_valid_duration(5) is True
        assert _is_valid_duration(4) is False

    def test_tally_zero_votes(self) -> None:
        counts = _tally(["A", "B", "C"], {})
        assert counts == [0, 0, 0]

    def test_tally_records_votes_correctly(self) -> None:
        votes = {"1": 0, "2": 0, "3": 1, "4": 2}  # 2 for X, 1 for Y, 1 for Z
        counts = _tally(["X", "Y", "Z"], votes)
        assert counts == [2, 1, 1]

    def test_single_vote_overwrites(self) -> None:
        """Assigning a new option to the same user replaces the old vote."""
        votes: dict[str, int] = {}
        votes["1"] = 0  # voted Red
        votes["1"] = 1  # changed to Blue
        counts = _tally(["Red", "Blue"], votes)
        assert counts == [0, 1]

    def test_format_option_line_100_percent(self) -> None:
        line = _format_option_line("Only", count=3, total=3)
        assert "100%" in line
        assert "Only" in line

    def test_format_option_line_zero_votes(self) -> None:
        line = _format_option_line("A", count=0, total=1)
        assert "0%" in line

    def test_build_embed_open(self) -> None:
        embed = build_poll_embed("Open poll", ["Yes", "No"], {}, closed=False, seconds_remaining=30)
        assert embed.title is not None and "Open poll" in embed.title
        assert embed.footer.text is not None and embed.footer.text.startswith("⏱️")

    def test_build_embed_closed(self) -> None:
        embed = build_poll_embed("Closed poll", ["Yes", "No"], {}, closed=True)
        assert embed.footer.text is not None and "closed" in embed.footer.text.lower()

    def test_bar_length_always_10(self) -> None:
        for filled in range(11):
            bar = _bar(filled)
            assert len(bar) == 10

    def test_buttons_have_deterministic_custom_ids(self) -> None:
        plugin = PollsPlugin()
        view = _PollView(plugin, 100, 555, "X", ["A", "B"])
        custom_ids = [child.custom_id for child in view.children]  # type: ignore[union-attr]
        assert custom_ids == ["poll:vote:555:0", "poll:vote:555:1"]


# ---------------------------------------------------------------------------
# TagsPlugin
# ---------------------------------------------------------------------------

class TestTagsPlugin:

    def _make_store(self, tmp_path) -> TagsStore:
        return TagsStore(str(tmp_path / "tags"))

    @pytest.mark.asyncio
    async def test_set_and_get(self, tmp_path) -> None:
        store = self._make_store(tmp_path)
        await store.set(100, "hello", "Hello World!", author_id=1)
        entry = store.get(100, "hello")
        assert entry is not None
        assert entry["text"] == "Hello World!"
        assert entry["author_id"] == 1

    def test_get_nonexistent_returns_none(self, tmp_path) -> None:
        store = self._make_store(tmp_path)
        assert store.get(100, "no_such_tag") is None

    @pytest.mark.asyncio
    async def test_delete_removes_tag(self, tmp_path) -> None:
        store = self._make_store(tmp_path)
        await store.set(100, "bye", "Goodbye!", author_id=1)
        await store.delete(100, "bye")
        assert store.get(100, "bye") is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent_no_error(self, tmp_path) -> None:
        store = self._make_store(tmp_path)
        await store.delete(100, "phantom_tag")  # must not raise

    @pytest.mark.asyncio
    async def test_list_names_sorted(self, tmp_path) -> None:
        store = self._make_store(tmp_path)
        await store.set(100, "zebra", "z", author_id=1)
        await store.set(100, "alpha", "a", author_id=1)
        await store.set(100, "middle", "m", author_id=1)
        names = store.list_names(100)
        assert names == ["alpha", "middle", "zebra"]

    def test_list_names_empty(self, tmp_path) -> None:
        store = self._make_store(tmp_path)
        assert store.list_names(100) == []

    @pytest.mark.asyncio
    async def test_plugin_get_missing_responds_not_found(self, tmp_path) -> None:
        plugin = TagsPlugin(data_dir=str(tmp_path / "tags"))
        ctx = _make_ctx()
        await plugin.get(ctx, name="nonexistent")
        ctx.respond.assert_called_once()
        args, kwargs = ctx.respond.call_args
        assert kwargs.get("ephemeral") is True

    @pytest.mark.asyncio
    async def test_plugin_delete_non_owner_non_admin_blocked(self, tmp_path) -> None:
        plugin = TagsPlugin(data_dir=str(tmp_path / "tags"))
        await plugin._store.set(100, "mytag", "content", author_id=999)

        ctx = _make_ctx(user_id=1, is_admin=False)
        ctx.guild.get_member = MagicMock(return_value=None)
        await plugin.delete(ctx, name="mytag")
        ctx.respond.assert_called_once()
        args, kwargs = ctx.respond.call_args
        assert kwargs.get("ephemeral") is True

    @pytest.mark.asyncio
    async def test_plugin_delete_by_owner_succeeds(self, tmp_path) -> None:
        plugin = TagsPlugin(data_dir=str(tmp_path / "tags"))
        await plugin._store.set(100, "mytag", "content", author_id=1)

        ctx = _make_ctx(user_id=1, is_admin=False)
        ctx.guild.get_member = MagicMock(return_value=None)
        await plugin.delete(ctx, name="mytag")
        assert plugin._store.get(100, "mytag") is None

    @pytest.mark.asyncio
    async def test_plugin_list_empty_responds_ephemeral(self, tmp_path) -> None:
        plugin = TagsPlugin(data_dir=str(tmp_path / "tags"))
        ctx = _make_ctx()
        await plugin.list(ctx)
        ctx.respond.assert_called_once()
        _, kwargs = ctx.respond.call_args
        assert kwargs.get("ephemeral") is True


# ---------------------------------------------------------------------------
# InviteTrackerPlugin
# ---------------------------------------------------------------------------

class TestInviteTrackerPlugin:

    def _make_plugin(self, tmp_path):
        from easycord.plugins.invite_tracker import InviteTrackerPlugin
        p = InviteTrackerPlugin.__new__(InviteTrackerPlugin)
        p.config = PluginConfigManager(str(tmp_path / "invite-tracker"))
        p._invite_cache = {}
        p._bot = MagicMock()
        return p

    @pytest.mark.asyncio
    async def test_cache_starts_empty(self, tmp_path) -> None:
        p = self._make_plugin(tmp_path)
        assert p._invite_cache == {}

    @pytest.mark.asyncio
    async def test_invite_create_updates_cache(self, tmp_path) -> None:
        """_on_invite_create stores new invite code in cache."""
        p = self._make_plugin(tmp_path)

        invite = MagicMock(spec=discord.Invite)
        invite.code = "ABC123"
        invite.uses = 0
        guild = MagicMock(spec=discord.Guild)
        guild.id = 100
        invite.guild = guild

        await p._on_invite_create(invite)
        assert p._invite_cache[100]["ABC123"] == 0

    @pytest.mark.asyncio
    async def test_invite_create_uses_none_treated_as_zero(self, tmp_path) -> None:
        """invite.uses=None (int|None) must be stored as 0, not raise TypeError."""
        p = self._make_plugin(tmp_path)

        invite = MagicMock(spec=discord.Invite)
        invite.code = "NULL_USES"
        invite.uses = None
        guild = MagicMock(spec=discord.Guild)
        guild.id = 100
        invite.guild = guild

        await p._on_invite_create(invite)
        assert p._invite_cache[100]["NULL_USES"] == 0

    @pytest.mark.asyncio
    async def test_log_invite_skips_non_sendable_channel(self, tmp_path) -> None:
        """_log_invite must skip channels not in SENDABLE_CHANNEL_TYPES."""
        p = self._make_plugin(tmp_path)

        member = MagicMock(spec=discord.Member)
        member.guild = MagicMock(spec=discord.Guild)
        member.guild.id = 100
        member.guild.get_channel.return_value = MagicMock(spec=discord.CategoryChannel)

        config = {"enabled": True, "log_channel": 999}
        p.config = MagicMock()
        p.config.get = AsyncMock(return_value=config)

        # Must return without raising even though channel is not sendable
        await p._log_invite(member, "SOMECODE")
        member.guild.get_channel.assert_called_once_with(999)

    @pytest.mark.asyncio
    async def test_invite_delete_removes_from_cache(self, tmp_path) -> None:
        """_on_invite_delete removes the invite code from cache."""
        p = self._make_plugin(tmp_path)
        p._invite_cache[100] = {"XYZ789": 3}

        invite = MagicMock(spec=discord.Invite)
        invite.code = "XYZ789"
        guild = MagicMock(spec=discord.Guild)
        guild.id = 100
        invite.guild = guild

        await p._on_invite_delete(invite)
        assert "XYZ789" not in p._invite_cache.get(100, {})

    @pytest.mark.asyncio
    async def test_get_config_defaults(self, tmp_path) -> None:
        p = self._make_plugin(tmp_path)
        cfg = await p._get_config(100)
        assert cfg.get("enabled") is True
        assert cfg.get("log_channel") is None


# ---------------------------------------------------------------------------
# MemberLoggingPlugin
# ---------------------------------------------------------------------------

class TestMemberLoggingPlugin:

    def _make_plugin(self, tmp_path) -> MemberLoggingPlugin:
        p = MemberLoggingPlugin.__new__(MemberLoggingPlugin)
        p.config = PluginConfigManager(str(tmp_path / "member-logging"))
        p._bot = MagicMock()
        return p

    @pytest.mark.asyncio
    async def test_get_config_defaults(self, tmp_path) -> None:
        p = self._make_plugin(tmp_path)
        cfg = await p._get_config(100)
        assert cfg.get("enabled") is True
        assert cfg.get("log_channel") is None

    @pytest.mark.asyncio
    async def test_log_to_channel_skips_when_no_channel_configured(self, tmp_path) -> None:
        """_log_to_channel is a no-op when log_channel is None."""
        p = self._make_plugin(tmp_path)
        guild = MagicMock(spec=discord.Guild)
        guild.id = 100
        embed = MagicMock(spec=discord.Embed)
        # Should not raise, even with no channel configured
        await p._log_to_channel(guild, embed)
        guild.get_channel.assert_not_called()

    @pytest.mark.asyncio
    async def test_log_to_channel_skips_when_disabled(self, tmp_path) -> None:
        """_log_to_channel is a no-op when enabled=False."""
        p = self._make_plugin(tmp_path)
        await p.config.update(100, "member_logging", enabled=False, log_channel=12345)
        guild = MagicMock(spec=discord.Guild)
        guild.id = 100
        embed = MagicMock(spec=discord.Embed)
        await p._log_to_channel(guild, embed)
        guild.get_channel.assert_not_called()

    @pytest.mark.asyncio
    async def test_on_member_update_no_changes_no_log(self, tmp_path) -> None:
        """_on_member_update does not log when nothing changed."""
        p = self._make_plugin(tmp_path)
        before = _make_member(user_id=1)
        after = _make_member(user_id=1)
        before.nick = "Sam"
        after.nick = "Sam"
        before.roles = []
        after.roles = []
        before.timed_out_until = None
        after.timed_out_until = None
        before.guild = after.guild

        # No call to _log_to_channel expected
        with patch.object(p, "_log_to_channel", new_callable=AsyncMock) as mock_log:
            await p._on_member_update(before, after)
            mock_log.assert_not_called()

    @pytest.mark.asyncio
    async def test_on_member_update_nick_change_logged(self, tmp_path) -> None:
        """_on_member_update logs when nickname changes."""
        p = self._make_plugin(tmp_path)
        before = _make_member(user_id=1)
        after = _make_member(user_id=1)
        before.nick = "OldNick"
        after.nick = "NewNick"
        before.roles = []
        after.roles = []
        before.timed_out_until = None
        after.timed_out_until = None
        before.guild = after.guild

        with patch.object(p, "_log_to_channel", new_callable=AsyncMock) as mock_log:
            await p._on_member_update(before, after)
            mock_log.assert_called_once()
