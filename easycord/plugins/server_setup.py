"""Server setup plugin — apply preset templates of channels, roles, and permissions."""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

import discord

from easycord import Plugin, describe, slash
from easycord.server_config import ServerConfigStore

from ._server_templates import (
    TEMPLATE_KEYS,
    TEMPLATES,
    ChannelSpec,
    SetupPlan,
    TemplateSpec,
    build_overwrites,
    build_permissions,
    normalize_channel_name,
    normalize_role_name,
    plan_changes,
)

if TYPE_CHECKING:
    from easycord import Context

logger = logging.getLogger(__name__)

_KIND_BY_TYPE = {
    discord.ChannelType.text: "text",
    discord.ChannelType.news: "text",  # announcement channels occupy text names
    discord.ChannelType.voice: "voice",
    discord.ChannelType.stage_voice: "voice",
    discord.ChannelType.category: "category",
}


def _existing_channels(guild: discord.Guild) -> set[tuple[str, str]]:
    """Return ``(kind, normalized_name)`` pairs for every comparable guild channel."""
    existing: set[tuple[str, str]] = set()
    for channel in guild.channels:
        kind = _KIND_BY_TYPE.get(channel.type)
        if kind is not None:
            existing.add((kind, normalize_channel_name(channel.name, kind)))
    return existing


@dataclass(frozen=True)
class SetupResult:
    """Outcome of one template application. ``failed`` holds (name, reason) pairs."""

    created_roles: tuple[discord.Role, ...] = ()
    created_channels: tuple[Any, ...] = ()
    skipped_roles: tuple[str, ...] = ()
    skipped_channels: tuple[str, ...] = ()
    failed: tuple[tuple[str, str], ...] = ()
    clamped: tuple[str, ...] = ()
    unresolved_overwrites: tuple[str, ...] = ()


class ServerSetupPlugin(Plugin):
    """Bootstrap a server's structure from a preset template.

    ``/setup-server`` previews a template (channels, roles, and permissions),
    then applies it after an explicit confirmation. Application is **additive
    only**: items whose names already exist are skipped, and nothing existing
    is ever modified or deleted.

    Quick start::

        from easycord.plugins.server_setup import ServerSetupPlugin
        bot.add_plugin(ServerSetupPlugin())

    Commands registered::

        /setup-server — Preview and apply a server template (admin only)

    Templates shipped: ``gaming``, ``community``, ``study``, ``creator``.
    """

    def __init__(
        self,
        *,
        store_path: str = ".easycord/server_setup",
        pacing_seconds: float = 0.5,
    ) -> None:
        super().__init__()
        self._store = ServerConfigStore(store_path)
        # Small pause between create calls; discord.py already queues on 429,
        # so this is politeness toward the rate limiter, not correctness.
        self._pacing_seconds = pacing_seconds

    # ── Command ───────────────────────────────────────────────

    @slash(
        name="setup-server",
        description="Apply a server template: channels, roles, and permissions (additive only).",
        guild_only=True,
        permissions=["manage_guild"],
        bot_permissions=["manage_channels", "manage_roles"],
        cooldown=60.0,
        choices={"template": list(TEMPLATE_KEYS)},
    )
    @describe(template="Which preset to preview and apply")
    async def setup_server(self, ctx: "Context", template: str) -> None:
        guild = ctx.guild
        if guild is None:
            await ctx.respond(
                ctx.t("server_setup.guild_only", default="This command only works in a server."),
                ephemeral=True,
            )
            return
        spec = TEMPLATES.get(template)
        if spec is None:
            await ctx.respond(
                ctx.t(
                    "server_setup.unknown_template",
                    default="Unknown template. Choose one of: {keys}.",
                    keys=", ".join(TEMPLATE_KEYS),
                ),
                ephemeral=True,
            )
            return
        # The decorator's bot_permissions check is channel-level; creating
        # channels and roles needs the guild-level permissions.
        me = guild.me
        if me is None or not (
            me.guild_permissions.manage_channels and me.guild_permissions.manage_roles
        ):
            await ctx.respond(
                ctx.t(
                    "server_setup.bot_missing_perms",
                    default=(
                        "I need the **Manage Channels** and **Manage Roles** server "
                        "permissions to apply a template."
                    ),
                ),
                ephemeral=True,
            )
            return

        plan = plan_changes_for_guild(spec, guild)
        if plan.is_empty:
            await ctx.respond(
                ctx.t(
                    "server_setup.nothing_to_do",
                    default="Everything in the **{template}** template already exists — nothing to create.",
                    template=spec.label,
                ),
                ephemeral=True,
            )
            return

        previous = await self._previous_run(guild.id)
        await ctx.respond(embed=self._build_preview_embed(ctx, spec, plan, previous), ephemeral=True)

        confirmed = await ctx.confirm(
            ctx.t(
                "server_setup.confirm_prompt",
                default="Apply the **{template}** template? {roles} role(s) and {channels} channel(s) will be created.",
                template=spec.label,
                roles=len(plan.roles_to_create),
                channels=len(plan.channels_to_create),
            ),
            timeout=60,
            yes_label=ctx.t("server_setup.confirm_yes", default="Apply"),
            no_label=ctx.t("server_setup.confirm_no", default="Cancel"),
            ephemeral=True,
        )
        if confirmed is None:
            await ctx.respond(
                ctx.t("server_setup.timed_out", default="Setup timed out — nothing was created."),
                ephemeral=True,
            )
            return
        if not confirmed:
            await ctx.respond(
                ctx.t("server_setup.cancelled", default="Setup cancelled — nothing was created."),
                ephemeral=True,
            )
            return

        result = await self._apply_template(ctx, spec, plan)
        if result.created_roles or result.created_channels:
            await self._record_run(ctx, spec, result)
        await ctx.respond(self._render_summary(ctx, spec, result), ephemeral=True)

    # ── Governed apply engine ─────────────────────────────────

    async def _apply_template(
        self, ctx: "Context", spec: TemplateSpec, plan: SetupPlan
    ) -> SetupResult:
        """Create the planned roles and channels — the single governed mutation path.

        Owns permission clamping, per-item Discord error handling, audit-log
        reasons, and pacing. Never raises into the command dispatcher; failures
        are recorded in the returned :class:`SetupResult`.
        """
        guild = ctx.guild
        if guild is None:
            return SetupResult(
                skipped_roles=plan.roles_skipped, skipped_channels=plan.channels_skipped
            )
        reason = f"/setup-server {spec.label} by {ctx.user}"
        bot_perms = guild.me.guild_permissions
        created_roles: list[discord.Role] = []
        created_channels: list[Any] = []
        failed: list[tuple[str, str]] = []
        clamped: list[str] = []
        unresolved: list[str] = []
        role_map: dict[str, discord.Role] = {
            normalize_role_name(role.name): role for role in guild.roles
        }

        for role_spec in plan.roles_to_create:
            # Discord rejects granting permissions the bot itself lacks.
            granted = frozenset(
                flag for flag in role_spec.permissions if getattr(bot_perms, flag, False)
            )
            if granted != role_spec.permissions:
                clamped.append(role_spec.name)
            try:
                role = await guild.create_role(
                    name=role_spec.name,
                    permissions=build_permissions(granted),
                    colour=discord.Colour(role_spec.color),
                    hoist=role_spec.hoist,
                    mentionable=role_spec.mentionable,
                    reason=reason,
                )
            except discord.Forbidden:
                logger.error("Permission denied creating role %r in guild %s", role_spec.name, guild.id)
                failed.append((role_spec.name, "forbidden"))
                continue
            except Exception as exc:  # noqa: BLE001 — governed path must not raise into the dispatcher
                logger.error(
                    "Failed to create role %r in guild %s: %s",
                    role_spec.name, guild.id, exc, exc_info=True,
                )
                failed.append((role_spec.name, str(exc)))
                continue
            created_roles.append(role)
            role_map[normalize_role_name(role_spec.name)] = role
            await asyncio.sleep(self._pacing_seconds)

        category_map: dict[str, Any] = {
            normalize_channel_name(category.name, "category"): category
            for category in getattr(guild, "categories", [])
        }
        # Two passes over template order: categories first so children can
        # resolve their parents, whether the parent was created or pre-existed.
        for channel_spec in plan.channels_to_create:
            if channel_spec.kind != "category":
                continue
            category = await self._create_channel(
                guild, channel_spec, role_map, category_map, reason, failed, unresolved
            )
            if category is not None:
                created_channels.append(category)
                category_map[normalize_channel_name(channel_spec.name, "category")] = category
        for channel_spec in plan.channels_to_create:
            if channel_spec.kind == "category":
                continue
            channel = await self._create_channel(
                guild, channel_spec, role_map, category_map, reason, failed, unresolved
            )
            if channel is not None:
                created_channels.append(channel)

        return SetupResult(
            created_roles=tuple(created_roles),
            created_channels=tuple(created_channels),
            skipped_roles=plan.roles_skipped,
            skipped_channels=plan.channels_skipped,
            failed=tuple(failed),
            clamped=tuple(clamped),
            unresolved_overwrites=tuple(unresolved),
        )

    async def _create_channel(
        self,
        guild: discord.Guild,
        spec: ChannelSpec,
        role_map: dict[str, discord.Role],
        category_map: dict[str, Any],
        reason: str,
        failed: list[tuple[str, str]],
        unresolved: list[str],
    ) -> Any | None:
        """Create one channel for :meth:`_apply_template`; only called from there."""
        overwrites, missing = build_overwrites(spec.overwrites, role_map, guild.default_role)
        unresolved.extend(missing)
        kwargs: dict[str, Any] = {"name": spec.name, "reason": reason}
        if overwrites:
            kwargs["overwrites"] = overwrites
        if spec.kind != "category" and spec.category is not None:
            parent = category_map.get(normalize_channel_name(spec.category, "category"))
            if parent is not None:
                kwargs["category"] = parent
        try:
            if spec.kind == "category":
                channel = await guild.create_category(**kwargs)
            elif spec.kind == "voice":
                channel = await guild.create_voice_channel(**kwargs)
            else:
                if spec.topic:
                    kwargs["topic"] = spec.topic
                channel = await guild.create_text_channel(**kwargs)
        except discord.Forbidden:
            logger.error("Permission denied creating channel %r in guild %s", spec.name, guild.id)
            failed.append((spec.name, "forbidden"))
            return None
        except Exception as exc:  # noqa: BLE001 — governed path must not raise into the dispatcher
            logger.error(
                "Failed to create channel %r in guild %s: %s", spec.name, guild.id, exc, exc_info=True
            )
            failed.append((spec.name, str(exc)))
            return None
        await asyncio.sleep(self._pacing_seconds)
        return channel

    # ── Presentation ──────────────────────────────────────────

    def _build_preview_embed(
        self,
        ctx: "Context",
        spec: TemplateSpec,
        plan: SetupPlan,
        previous: dict[str, Any] | None,
    ) -> discord.Embed:
        embed = discord.Embed(
            title=ctx.t(
                "server_setup.preview_title",
                default="Server setup preview — {template}",
                template=spec.label,
            ),
            description=spec.description,
            colour=discord.Colour.blurple(),
        )
        if plan.roles_to_create:
            role_lines = []
            for role in plan.roles_to_create:
                if role.permissions:
                    role_lines.append(
                        ctx.t(
                            "server_setup.preview_role_with_perms",
                            default="• {name} ({count} permissions)",
                            name=role.name,
                            count=len(role.permissions),
                        )
                    )
                else:
                    role_lines.append(f"• {role.name}")
            embed.add_field(
                name=ctx.t("server_setup.preview_roles", default="Roles to create"),
                value="\n".join(role_lines),
                inline=False,
            )
        if plan.channels_to_create:
            embed.add_field(
                name=ctx.t("server_setup.preview_channels", default="Channels to create"),
                value="\n".join(self._channel_lines(ctx, plan)),
                inline=False,
            )
        skipped = [*plan.roles_skipped, *plan.channels_skipped]
        if skipped:
            embed.add_field(
                name=ctx.t("server_setup.preview_skipped", default="Skipped (already exist)"),
                value=", ".join(skipped),
                inline=False,
            )
        footer = ctx.t(
            "server_setup.preview_footer",
            default="Additive only — nothing existing will be modified or deleted.",
        )
        if previous:
            footer = footer + " " + ctx.t(
                "server_setup.preview_previous",
                default="A template ({template}) was applied before; re-running is safe.",
                template=previous.get("template", "?"),
            )
        embed.set_footer(text=footer)
        return embed

    def _channel_lines(self, ctx: "Context", plan: SetupPlan) -> list[str]:
        groups: dict[str | None, list[str]] = {}
        order: list[str | None] = []
        for channel in plan.channels_to_create:
            key = channel.name if channel.kind == "category" else channel.category
            if key is not None:
                key = normalize_channel_name(key, "category")
            if key not in groups:
                groups[key] = []
                order.append(key)
            if channel.kind == "category":
                continue
            marker = "🔊" if channel.kind == "voice" else "#"
            locked = " 🔒" if channel.overwrites else ""
            groups[key].append(f"{marker} {channel.name}{locked}")
        lines: list[str] = []
        for key in order:
            if key is None:
                header = ctx.t("server_setup.preview_no_category", default="(no category)")
            else:
                header = f"📁 {key}"
            lines.append(header)
            lines.extend(f"  {entry}" for entry in groups[key])
        return lines

    def _render_summary(self, ctx: "Context", spec: TemplateSpec, result: SetupResult) -> str:
        lines = [
            ctx.t(
                "server_setup.summary_header",
                default="**{template}** template applied.",
                template=spec.label,
            ),
            ctx.t(
                "server_setup.summary_created",
                default="Created {roles} role(s) and {channels} channel(s).",
                roles=len(result.created_roles),
                channels=len(result.created_channels),
            ),
        ]
        skipped = len(result.skipped_roles) + len(result.skipped_channels)
        if skipped:
            lines.append(
                ctx.t(
                    "server_setup.summary_skipped",
                    default="Skipped {count} existing item(s).",
                    count=skipped,
                )
            )
        if result.clamped:
            lines.append(
                ctx.t(
                    "server_setup.summary_clamped",
                    default="Some role permissions were reduced to what I can grant: {roles}.",
                    roles=", ".join(result.clamped),
                )
            )
        if result.unresolved_overwrites:
            lines.append(
                ctx.t(
                    "server_setup.summary_unresolved",
                    default="Could not resolve permission overwrites for: {roles}.",
                    roles=", ".join(sorted(set(result.unresolved_overwrites))),
                )
            )
        if result.failed:
            failures = "\n".join(f"• {name} — {why}" for name, why in result.failed)
            lines.append(
                ctx.t(
                    "server_setup.summary_failed",
                    default="Failed to create {count} item(s):\n{failures}",
                    count=len(result.failed),
                    failures=failures,
                )
            )
        return "\n".join(lines)

    # ── Persistence ───────────────────────────────────────────

    async def _previous_run(self, guild_id: int) -> dict[str, Any] | None:
        cfg = await self._store.load(guild_id)
        return cfg.get_other("server_setup")

    async def _record_run(self, ctx: "Context", spec: TemplateSpec, result: SetupResult) -> None:
        if ctx.guild is None:
            return
        applied = {
            "template": spec.key,
            "applied_at": datetime.now(timezone.utc).isoformat(),
            "applied_by": ctx.user.id,
            "created_role_ids": [role.id for role in result.created_roles],
            "created_channel_ids": [channel.id for channel in result.created_channels],
        }
        await self._store.mutate(
            ctx.guild.id, lambda cfg: cfg.set_other("server_setup", applied)
        )


def plan_changes_for_guild(spec: TemplateSpec, guild: discord.Guild) -> SetupPlan:
    """Build the additive plan for a real guild (thin wrapper over the pure planner)."""
    return plan_changes(
        spec,
        existing_role_names={normalize_role_name(role.name) for role in guild.roles},
        existing_channels=_existing_channels(guild),
    )
