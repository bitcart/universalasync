import asyncio


def _create_new_event_loop() -> asyncio.AbstractEventLoop:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    return loop


def _get_event_loop() -> asyncio.AbstractEventLoop:
    current_loop = asyncio._get_running_loop()
    if current_loop is not None:
        return current_loop
    policy = asyncio.get_event_loop_policy()
    if policy._local._loop is not None:
        return policy._local._loop
    return _create_new_event_loop()


def get_event_loop() -> asyncio.AbstractEventLoop:
    """Useful utility for getting event loop. Acts like get_event_loop(), but also creates new event loop if needed

    This will return a working event loop in 100% of cases.

    Returns:
        asyncio.AbstractEventLoop: event loop
    """
    loop = _get_event_loop()
    if loop.is_closed():
        return _create_new_event_loop()
    return loop
