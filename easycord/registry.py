import logging
from typing import Callable, Any

logger = logging.getLogger("easycord")


class InteractionRegistry:
    """Central registry for persistent interaction handlers."""

    def __init__(self):
        self.components: dict[str, dict[str, Any]] = {}
        self.modals: dict[str, dict[str, Any]] = {}

    def register_component(self, custom_id: str, func: Callable, source_plugin: str | None = None) -> None:
        if custom_id in self.components:
            existing = self.components[custom_id]
            raise ValueError(
                f"Component ID {custom_id!r} already registered by:\n"
                f"- Plugin: {existing.get('plugin') or 'Bot'}\n"
                f"- Method: {existing['func'].__name__}"
            )
        self.components[custom_id] = {"func": func, "plugin": source_plugin}
        logger.debug(
            "Registered COMPONENT %r\n  → Plugin: %s\n  → Method: %s",
            custom_id,
            source_plugin or "Bot",
            func.__name__,
        )

    def register_modal(self, custom_id: str, func: Callable, source_plugin: str | None = None) -> None:
        if custom_id in self.modals:
            existing = self.modals[custom_id]
            raise ValueError(
                f"Modal ID {custom_id!r} already registered by:\n"
                f"- Plugin: {existing.get('plugin') or 'Bot'}\n"
                f"- Method: {existing['func'].__name__}"
            )
        self.modals[custom_id] = {"func": func, "plugin": source_plugin}
        logger.debug(
            "Registered MODAL %r\n  → Plugin: %s\n  → Method: %s",
            custom_id,
            source_plugin or "Bot",
            func.__name__,
        )
