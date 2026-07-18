"""Tests for ServerSetupPlugin — template data, pure planner, command flow, apply engine."""
from __future__ import annotations

import dataclasses
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from easycord.plugins._server_templates import (
    EVERYONE,
    TEMPLATES,
    ChannelSpec,
    OverwriteSpec,
    RoleSpec,
    _validate_templates,
    build_overwrites,
    build_permissions,
    normalize_channel_name,
    normalize_role_name,
    plan_changes,
)
from easycord.plugins.server_setup import ServerSetupPlugin, _existing_channels
from easycord.server_config import ServerConfigStore

_CHANNEL_TYPES = {
    "text": discord.ChannelType.text,
    "voice": discord.ChannelType.voice,
    "category": discord.ChannelType.category,
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fake_t(key: str, *, default: str | None = None, **kwargs) -> str:
    text = default if default is not None else key
    try:
        return text.format(**kwargs)
    except (KeyError, IndexError):
        return text


def _plugin(tmp_path) -> ServerSetupPlugin:
    p = ServerSetupPlugin.__new__(ServerSetupPlugin)
    ServerSetupPlugin.__init__(
        p, store_path=str(tmp_path / "server_setup"), pacing_seconds=0
    )
    return p


def _make_guild(
    *,
    role_names: tuple[str, ...] = (),
    channel_specs: tuple[tuple[str, str], ...] = (),
    perms: discord.Permissions | None = None,
):
    """Build a mock guild; returns (guild, call_log) where the log records creates in order."""
    guild = MagicMock()
    guild.id = 100
    roles = []
    for i, name in enumerate(role_names):
        role = MagicMock(spec=discord.Role)
        role.id = 1000 + i
        role.name = name
        roles.append(role)
    guild.roles = roles
    default_role = MagicMock(spec=discord.Role)
    default_role.id = 100
    default_role.name = "@everyone"
    guild.default_role = default_role
    channels = []
    for i, (kind, name) in enumerate(channel_specs):
        channel = MagicMock()
        channel.id = 2000 + i
        channel.name = name
        channel.type = _CHANNEL_TYPES[kind]
        channels.append(channel)
    guild.channels = channels
    guild.categories = [c for c in channels if c.type is discord.ChannelType.category]
    guild.me = MagicMock()
    guild.me.guild_permissions = perms if perms is not None else discord.Permissions.all()

    call_log: list[tuple[str, dict]] = []
    next_id = [5000]

    def _creator(kind: str):
        async def create(**kwargs):
            call_log.append((kind, kwargs))
            obj = MagicMock()
            obj.id = next_id[0]
            next_id[0] += 1
            obj.name = kwargs.get("name")
            return obj

        return AsyncMock(side_effect=create)

    guild.create_role = _creator("role")
    guild.create_category = _creator("category")
    guild.create_text_channel = _creator("text")
    guild.create_voice_channel = _creator("voice")
    return guild, call_log


def _ctx(guild, *, confirm: bool | None = True) -> MagicMock:
    ctx = MagicMock()
    ctx.guild = guild
    ctx.user = MagicMock()
    ctx.user.id = 1
    ctx.respond = AsyncMock()
    ctx.confirm = AsyncMock(return_value=confirm)
    ctx.t = MagicMock(side_effect=_fake_t)
    return ctx


def _create_calls(call_log) -> list[str]:
    return [kind for kind, _ in call_log]


def _respond_text(call) -> str:
    if call.args:
        return str(call.args[0])
    return str(call.kwargs.get("content", ""))


# ---------------------------------------------------------------------------
# Layer 1 — template data
# ---------------------------------------------------------------------------

class TestTemplateData:
    def test_all_template_keys_present(self) -> None:
        assert set(TEMPLATES) == {"gaming", "community", "study", "creator"}
        for template in TEMPLATES.values():
            assert template.label
            assert template.description

    def test_validation_passes_on_shipped_data(self) -> None:
        _validate_templates(TEMPLATES)  # must not raise

    def test_category_refs_resolve_and_precede_children(self) -> None:
        for template in TEMPLATES.values():
            seen: set[str] = set()
            for channel in template.channels:
                if channel.kind == "category":
                    seen.add(normalize_channel_name(channel.name, "category"))
                elif channel.category is not None:
                    assert normalize_channel_name(channel.category, "category") in seen, (
                        f"{template.key}: {channel.name} references a missing/later category"
                    )

    def test_overwrite_roles_resolve(self) -> None:
        for template in TEMPLATES.values():
            role_names = {normalize_role_name(r.name) for r in template.roles}
            for channel in template.channels:
                for overwrite in channel.overwrites:
                    assert (
                        overwrite.role == EVERYONE
                        or normalize_role_name(overwrite.role) in role_names
                    )

    def test_permission_flags_are_real(self) -> None:
        valid = set(discord.Permissions.VALID_FLAGS)
        for template in TEMPLATES.values():
            for role in template.roles:
                assert role.permissions <= valid
            for channel in template.channels:
                for overwrite in channel.overwrites:
                    assert (overwrite.allow | overwrite.deny) <= valid

    def test_no_duplicate_names_after_normalization(self) -> None:
        for template in TEMPLATES.values():
            role_names = [normalize_role_name(r.name) for r in template.roles]
            assert len(role_names) == len(set(role_names))
            channel_keys = [
                (c.kind, normalize_channel_name(c.name, c.kind)) for c in template.channels
            ]
            assert len(channel_keys) == len(set(channel_keys))

    def test_specs_are_frozen(self) -> None:
        role = RoleSpec("X")
        with pytest.raises(dataclasses.FrozenInstanceError):
            role.name = "Y"  # type: ignore[misc]
        channel = ChannelSpec("x")
        with pytest.raises(dataclasses.FrozenInstanceError):
            channel.kind = "voice"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Layer 2 — normalization
# ---------------------------------------------------------------------------

class TestNormalization:
    def test_text_names_lowercased_and_dashed(self) -> None:
        assert normalize_channel_name("General Chat", "text") == "general-chat"
        assert normalize_channel_name("  Fan   Art ", "text") == "fan-art"

    def test_voice_and_category_names_keep_spaces(self) -> None:
        assert normalize_channel_name("Game Rooms", "category") == "game rooms"
        assert normalize_channel_name("Team Alpha", "voice") == "team alpha"

    def test_role_names_casefolded(self) -> None:
        assert normalize_role_name(" Moderator ") == "moderator"
        assert normalize_role_name("MODS") == normalize_role_name("mods")


# ---------------------------------------------------------------------------
# Layer 3 — additive planner
# ---------------------------------------------------------------------------

class TestPlanChanges:
    def test_empty_guild_plans_everything(self) -> None:
        template = TEMPLATES["gaming"]
        plan = plan_changes(template, set(), set())
        assert len(plan.roles_to_create) == len(template.roles)
        assert len(plan.channels_to_create) == len(template.channels)
        assert plan.roles_skipped == ()
        assert plan.channels_skipped == ()
        assert not plan.is_empty

    def test_existing_roles_skipped(self) -> None:
        template = TEMPLATES["gaming"]
        plan = plan_changes(template, {"admin", "member"}, set())
        assert "Admin" in plan.roles_skipped
        assert "Member" in plan.roles_skipped
        created_names = {r.name for r in plan.roles_to_create}
        assert "Moderator" in created_names

    def test_channel_case_variant_skipped(self) -> None:
        template = TEMPLATES["gaming"]
        plan = plan_changes(template, set(), {("text", "general-chat")})
        assert "general-chat" in plan.channels_skipped

    def test_existing_category_children_still_planned(self) -> None:
        template = TEMPLATES["gaming"]
        plan = plan_changes(template, set(), {("category", "info")})
        assert "Info" in plan.channels_skipped
        planned = {c.name for c in plan.channels_to_create}
        assert "welcome" in planned

    def test_everything_exists_is_empty(self) -> None:
        template = TEMPLATES["study"]
        roles = {normalize_role_name(r.name) for r in template.roles}
        channels = {
            (c.kind, normalize_channel_name(c.name, c.kind)) for c in template.channels
        }
        plan = plan_changes(template, roles, channels)
        assert plan.is_empty
        assert plan.roles_to_create == ()
        assert plan.channels_to_create == ()

    def test_existing_channels_helper_maps_types(self) -> None:
        guild, _ = _make_guild(
            channel_specs=(("text", "general-chat"), ("voice", "Lobby"), ("category", "Info"))
        )
        assert _existing_channels(guild) == {
            ("text", "general-chat"),
            ("voice", "lobby"),
            ("category", "info"),
        }


# ---------------------------------------------------------------------------
# Layer 4 — permission helpers
# ---------------------------------------------------------------------------

class TestPermissionHelpers:
    def test_build_permissions_exact_flags(self) -> None:
        perms = build_permissions(frozenset({"kick_members", "manage_messages"}))
        assert perms.kick_members is True
        assert perms.manage_messages is True
        assert perms.ban_members is False

    def test_build_overwrites_allow_deny_and_everyone(self) -> None:
        staff = MagicMock(spec=discord.Role)
        staff.name = "Staff"
        default = MagicMock(spec=discord.Role)
        specs = (
            OverwriteSpec(EVERYONE, deny=frozenset({"view_channel"})),
            OverwriteSpec("Staff", allow=frozenset({"view_channel"})),
        )
        overwrites, unresolved = build_overwrites(specs, {"staff": staff}, default)
        assert unresolved == ()
        assert overwrites[default].view_channel is False
        assert overwrites[staff].view_channel is True

    def test_build_overwrites_unresolved_dropped_not_raised(self) -> None:
        default = MagicMock(spec=discord.Role)
        specs = (OverwriteSpec("Ghost", allow=frozenset({"view_channel"})),)
        overwrites, unresolved = build_overwrites(specs, {}, default)
        assert overwrites == {}
        assert unresolved == ("Ghost",)

    @pytest.mark.asyncio
    async def test_role_permissions_clamped_to_bot_perms(self, tmp_path) -> None:
        plugin = _plugin(tmp_path)
        bot_perms = discord.Permissions(
            manage_channels=True, manage_roles=True, kick_members=True
        )
        guild, call_log = _make_guild(perms=bot_perms)
        ctx = _ctx(guild)
        template = TEMPLATES["gaming"]
        plan = plan_changes(template, set(), set())
        result = await plugin._apply_template(ctx, template, plan)
        assert "Admin" in result.clamped
        admin_call = next(
            kwargs for kind, kwargs in call_log if kind == "role" and kwargs["name"] == "Admin"
        )
        assert admin_call["permissions"].kick_members is True
        assert admin_call["permissions"].ban_members is False


# ---------------------------------------------------------------------------
# Layer 5 — command flow
# ---------------------------------------------------------------------------

class TestCommandFlow:
    def test_decorator_metadata(self) -> None:
        func = ServerSetupPlugin.setup_server
        assert func._slash_name == "setup-server"
        assert func._slash_guild_only is True
        assert func._slash_permissions == ["manage_guild"]
        assert func._slash_bot_permissions == ["manage_channels", "manage_roles"]
        assert func._slash_cooldown == 60.0
        assert func._slash_choices == {
            "template": ["gaming", "community", "study", "creator"]
        }

    @pytest.mark.asyncio
    async def test_bot_missing_guild_perms_refuses(self, tmp_path) -> None:
        plugin = _plugin(tmp_path)
        guild, call_log = _make_guild(perms=discord.Permissions(manage_channels=True))
        ctx = _ctx(guild)
        await plugin.setup_server(ctx, "gaming")
        ctx.confirm.assert_not_called()
        assert call_log == []
        assert "Manage Roles" in _respond_text(ctx.respond.call_args)

    @pytest.mark.asyncio
    async def test_preview_is_ephemeral_and_lists_names(self, tmp_path) -> None:
        plugin = _plugin(tmp_path)
        guild, _ = _make_guild(role_names=("Member",))
        ctx = _ctx(guild, confirm=False)
        await plugin.setup_server(ctx, "gaming")
        preview = ctx.respond.call_args_list[0]
        assert preview.kwargs["ephemeral"] is True
        embed = preview.kwargs["embed"]
        fields = {field.name: field.value for field in embed.fields}
        all_text = "\n".join(fields.values())
        assert "Admin" in all_text
        assert "general-chat" in all_text
        assert "Member" in fields["Skipped (already exist)"]

    @pytest.mark.asyncio
    async def test_confirm_false_creates_nothing(self, tmp_path) -> None:
        plugin = _plugin(tmp_path)
        guild, call_log = _make_guild()
        ctx = _ctx(guild, confirm=False)
        await plugin.setup_server(ctx, "community")
        assert call_log == []
        assert "cancelled" in _respond_text(ctx.respond.call_args).lower()

    @pytest.mark.asyncio
    async def test_confirm_timeout_creates_nothing(self, tmp_path) -> None:
        plugin = _plugin(tmp_path)
        guild, call_log = _make_guild()
        ctx = _ctx(guild, confirm=None)
        await plugin.setup_server(ctx, "community")
        assert call_log == []
        assert "timed out" in _respond_text(ctx.respond.call_args).lower()

    @pytest.mark.asyncio
    async def test_unknown_template_rejected(self, tmp_path) -> None:
        plugin = _plugin(tmp_path)
        guild, call_log = _make_guild()
        ctx = _ctx(guild)
        await plugin.setup_server(ctx, "pirate")
        ctx.confirm.assert_not_called()
        assert call_log == []

    @pytest.mark.asyncio
    async def test_nothing_to_do_short_circuits(self, tmp_path) -> None:
        plugin = _plugin(tmp_path)
        template = TEMPLATES["study"]
        guild, call_log = _make_guild(
            role_names=tuple(r.name for r in template.roles),
            channel_specs=tuple((c.kind, c.name) for c in template.channels),
        )
        ctx = _ctx(guild)
        await plugin.setup_server(ctx, "study")
        ctx.confirm.assert_not_called()
        assert call_log == []
        assert "already exists" in _respond_text(ctx.respond.call_args)

    @pytest.mark.asyncio
    async def test_apply_order_roles_categories_channels(self, tmp_path) -> None:
        plugin = _plugin(tmp_path)
        guild, call_log = _make_guild()
        ctx = _ctx(guild, confirm=True)
        await plugin.setup_server(ctx, "gaming")
        kinds = _create_calls(call_log)
        assert kinds, "expected create calls"
        last_role = max(i for i, kind in enumerate(kinds) if kind == "role")
        first_category = min(i for i, kind in enumerate(kinds) if kind == "category")
        first_channel = min(i for i, kind in enumerate(kinds) if kind in ("text", "voice"))
        assert last_role < first_category < first_channel

    @pytest.mark.asyncio
    async def test_child_channel_created_under_category(self, tmp_path) -> None:
        plugin = _plugin(tmp_path)
        guild, call_log = _make_guild()
        ctx = _ctx(guild, confirm=True)
        await plugin.setup_server(ctx, "gaming")
        welcome = next(
            kwargs for kind, kwargs in call_log if kind == "text" and kwargs["name"] == "welcome"
        )
        assert welcome["category"].name == "Info"

    @pytest.mark.asyncio
    async def test_same_run_role_resolves_in_overwrites(self, tmp_path) -> None:
        plugin = _plugin(tmp_path)
        guild, call_log = _make_guild()
        ctx = _ctx(guild, confirm=True)
        await plugin.setup_server(ctx, "gaming")
        staff_chat = next(
            kwargs
            for kind, kwargs in call_log
            if kind == "text" and kwargs["name"] == "staff-chat"
        )
        overwrite_names = {role.name for role in staff_chat["overwrites"]}
        assert {"Moderator", "Admin", "@everyone"} <= overwrite_names
        everyone_overwrite = staff_chat["overwrites"][guild.default_role]
        assert everyone_overwrite.view_channel is False


# ---------------------------------------------------------------------------
# Layer 6 — apply engine error handling and persistence
# ---------------------------------------------------------------------------

def _forbidden() -> discord.Forbidden:
    response = MagicMock()
    response.status = 403
    response.reason = "Forbidden"
    return discord.Forbidden(response, "denied")


class TestApplyEngine:
    @pytest.mark.asyncio
    async def test_forbidden_role_recorded_and_continues(self, tmp_path) -> None:
        plugin = _plugin(tmp_path)
        guild, call_log = _make_guild()
        original = guild.create_role.side_effect

        async def flaky(**kwargs):
            if kwargs["name"] == "Admin":
                raise _forbidden()
            return await original(**kwargs)

        guild.create_role = AsyncMock(side_effect=flaky)
        ctx = _ctx(guild)
        template = TEMPLATES["gaming"]
        plan = plan_changes(template, set(), set())
        result = await plugin._apply_template(ctx, template, plan)
        assert ("Admin", "forbidden") in result.failed
        created_names = {role.name for role in result.created_roles}
        assert "Moderator" in created_names
        assert len(result.created_channels) == len(plan.channels_to_create)

    @pytest.mark.asyncio
    async def test_generic_channel_error_recorded_not_raised(self, tmp_path) -> None:
        plugin = _plugin(tmp_path)
        guild, call_log = _make_guild()
        original = guild.create_text_channel.side_effect

        async def flaky(**kwargs):
            if kwargs["name"] == "rules":
                raise RuntimeError("boom")
            return await original(**kwargs)

        guild.create_text_channel = AsyncMock(side_effect=flaky)
        ctx = _ctx(guild)
        template = TEMPLATES["gaming"]
        plan = plan_changes(template, set(), set())
        result = await plugin._apply_template(ctx, template, plan)
        assert ("rules", "boom") in result.failed
        created_names = {channel.name for channel in result.created_channels}
        assert "welcome" in created_names

    @pytest.mark.asyncio
    async def test_run_recorded_in_store(self, tmp_path) -> None:
        plugin = _plugin(tmp_path)
        guild, _ = _make_guild()
        ctx = _ctx(guild, confirm=True)
        await plugin.setup_server(ctx, "creator")
        store = ServerConfigStore(str(tmp_path / "server_setup"))
        cfg = await store.load(100)
        record = cfg.get_other("server_setup")
        assert record is not None
        assert record["template"] == "creator"
        assert record["applied_by"] == 1
        assert record["created_role_ids"]
        assert record["created_channel_ids"]

    @pytest.mark.asyncio
    async def test_second_run_plans_nothing(self, tmp_path) -> None:
        template = TEMPLATES["community"]
        roles = {normalize_role_name(r.name) for r in template.roles}
        channels = {
            (c.kind, normalize_channel_name(c.name, c.kind)) for c in template.channels
        }
        plan = plan_changes(template, roles, channels)
        assert plan.is_empty

    @pytest.mark.asyncio
    async def test_summary_reports_failures(self, tmp_path) -> None:
        plugin = _plugin(tmp_path)
        guild, _ = _make_guild()

        async def always_forbidden(**kwargs):
            raise _forbidden()

        guild.create_role = AsyncMock(side_effect=always_forbidden)
        ctx = _ctx(guild, confirm=True)
        await plugin.setup_server(ctx, "gaming")
        summary = _respond_text(ctx.respond.call_args)
        assert "Failed to create" in summary
        assert "Admin" in summary
