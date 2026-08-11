"""Helpers for common plugin lifecycle patterns.

Eliminates repetitive on_ready/on_unload task management boilerplate.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from .plugin import Plugin

logger = logging.getLogger("easycord")

# Special key for timers that are not grouped by guild_id
_UNGROUPED_KEY = "__ungrouped__"


class TaskManager:
    """Simple task storage and lifecycle management for plugins.
    
    Eliminates the need to manually track asyncio.Task handles and cancel them
    in on_unload().
    
    Example::
    
        class MyPlugin(Plugin):
            def __init__(self):
                super().__init__()
                self.tasks = TaskManager()
            
            async def on_load(self):
                # This task will be tracked automatically
                await self.tasks.start_recurring(self._background_loop, 60.0)
            
            async def on_unload(self):
                # All tasks are cancelled automatically
                await self.tasks.cancel_all()
            
            async def _background_loop(self):
                # Do work
                pass
    """
    
    def __init__(self) -> None:
        self.tasks: dict[str, asyncio.Task] = {}
    
    def track(self, name: str, task: asyncio.Task) -> asyncio.Task:
        """Register a task for tracking.
        
        Returns the task (for chaining).
        """
        self.tasks[name] = task
        task.add_done_callback(lambda t: self.tasks.pop(name, None))
        return task
    
    async def start_once(self, name: str, coro, *args, **kwargs) -> asyncio.Task:
        """Start a task and track it by name.
        
        If a task with that name already exists, returns the existing one.
        """
        if name in self.tasks and not self.tasks[name].done():
            return self.tasks[name]
        task = asyncio.create_task(coro(*args, **kwargs) if callable(coro) else coro)
        return self.track(name, task)
    
    async def start_recurring(
        self,
        fn: Callable,
        interval: float,
        name: str | None = None,
    ) -> asyncio.Task:
        """Start a recurring task with fixed interval.
        
        Parameters
        ----------
        fn: Callable
            Async function to call repeatedly.
        interval: float
            Seconds between calls.
        name: str
            Task name (defaults to fn.__name__).
        
        Returns
        -------
        The asyncio.Task handle.
        """
        name = name or fn.__name__
        
        async def loop():
            try:
                while True:
                    try:
                        await fn()
                    except Exception:
                        logger.exception(f"Error in recurring task {name}")
                    await asyncio.sleep(interval)
            except asyncio.CancelledError:
                pass
        
        task = asyncio.create_task(loop())
        return self.track(name, task)
    
    async def cancel_all(self) -> None:
        """Cancel all tracked tasks."""
        for task in list(self.tasks.values()):
            if not task.done():
                task.cancel()
        if self.tasks:
            await asyncio.gather(*self.tasks.values(), return_exceptions=True)
        self.tasks.clear()


class TimerManager:
    """Timer scheduling for delayed/recurring tasks (like giveaways, reminders).
    
    Eliminates the need to track timers in dicts and cancel them manually.
    
    Example::
    
        class GiveawayPlugin(Plugin):
            def __init__(self):
                super().__init__()
                self.timers = TimerManager()
            
            async def start_giveaway(self, guild_id: int, message_id: int, seconds: float):
                # Timer is tracked automatically; named "giveaway:{guild_id}:{message_id}"
                await self.timers.schedule(
                    f"giveaway:{guild_id}:{message_id}",
                    self._end_giveaway,
                    seconds,
                    guild_id,
                    message_id,
                )
            
            async def on_unload(self):
                await self.timers.cancel_all()
            
            async def _end_giveaway(self, guild_id: int, message_id: int):
                # Timer fires and handler is called automatically
                pass
    """
    
    def __init__(self) -> None:
        # Maps timer_id -> {guild_id -> task} for hierarchical cancellation
        # Timers without guild_id are stored under _UNGROUPED_KEY
        self.timers: dict[str, dict[int | str, asyncio.Task]] = {}
    
    async def schedule(
        self,
        timer_id: str,
        fn: Callable,
        seconds: float,
        *args,
        guild_id: int | None = None,
        **kwargs,
    ) -> asyncio.Task:
        """Schedule a function to run after *seconds*.
        
        Parameters
        ----------
        timer_id: str
            Unique timer identifier (e.g., "giveaway:123:456").
        fn: Callable
            Async function to call.
        seconds: float
            Delay in seconds before calling.
        guild_id: int
            Optional guild ID for hierarchical tracking (enables cancel_guild).
        args, kwargs: 
            Arguments passed to *fn*.
        
        Returns
        -------
        The asyncio.Task handle.
        """
        async def delayed():
            try:
                await asyncio.sleep(seconds)
                await fn(*args, **kwargs)
            except asyncio.CancelledError:
                pass
            finally:
                if guild_id is not None:
                    self.timers.get(timer_id, {}).pop(guild_id, None)
                else:
                    self.timers.get(timer_id, {}).pop(_UNGROUPED_KEY, None)
        
        task = asyncio.create_task(delayed())
        # Store ungrouped timers under a special key so cancel_all() catches them
        key = guild_id if guild_id is not None else _UNGROUPED_KEY
        self.timers.setdefault(timer_id, {})[key] = task
        return task
    
    async def cancel_timer(self, timer_id: str, guild_id: int | None = None) -> None:
        """Cancel a specific timer.
        
        If *guild_id* is provided, cancels only that timer within the guild.
        Otherwise cancels all timers with that ID.
        """
        if timer_id not in self.timers:
            return
        
        if guild_id is not None:
            task = self.timers[timer_id].pop(guild_id, None)
            if task and not task.done():
                task.cancel()
        else:
            for task in self.timers[timer_id].values():
                if not task.done():
                    task.cancel()
            self.timers.pop(timer_id, None)
    
    async def cancel_guild(self, timer_id: str, guild_id: int) -> None:
        """Cancel all timers for a specific guild."""
        await self.cancel_timer(timer_id, guild_id=guild_id)
    
    async def cancel_all(self) -> None:
        """Cancel all tracked timers."""
        tasks = []
        for timer_dict in self.timers.values():
            for task in timer_dict.values():
                if not task.done():
                    task.cancel()
                    tasks.append(task)
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self.timers.clear()
