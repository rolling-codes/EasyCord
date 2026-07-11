from __future__ import annotations

import asyncio
import inspect
import logging
from typing import Any, Callable

logger = logging.getLogger("easycord")

class EventBus:
    """An asynchronous event bus supporting event publishing and subscriptions."""

    def __init__(self) -> None:
        self._listeners: dict[str, list[Callable[..., Any]]] = {}

    def subscribe(self, event: str, callback: Callable[..., Any]) -> None:
        """Subscribe a callback to a specific event.

        Callbacks for the same event are invoked in registration order:
        :meth:`publish` calls them in the order they were subscribed.

        Parameters
        ----------
        event:
            The event name to subscribe to.
        callback:
            The callable to invoke when the event is published.
        """
        if not event:
            raise ValueError("Event name cannot be empty")
        if not callable(callback):
            raise TypeError("Callback must be callable")
        self._listeners.setdefault(event, []).append(callback)

    def unsubscribe(self, event: str, callback: Callable[..., Any]) -> None:
        """Unsubscribe a callback from a specific event.

        Parameters
        ----------
        event:
            The event name.
        callback:
            The callback to unsubscribe.
        """
        if event in self._listeners:
            try:
                self._listeners[event].remove(callback)
            except ValueError:
                logger.debug(
                    "Attempted to unsubscribe non-existent callback from event %r",
                    event,
                )
            if not self._listeners[event]:
                del self._listeners[event]

    async def publish(self, event: str, **payload: Any) -> None:
        """Publish an event, invoking all subscribed callbacks.

        Listeners are invoked sequentially in registration order (the order
        they were passed to :meth:`subscribe`). A raising callback is logged
        with its ``__qualname__`` and does not stop later callbacks from
        running.

        Parameters
        ----------
        event:
            The event name to publish.
        payload:
            Keyword arguments passed as payload to the callbacks.
        """
        if event not in self._listeners:
            return

        for callback in list(self._listeners.get(event, [])):
            try:
                if inspect.iscoroutinefunction(callback):
                    await callback(**payload)
                else:
                    callback(**payload)
            except Exception as e:
                logger.error(
                    "Error in EventBus subscriber %r for event %r: %s",
                    getattr(callback, "__qualname__", repr(callback)),
                    event,
                    e,
                    exc_info=True,
                )
