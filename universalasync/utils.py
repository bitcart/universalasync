import asyncio


def get_event_loop() -> asyncio.AbstractEventLoop:
    """Useful utility for getting event loop. Acts like get_event_loop(), but also creates new event loop if needed

    This will return a working event loop in 100% of cases.

    Returns:
        asyncio.AbstractEventLoop: event loop
    """
    current_loop = asyncio._get_running_loop()
    if current_loop is not None:
        return current_loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    return loop
