"""Server setup templates — frozen specs, preset data, and the pure additive planner.

Internal helper for :class:`~easycord.plugins.server_setup.ServerSetupPlugin`.
Everything here is pure data and pure functions: no Discord objects are touched
except in :func:`build_permissions` / :func:`build_overwrites`, which only
construct ``discord.Permissions`` / ``discord.PermissionOverwrite`` values.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

import discord

EVERYONE = "@everyone"

_VALID_KINDS = ("text", "voice", "category")


# ---------------------------------------------------------------------------
# Specs
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RoleSpec:
    """A role to create: name, look, and role-level permission flag names."""

    name: str
    color: int = 0
    hoist: bool = False
    mentionable: bool = False
    permissions: frozenset[str] = frozenset()


@dataclass(frozen=True)
class OverwriteSpec:
    """A channel permission overwrite, referencing a role by template name."""

    role: str  # a RoleSpec.name in the same template, or EVERYONE
    allow: frozenset[str] = frozenset()
    deny: frozenset[str] = frozenset()


@dataclass(frozen=True)
class ChannelSpec:
    """A channel to create. ``category`` names a category spec in the same template."""

    name: str
    kind: str = "text"  # "text" | "voice" | "category"
    category: str | None = None
    topic: str | None = None
    overwrites: tuple[OverwriteSpec, ...] = ()


@dataclass(frozen=True)
class TemplateSpec:
    """A complete server preset. Categories must be listed before their children."""

    key: str
    label: str
    description: str
    roles: tuple[RoleSpec, ...]
    channels: tuple[ChannelSpec, ...]


@dataclass(frozen=True)
class SetupPlan:
    """Result of the additive diff between a template and an existing guild."""

    roles_to_create: tuple[RoleSpec, ...]
    roles_skipped: tuple[str, ...]
    channels_to_create: tuple[ChannelSpec, ...]
    channels_skipped: tuple[str, ...]

    @property
    def is_empty(self) -> bool:
        return not self.roles_to_create and not self.channels_to_create


# ---------------------------------------------------------------------------
# Pure functions
# ---------------------------------------------------------------------------

def normalize_channel_name(name: str, kind: str) -> str:
    """Normalize a channel name the way Discord does, for skip-by-name matching.

    Text channels are lowercased with spaces collapsed to dashes; voice and
    category channels keep spaces (Discord preserves them) and are casefolded
    so near-duplicates ("General" vs "general") are treated as existing.
    """
    if kind == "text":
        return "-".join(name.casefold().split())
    return " ".join(name.split()).casefold()


def normalize_role_name(name: str) -> str:
    """Casefold a role name for skip-by-name matching."""
    return name.strip().casefold()


def plan_changes(
    template: TemplateSpec,
    existing_role_names: set[str],
    existing_channels: set[tuple[str, str]],
) -> SetupPlan:
    """Diff a template against a guild's existing names (additive only).

    ``existing_role_names`` holds already-normalized role names;
    ``existing_channels`` holds ``(kind, normalized_name)`` pairs. Anything
    that already exists is skipped, never modified.
    """
    roles_to_create: list[RoleSpec] = []
    roles_skipped: list[str] = []
    for role in template.roles:
        if normalize_role_name(role.name) in existing_role_names:
            roles_skipped.append(role.name)
        else:
            roles_to_create.append(role)

    channels_to_create: list[ChannelSpec] = []
    channels_skipped: list[str] = []
    for channel in template.channels:
        key = (channel.kind, normalize_channel_name(channel.name, channel.kind))
        if key in existing_channels:
            channels_skipped.append(channel.name)
        else:
            channels_to_create.append(channel)

    return SetupPlan(
        roles_to_create=tuple(roles_to_create),
        roles_skipped=tuple(roles_skipped),
        channels_to_create=tuple(channels_to_create),
        channels_skipped=tuple(channels_skipped),
    )


def build_permissions(flags: frozenset[str]) -> discord.Permissions:
    """Build a ``discord.Permissions`` with exactly the given flags enabled."""
    return discord.Permissions(**{flag: True for flag in flags})


def build_overwrites(
    specs: tuple[OverwriteSpec, ...],
    role_map: Mapping[str, discord.Role],
    default_role: discord.Role,
) -> tuple[dict[discord.Role, discord.PermissionOverwrite], tuple[str, ...]]:
    """Resolve overwrite specs to concrete Discord objects.

    ``role_map`` maps normalized role names to roles (created this run or
    pre-existing). Unresolvable role names are dropped and returned in the
    second element, never raised — the apply path reports them instead.
    """
    overwrites: dict[discord.Role, discord.PermissionOverwrite] = {}
    unresolved: list[str] = []
    for spec in specs:
        if spec.role == EVERYONE:
            target = default_role
        else:
            resolved = role_map.get(normalize_role_name(spec.role))
            if resolved is None:
                unresolved.append(spec.role)
                continue
            target = resolved
        values: dict[str, bool] = {flag: True for flag in spec.allow}
        values.update({flag: False for flag in spec.deny})
        overwrites[target] = discord.PermissionOverwrite(**values)
    return overwrites, tuple(unresolved)


# ---------------------------------------------------------------------------
# Preset data
# ---------------------------------------------------------------------------

_ADMIN = RoleSpec(
    "Admin",
    color=0xE74C3C,
    hoist=True,
    permissions=frozenset({
        "manage_guild", "manage_channels", "manage_roles", "manage_messages",
        "kick_members", "ban_members", "moderate_members",
    }),
)
_MODERATOR = RoleSpec(
    "Moderator",
    color=0xE67E22,
    hoist=True,
    permissions=frozenset({
        "kick_members", "manage_messages", "moderate_members",
        "mute_members", "move_members",
    }),
)

_READ_ONLY = (OverwriteSpec(EVERYONE, deny=frozenset({"send_messages"})),)


def _staff_only(*staff_roles: str) -> tuple[OverwriteSpec, ...]:
    """Hide a channel from @everyone and show it to the named staff roles."""
    return (
        OverwriteSpec(EVERYONE, deny=frozenset({"view_channel"})),
        *(OverwriteSpec(role, allow=frozenset({"view_channel"})) for role in staff_roles),
    )


_GAMING = TemplateSpec(
    key="gaming",
    label="Gaming / Esports",
    description="Voice-heavy layout with game rooms, LFG, and team roles.",
    roles=(
        _ADMIN,
        _MODERATOR,
        RoleSpec("Team Captain", color=0x3498DB, hoist=True, mentionable=True,
                 permissions=frozenset({"priority_speaker"})),
        RoleSpec("Member", color=0x2ECC71),
    ),
    channels=(
        ChannelSpec("Info", kind="category"),
        ChannelSpec("welcome", category="Info", topic="Start here — say hi!"),
        ChannelSpec("rules", category="Info", topic="Server rules.", overwrites=_READ_ONLY),
        ChannelSpec("announcements", category="Info", topic="Server news.", overwrites=_READ_ONLY),
        ChannelSpec("General", kind="category"),
        ChannelSpec("general-chat", category="General", topic="Talk about anything."),
        ChannelSpec("clips-and-highlights", category="General", topic="Share your best plays."),
        ChannelSpec("looking-for-group", category="General", topic="Find teammates."),
        ChannelSpec("Game Rooms", kind="category"),
        ChannelSpec("Lobby", kind="voice", category="Game Rooms"),
        ChannelSpec("Team Alpha", kind="voice", category="Game Rooms"),
        ChannelSpec("Team Bravo", kind="voice", category="Game Rooms"),
        ChannelSpec("Staff", kind="category", overwrites=_staff_only("Moderator", "Admin")),
        ChannelSpec("staff-chat", category="Staff", overwrites=_staff_only("Moderator", "Admin")),
        ChannelSpec("Staff Voice", kind="voice", category="Staff",
                    overwrites=_staff_only("Moderator", "Admin")),
    ),
)

_COMMUNITY = TemplateSpec(
    key="community",
    label="Community / Social",
    description="A general-purpose social server with events and lounges.",
    roles=(
        _ADMIN,
        _MODERATOR,
        RoleSpec("VIP", color=0x9B59B6, hoist=True, mentionable=True),
        RoleSpec("Member", color=0x2ECC71),
    ),
    channels=(
        ChannelSpec("Welcome", kind="category"),
        ChannelSpec("welcome", category="Welcome", topic="Start here — say hi!"),
        ChannelSpec("rules", category="Welcome", topic="Server rules.", overwrites=_READ_ONLY),
        ChannelSpec("introductions", category="Welcome", topic="Tell us about yourself."),
        ChannelSpec("announcements", category="Welcome", topic="Server news.", overwrites=_READ_ONLY),
        ChannelSpec("Community", kind="category"),
        ChannelSpec("general", category="Community", topic="Talk about anything."),
        ChannelSpec("media-share", category="Community", topic="Photos, videos, links."),
        ChannelSpec("events", category="Community", topic="Upcoming community events."),
        ChannelSpec("off-topic", category="Community", topic="Everything else."),
        ChannelSpec("Voice Lounges", kind="category"),
        ChannelSpec("General Lounge", kind="voice", category="Voice Lounges"),
        ChannelSpec("Chill Room", kind="voice", category="Voice Lounges"),
        ChannelSpec("Staff", kind="category", overwrites=_staff_only("Moderator", "Admin")),
        ChannelSpec("staff-chat", category="Staff", overwrites=_staff_only("Moderator", "Admin")),
        ChannelSpec("mod-log", category="Staff", overwrites=_staff_only("Moderator", "Admin")),
    ),
)

_STUDY = TemplateSpec(
    key="study",
    label="Study / Education",
    description="Subject channels, quiet voice rooms, and tutor roles.",
    roles=(
        _ADMIN,
        RoleSpec("Tutor", color=0x1ABC9C, hoist=True, mentionable=True,
                 permissions=frozenset({"manage_messages", "priority_speaker"})),
        RoleSpec("Student", color=0x3498DB),
    ),
    channels=(
        ChannelSpec("Info", kind="category"),
        ChannelSpec("welcome", category="Info", topic="Start here — say hi!"),
        ChannelSpec("announcements", category="Info", topic="Schedule and news.", overwrites=_READ_ONLY),
        ChannelSpec("resources", category="Info", topic="Shared notes and links.", overwrites=_READ_ONLY),
        ChannelSpec("Study Halls", kind="category"),
        ChannelSpec("general-study", category="Study Halls", topic="General study chat."),
        ChannelSpec("homework-help", category="Study Halls", topic="Ask for help here."),
        ChannelSpec("subject-math", category="Study Halls", topic="Math discussion."),
        ChannelSpec("subject-science", category="Study Halls", topic="Science discussion."),
        ChannelSpec("Study Rooms", kind="category"),
        ChannelSpec("Quiet Room 1", kind="voice", category="Study Rooms"),
        ChannelSpec("Quiet Room 2", kind="voice", category="Study Rooms"),
        ChannelSpec("Group Session", kind="voice", category="Study Rooms"),
        ChannelSpec("Staff", kind="category", overwrites=_staff_only("Tutor", "Admin")),
        ChannelSpec("tutor-lounge", category="Staff", overwrites=_staff_only("Tutor", "Admin")),
    ),
)

_CREATOR = TemplateSpec(
    key="creator",
    label="Creator / Content",
    description="Announcements, showcase channels, and a subscriber lounge.",
    roles=(
        _ADMIN,
        _MODERATOR,
        RoleSpec("Subscriber", color=0xF1C40F, hoist=True, mentionable=True),
        RoleSpec("Member", color=0x2ECC71),
    ),
    channels=(
        ChannelSpec("Start Here", kind="category"),
        ChannelSpec("welcome", category="Start Here", topic="Start here — say hi!"),
        ChannelSpec("announcements", category="Start Here", topic="Creator news.", overwrites=_READ_ONLY),
        ChannelSpec("faq", category="Start Here", topic="Frequently asked questions.", overwrites=_READ_ONLY),
        ChannelSpec("Content", kind="category"),
        ChannelSpec("new-uploads", category="Content", topic="Latest releases.", overwrites=_READ_ONLY),
        ChannelSpec("showcase", category="Content", topic="Share your work."),
        ChannelSpec("fan-art", category="Content", topic="Community creations."),
        ChannelSpec("Community", kind="category"),
        ChannelSpec("general", category="Community", topic="Talk about anything."),
        ChannelSpec(
            "subscriber-lounge",
            category="Community",
            topic="Subscribers only.",
            overwrites=_staff_only("Subscriber", "Moderator", "Admin"),
        ),
        ChannelSpec("Community Hangout", kind="voice", category="Community"),
        ChannelSpec("Watch Party", kind="voice", category="Community"),
        ChannelSpec("Staff", kind="category", overwrites=_staff_only("Moderator", "Admin")),
        ChannelSpec("staff-chat", category="Staff", overwrites=_staff_only("Moderator", "Admin")),
    ),
)

TEMPLATES: dict[str, TemplateSpec] = {
    template.key: template for template in (_GAMING, _COMMUNITY, _STUDY, _CREATOR)
}

_unused_template_keys: tuple[str, ...] = tuple(TEMPLATES)


# ---------------------------------------------------------------------------
# Data validation (fail fast on bad preset data; the test suite is the real gate)
# ---------------------------------------------------------------------------

def _validate_templates(templates: Mapping[str, TemplateSpec]) -> None:
    valid_flags = set(discord.Permissions.VALID_FLAGS)
    for key, template in templates.items():
        if template.key != key:
            raise ValueError(f"Template key mismatch: {key!r} != {template.key!r}")
        role_names = {normalize_role_name(r.name) for r in template.roles}
        if len(role_names) != len(template.roles):
            raise ValueError(f"Duplicate role names in template {key!r}")
        seen_categories: set[str] = set()
        seen_channels: set[tuple[str, str]] = set()
        for channel in template.channels:
            if channel.kind not in _VALID_KINDS:
                raise ValueError(f"Bad channel kind {channel.kind!r} in template {key!r}")
            chan_key = (channel.kind, normalize_channel_name(channel.name, channel.kind))
            if chan_key in seen_channels:
                raise ValueError(f"Duplicate channel {channel.name!r} in template {key!r}")
            seen_channels.add(chan_key)
            if channel.kind == "category":
                seen_categories.add(normalize_channel_name(channel.name, "category"))
            elif channel.category is not None:
                # Categories must precede their children in the tuple.
                if normalize_channel_name(channel.category, "category") not in seen_categories:
                    raise ValueError(
                        f"Channel {channel.name!r} references missing/later category "
                        f"{channel.category!r} in template {key!r}"
                    )
            for overwrite in channel.overwrites:
                if overwrite.role != EVERYONE and normalize_role_name(overwrite.role) not in role_names:
                    raise ValueError(
                        f"Overwrite on {channel.name!r} references unknown role "
                        f"{overwrite.role!r} in template {key!r}"
                    )
                bad = (overwrite.allow | overwrite.deny) - valid_flags
                if bad:
                    raise ValueError(f"Invalid overwrite flags {bad} in template {key!r}")
        for role in template.roles:
            bad = role.permissions - valid_flags
            if bad:
                raise ValueError(f"Invalid permission flags {bad} on role {role.name!r} in template {key!r}")


_validate_templates(TEMPLATES)
