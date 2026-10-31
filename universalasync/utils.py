import asyncio
import os
import signal
import sys
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from asyncio.events import _AbstractEventLoopPolicy


def _create_new_event_loop() -> asyncio.AbstractEventLoop:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    return loop


def _get_event_loop_policy() -> "_AbstractEventLoopPolicy":
    if sys.version_info >= (3, 14):
        return asyncio.events._get_event_loop_policy()
    return asyncio.get_event_loop_policy()


def _reset_event_loop_after_fork() -> None:
    policy = cast(Any, asyncio.events)._event_loop_policy
    if policy is not None:
        policy._local = type(policy._local)()
    signal.set_wakeup_fd(-1)


# python 3.12+ does the same reset itself: https://github.com/python/cpython/pull/99539
if sys.version_info < (3, 12) and hasattr(os, "register_at_fork"):
    os.register_at_fork(after_in_child=_reset_event_loop_after_fork)


def _get_event_loop() -> asyncio.AbstractEventLoop:
    current_loop = asyncio._get_running_loop()
    if current_loop is not None:
        return current_loop
    loop: asyncio.AbstractEventLoop | None = cast(Any, _get_event_loop_policy())._local._loop
    if loop is not None:
        return loop
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
