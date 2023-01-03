import asyncio
import signal
from typing import Any

from .utils import get_event_loop
from .wrapper import async_to_sync_wraps, wrap

asyncio.get_event_loop_policy()  # initialize default policy import-time to allow get_event_loop() to work even in finalizers


@async_to_sync_wraps
async def idle() -> None:
    """Useful for making event loop idle in the main thread for other threads to work"""
    is_idling = True

    def signal_handler(*args: Any, **kwargs: Any) -> None:
        nonlocal is_idling

        is_idling = False

    for s in (signal.SIGINT, signal.SIGTERM, signal.SIGABRT):
        signal.signal(s, signal_handler)

    while is_idling:
        await asyncio.sleep(1)


__all__ = ["async_to_sync_wraps", "wrap", "get_event_loop", "idle"]
