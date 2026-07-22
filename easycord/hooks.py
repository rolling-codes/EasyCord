from __future__ import annotations

import asyncio
import inspect
import logging
from typing import Any, Callable

logger = logging.getLogger("easycord")

SUPPORTED_HOOKS = {
    "before_command",
    "after_command",
    "on_plugin_load",
    "on_plugin_unload",
}

class HookRegistry:
    """A registry for managing and firing lifecycle and execution hooks."""

    def __init__(self) -> None:
        self._callbacks: dict[str, list[Callable[..., Any]]] = {
            hook: [] for hook in SUPPORTED_HOOKS
        }

    def register(self, hook_name: str, callback: Callable[..., Any]) -> None:
        """Register a callback for a specific hook.

        Parameters
        ----------
        hook_name:
            The name of the hook (e.g. 'before_command').
        callback:
            The callable to invoke when the hook is fired.
        """
        if hook_name not in SUPPORTED_HOOKS:
            raise ValueError(f"Unsupported hook: {hook_name}. Supported hooks: {sorted(SUPPORTED_HOOKS)}")
        if not callable(callback):
            raise TypeError("Callback must be callable")
        self._callbacks[hook_name].append(callback)

    def unregister(self, hook_name: str, callback: Callable[..., Any]) -> bool:
        """Remove a previously registered callback from a hook.

        Parameters
        ----------
        hook_name:
            The name of the hook (e.g. 'before_command').
        callback:
            The callable to remove. If it was never registered, returns
            ``False`` without raising.

        Returns
        -------
        bool
            ``True`` if the callback was found and removed, ``False`` if it
            was not registered.
        """
        if hook_name not in SUPPORTED_HOOKS:
            raise ValueError(f"Unsupported hook: {hook_name}. Supported hooks: {sorted(SUPPORTED_HOOKS)}")
        try:
            self._callbacks[hook_name].remove(callback)
            return True
        except ValueError:
            return False

    async def fire(self, hook_name: str, **kwargs: Any) -> None:
        """Fire a hook, executing all registered callbacks.

        Parameters
        ----------
        hook_name:
            The name of the hook to fire.
        kwargs:
            Keyword arguments to pass to the callbacks.
        """
        if hook_name not in SUPPORTED_HOOKS:
            raise ValueError(f"Unsupported hook: {hook_name}. Supported hooks: {sorted(SUPPORTED_HOOKS)}")

        for callback in self._callbacks[hook_name]:
            if inspect.iscoroutinefunction(callback):
                await callback(**kwargs)
            else:
                callback(**kwargs)
