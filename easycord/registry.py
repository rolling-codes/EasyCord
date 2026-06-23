"""Interaction inventory and routing helpers."""
from __future__ import annotations

from dataclasses import dataclass, field
import logging
import re
import time
from typing import Any, Callable, Literal

logger = logging.getLogger("easycord")

InteractionType = Literal[
    "slash",
    "context_menu",
    "component",
    "modal",
    "autocomplete",
]


_TYPE_PATTERNS: dict[str, str] = {
    "str": r"[^:]+",
    "int": r"-?\d+",
    "snowflake": r"\d{15,22}",
}


@dataclass
class InteractionEntry:
    """Metadata for one EasyCord interaction registration."""

    interaction_type: InteractionType
    name: str
    callback: Callable
    source: str | None = None
    guild_id: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    sync_state: str = "local"
    registered_at: float = field(default_factory=time.time)
    pattern: str | None = None
    regex: re.Pattern[str] | None = None
    variables: list[tuple[str, str]] = field(default_factory=list)
    expires_at: float | None = None

    def __getitem__(self, key: str) -> Any:
        aliases = {
            "func": "callback",
            "plugin": "source",
            "custom_id": "name",
        }
        return getattr(self, aliases.get(key, key))

    def get(self, key: str, default: Any = None) -> Any:
        try:
            return self[key]
        except AttributeError:
            return default

    def to_dict(self) -> dict[str, Any]:
        return {
            "interaction_type": self.interaction_type,
            "name": self.name,
            "pattern": self.pattern,
            "callback": getattr(self.callback, "__name__", repr(self.callback)),
            "source": self.source,
            "plugin": self.source,
            "guild_id": self.guild_id,
            "metadata": dict(self.metadata),
            "enabled": self.enabled,
            "sync_state": self.sync_state,
            "registered_at": self.registered_at,
            "expires_at": self.expires_at,
        }


class InteractionRegistry:
    """Authoritative EasyCord inventory for registered interactions.

    ``discord.app_commands.CommandTree`` remains the sync backend. This registry
    tracks EasyCord metadata for inspection, collision checks, plugin unload, and
    developer sync planning.
    """

    def __init__(self):
        self.slash_commands: dict[str, InteractionEntry] = {}
        self.context_menus: dict[str, InteractionEntry] = {}
        self.components: dict[str, InteractionEntry] = {}
        self.modals: dict[str, InteractionEntry] = {}
        self.autocomplete_callbacks: dict[str, InteractionEntry] = {}

    # ── Registration ─────────────────────────────────────────

    def register_slash_command(
        self,
        name: str,
        func: Callable,
        *,
        source_plugin: str | None = None,
        guild_id: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> InteractionEntry:
        return self._register_named(
            self.slash_commands,
            "slash",
            name,
            func,
            source_plugin=source_plugin,
            guild_id=guild_id,
            metadata=metadata,
        )

    def register_context_menu(
        self,
        name: str,
        func: Callable,
        *,
        source_plugin: str | None = None,
        guild_id: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> InteractionEntry:
        return self._register_named(
            self.context_menus,
            "context_menu",
            name,
            func,
            source_plugin=source_plugin,
            guild_id=guild_id,
            metadata=metadata,
        )

    def register_component(
        self,
        custom_id: str,
        func: Callable,
        source_plugin: str | None = None,
        *,
        ttl: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> InteractionEntry:
        entry = self._build_component_entry(
            "component",
            custom_id,
            func,
            source_plugin,
            ttl=ttl,
            metadata=metadata,
        )
        self._detect_component_collision(entry)
        self.components[custom_id] = entry
        logger.debug("Registered COMPONENT %r from %s", custom_id, source_plugin or "Bot")
        return entry

    def register_modal(
        self,
        custom_id: str,
        func: Callable,
        source_plugin: str | None = None,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> InteractionEntry:
        if custom_id in self.modals:
            existing = self.modals[custom_id]
            plugin = existing.source or "Bot"
            existing_name = existing.callback.__name__
            raise ValueError(
                f"Modal ID {custom_id!r} already registered by {plugin}:{existing_name}. "
                f"Ensure your modal IDs are unique across all plugins."
            )
        entry = InteractionEntry(
            interaction_type="modal",
            name=custom_id,
            callback=func,
            source=source_plugin,
            metadata=metadata or {},
        )
        self.modals[custom_id] = entry
        logger.debug("Registered MODAL %r from %s", custom_id, source_plugin or "Bot")
        return entry

    def register_autocomplete(
        self,
        command_name: str,
        option_name: str,
        func: Callable,
        *,
        source_plugin: str | None = None,
        guild_id: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> InteractionEntry:
        key = f"{self._scope_key(guild_id)}:{command_name}:{option_name}"
        return self._register_named(
            self.autocomplete_callbacks,
            "autocomplete",
            key,
            func,
            source_plugin=source_plugin,
            guild_id=guild_id,
            metadata={
                "command_name": command_name,
                "option_name": option_name,
                **(metadata or {}),
            },
        )

    def _register_named(
        self,
        bucket: dict[str, InteractionEntry],
        interaction_type: InteractionType,
        name: str,
        func: Callable,
        *,
        source_plugin: str | None,
        guild_id: int | None,
        metadata: dict[str, Any] | None,
    ) -> InteractionEntry:
        key = f"{self._scope_key(guild_id)}:{name}"
        if key in bucket:
            existing = bucket[key]
            plugin = existing.source or "Bot"
            existing_name = existing.callback.__name__
            raise ValueError(
                f"{interaction_type.replace('_', ' ').title()} {name!r} already registered by {plugin}:{existing_name}. "
                f"Slash commands and context menus must have unique names."
            )
        entry = InteractionEntry(
            interaction_type=interaction_type,
            name=name,
            callback=func,
            source=source_plugin,
            guild_id=guild_id,
            metadata=metadata or {},
        )
        bucket[key] = entry
        return entry

    # ── Components ────────────────────────────────────────────

    def _build_component_entry(
        self,
        interaction_type: InteractionType,
        custom_id: str,
        func: Callable,
        source_plugin: str | None,
        *,
        ttl: float | None,
        metadata: dict[str, Any] | None,
    ) -> InteractionEntry:
        regex, variables = self._compile_pattern(custom_id)
        return InteractionEntry(
            interaction_type=interaction_type,
            name=custom_id,
            pattern=custom_id if regex is not None else None,
            regex=regex,
            variables=variables,
            callback=func,
            source=source_plugin,
            metadata=metadata or {},
            expires_at=time.time() + ttl if ttl is not None else None,
        )

    def _detect_component_collision(self, entry: InteractionEntry) -> None:
        custom_id = entry.name
        if custom_id in self.components:
            existing = self.components[custom_id]
            plugin = existing.source or "Bot"
            func = existing.callback.__name__
            raise ValueError(
                f"Component ID {custom_id!r} already registered by {plugin}:{func}. "
                f"Ensure your custom_ids are unique."
            )
        def _shape(pattern: str) -> str:
            return re.sub(r"\?P<[^>]+>", "", pattern)

        for existing in self.components.values():
            if existing.regex is not None and entry.regex is not None:
                if _shape(existing.regex.pattern) == _shape(entry.regex.pattern):
                    raise ValueError(
                        f"Dynamic component pattern {custom_id!r} from {entry.source or 'Bot'} "
                        f"collides with pattern {existing.name!r} from {existing.source or 'Bot'}. "
                        f"They share the same underlying structure: {_shape(entry.regex.pattern)}"
                    )
            elif existing.regex is not None and existing.regex.fullmatch(custom_id):
                raise ValueError(
                    f"Static component ID {custom_id!r} from {entry.source or 'Bot'} "
                    f"collides with dynamic pattern {existing.name!r} from {existing.source or 'Bot'}."
                )
            elif entry.regex is not None and entry.regex.fullmatch(existing.name):
                raise ValueError(
                    f"Dynamic component pattern {custom_id!r} from {entry.source or 'Bot'} "
                    f"collides with static ID {existing.name!r} from {existing.source or 'Bot'}."
                )

    @staticmethod
    def _compile_pattern(pattern: str) -> tuple[re.Pattern[str] | None, list[tuple[str, str]]]:
        if "{" not in pattern:
            return None, []
        variables: list[tuple[str, str]] = []
        regex = ""
        pos = 0
        for match in re.finditer(r"\{([a-zA-Z_]\w*)(?::([a-zA-Z_]\w*))?\}", pattern):
            regex += re.escape(pattern[pos:match.start()])
            name = match.group(1)
            kind = match.group(2) or "str"
            if kind not in _TYPE_PATTERNS:
                raise ValueError(
                    f"Unsupported component route type {kind!r}; use str, int, or snowflake"
                )
            variables.append((name, kind))
            regex += f"(?P<{name}>{_TYPE_PATTERNS[kind]})"
            pos = match.end()
        regex += re.escape(pattern[pos:])
        return re.compile(f"^{regex}$"), variables

    def resolve_component(self, custom_id: str) -> tuple[InteractionEntry | None, dict[str, Any]]:
        entry = self.components.get(custom_id)
        if entry is not None:
            return (entry if self._entry_active(entry) else None), {}
        for candidate in self.components.values():
            if candidate.regex is None:
                continue
            match = candidate.regex.fullmatch(custom_id)
            if match is None or not self._entry_active(candidate):
                continue
            return candidate, {
                name: self._coerce_component_value(match.group(name), kind)
                for name, kind in candidate.variables
            }
        return None, {}

    @staticmethod
    def _coerce_component_value(value: str, kind: str) -> Any:
        if kind in {"int", "snowflake"}:
            return int(value)
        return value

    @staticmethod
    def _entry_active(entry: InteractionEntry) -> bool:
        if not entry.enabled:
            return False
        return entry.expires_at is None or entry.expires_at >= time.time()

    # ── Inventory ────────────────────────────────────────────

    def unregister_plugin(self, plugin_name: str) -> None:
        for bucket in (
            self.slash_commands,
            self.context_menus,
            self.components,
            self.modals,
            self.autocomplete_callbacks,
        ):
            for key, entry in list(bucket.items()):
                if entry.source == plugin_name:
                    bucket.pop(key, None)

    def grouped(self) -> dict[str, list[dict[str, Any]]]:
        return {
            "slash": [entry.to_dict() for entry in self.slash_commands.values()],
            "context_menu": [entry.to_dict() for entry in self.context_menus.values()],
            "component": [entry.to_dict() for entry in self.components.values()],
            "modal": [entry.to_dict() for entry in self.modals.values()],
            "autocomplete": [
                entry.to_dict() for entry in self.autocomplete_callbacks.values()
            ],
        }

    def iter_syncable(self, *, guild_id: int | None = None) -> list[InteractionEntry]:
        scope = self._scope_key(guild_id)
        return [
            entry
            for bucket in (self.slash_commands, self.context_menus)
            for key, entry in bucket.items()
            if key.startswith(f"{scope}:")
        ]

    @staticmethod
    def _scope_key(guild_id: int | None) -> str:
        return f"guild:{guild_id}" if guild_id is not None else "global"
