import asyncio
import threading


def _get_event_loop() -> asyncio.AbstractEventLoop:
    try:
        # NOTE: do NOT remove those 2 lines. Otherwise everything just hangs because of incorrect loop being used
        if threading.current_thread() is threading.main_thread():
            return asyncio.get_event_loop_policy().get_event_loop()
        return asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop


def get_event_loop() -> asyncio.AbstractEventLoop:
    """Useful utility for getting event loop. Acts like get_event_loop(), but also creates new event loop if needed

    This will return a working event loop in 100% of cases.

    Returns:
        asyncio.AbstractEventLoop: event loop
    """
    loop = _get_event_loop()
    if loop.is_closed():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop
