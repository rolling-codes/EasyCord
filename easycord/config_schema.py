"""Versioned plugin configuration schema with migration support."""
from __future__ import annotations

import copy
import logging
from typing import Any, Callable

logger = logging.getLogger("easycord")


class ConfigSchema:
    """Declarative schema for a plugin config section.

    Usage::

        _DEFAULTS = {"enabled": True, "channel": None}
        SCHEMA = ConfigSchema(key="myplugin", version=1, defaults=_DEFAULTS)

        @SCHEMA.migration(from_version=1)
        def _v1_to_v2(section: dict) -> dict:
            return {**section, "new_field": "default_value"}

    Pass ``SCHEMA`` to :meth:`PluginConfigManager.get_schema` to get a
    healed-and-persisted config section. The ``_v`` version stamp is
    maintained automatically and is never exposed in ``defaults``.
    """

    def __init__(self, *, key: str, version: int, defaults: dict[str, Any]) -> None:
        self._key = key
        self._version = version
        self._defaults = defaults
        self._migrations: dict[int, Callable[[dict[str, Any]], dict[str, Any]]] = {}

    @property
    def key(self) -> str:
        return self._key

    @property
    def version(self) -> int:
        return self._version

    def migration(self, *, from_version: int) -> Callable:
        """Register a migration from ``from_version`` to ``from_version + 1``."""

        def decorator(
            fn: Callable[[dict[str, Any]], dict[str, Any]],
        ) -> Callable[[dict[str, Any]], dict[str, Any]]:
            self._migrations[from_version] = fn
            return fn

        return decorator

    def apply(
        self, section: dict[str, Any] | None
    ) -> tuple[dict[str, Any], list[str]]:
        """Heal *section* against this schema.  Pure — no I/O.

        Returns ``(healed_section, changes)`` where *changes* is a list of
        human-readable strings describing every alteration made.  An empty
        list means the section was already valid; callers may skip persisting.

        Behaviour:
        - Absent / empty section → deep copy of defaults, stamped with ``_v``.
        - Non-dict value → replaced with defaults, reported in changes.
        - Existing section → migrations run step-wise from its ``_v`` (missing
          ``_v`` is treated as pre-schema version 1); missing default keys are
          backfilled; unknown keys are preserved; ``_v`` is stamped.
        """
        changes: list[str] = []

        # --- absent / empty / wrong type ----------------------------------------
        if section is None or section == {}:
            result = copy.deepcopy(self._defaults)
            result["_v"] = self._version
            changes.append("initialized with defaults")
            return result, changes

        if not isinstance(section, dict):
            changes.append(
                f"replaced non-dict value ({type(section).__name__}) with defaults"
            )
            result = copy.deepcopy(self._defaults)
            result["_v"] = self._version
            return result, changes

        # --- work on a shallow copy so the caller's dict is untouched -----------
        result = dict(section)

        # --- migrations ---------------------------------------------------------
        current_v = result.get("_v")
        if current_v is None:
            current_v = 1  # pre-schema; treat as version 1
            if self._version > 1:
                changes.append("no _v stamp — treating as pre-schema v1")

        if isinstance(current_v, int) and current_v < self._version:
            v = current_v
            while v < self._version:
                if v in self._migrations:
                    result = self._migrations[v](result)
                    changes.append(f"migrated v{v}→v{v + 1}")
                v += 1
            result["_v"] = self._version

        # --- backfill missing default keys (unknown keys preserved) -------------
        for k, default_val in self._defaults.items():
            if k not in result:
                result[k] = copy.deepcopy(default_val)
                changes.append(f"backfilled missing key '{k}'")

        # --- ensure _v stamp (handles first heal on a v1 schema) ---------------
        if "_v" not in result:
            result["_v"] = self._version
            changes.append("added _v stamp")

        return result, changes
