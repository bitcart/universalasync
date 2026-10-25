import asyncio
import concurrent.futures
import functools
import threading
import weakref
from collections.abc import Awaitable, Callable, Coroutine
from typing import Any, Generic, TypeVar

from universalasync.utils import get_event_loop

T = TypeVar("T")


class LoopLocal(Generic[T]):
    """Keep one value per event loop, like `threading.local` does per thread, and close each value on its own loop.

    Wrapped methods run on the current thread's event loop, so resources bound to an event loop
    (like `aiohttp.ClientSession`) need one instance per loop. `LoopLocal` creates them lazily, and closes every one of
    them on the loop that owns it when [`close`][universalasync.loop_local.LoopLocal.close] is called,
    or when the `LoopLocal` is garbage collected.

    Args:
        close (Callable): async function closing a value. It must not reference the object holding this `LoopLocal`,
            or that object is never garbage collected. When the loop owning a value is already closed,
            the value is closed on another loop, so `close` must not need the closed loop
    """

    def __init__(self, close: Callable[[T], Coroutine[Any, Any, Any]]) -> None:
        self._close = close
        self._values: dict[asyncio.AbstractEventLoop, T] = {}
        weakref.finalize(self, _close_values_or_raise, self._values, close)

    def get(self, create: Callable[[], T]) -> T:
        """Return the value of the current event loop, creating it first if needed

        When a value is created, values of event loops closed since then are closed and dropped.

        Args:
            create (Callable): function creating the value. Unlike `close`, it is not stored,
                so it may reference the object holding this `LoopLocal`

        Returns:
            T: value bound to the current event loop
        """
        loop = get_event_loop()
        if loop not in self._values:
            closed = {owner: self._values.pop(owner) for owner in list(self._values) if owner.is_closed()}
            for error in _close_values(closed, self._close):
                _report_close_error(loop, error)
            self._values[loop] = create()
        return self._values[loop]

    def close(self) -> Any:
        """Close all values, each on the event loop that owns it"""
        if asyncio._get_running_loop() is None:
            _close_values_or_raise(self._values, self._close)
            return None
        return self._close_async()

    async def _close_async(self) -> None:
        running_loop = asyncio.get_running_loop()
        awaitables: list[Awaitable[Any]] = []
        while self._values:
            loop, value = self._values.popitem()
            coroutine = self._close(value)
            if loop is running_loop or loop.is_closed():
                awaitables.append(coroutine)
            elif loop.is_running():
                awaitables.append(asyncio.wrap_future(asyncio.run_coroutine_threadsafe(coroutine, loop)))
            else:
                awaitables.append(asyncio.to_thread(loop.run_until_complete, coroutine))
        closing = [asyncio.ensure_future(awaitable) for awaitable in awaitables]
        try:
            results = await asyncio.shield(asyncio.gather(*closing, return_exceptions=True))
        except asyncio.CancelledError:
            for future in closing:
                future.add_done_callback(functools.partial(_report_future_error, running_loop))
            raise
        errors = [result for result in results if isinstance(result, Exception)]
        if errors:
            raise errors[0]


def _close_values(
    values: dict[asyncio.AbstractEventLoop, T], close: Callable[[T], Coroutine[Any, Any, Any]]
) -> list[Exception]:
    errors: list[Exception] = []
    while values:
        loop, value = values.popitem()
        try:
            _close_on(loop, close(value))
        except Exception as e:
            errors.append(e)
    return errors


def _close_values_or_raise(values: dict[asyncio.AbstractEventLoop, T], close: Callable[[T], Coroutine[Any, Any, Any]]) -> None:
    errors = _close_values(values, close)
    if errors:
        raise errors[0]


def _close_on(loop: asyncio.AbstractEventLoop, coroutine: Coroutine[Any, Any, Any]) -> None:
    running_loop = asyncio._get_running_loop()
    if loop.is_closed():
        if running_loop is None:
            temporary_loop = asyncio.new_event_loop()
            try:
                temporary_loop.run_until_complete(coroutine)
            finally:
                temporary_loop.close()
        else:
            running_loop.create_task(coroutine)
    elif loop.is_running():
        future = asyncio.run_coroutine_threadsafe(coroutine, loop)
        future.add_done_callback(functools.partial(_report_future_error, loop))
    elif running_loop is None:
        loop.run_until_complete(coroutine)
    else:
        threading.Thread(target=_run_in_thread, args=(loop, coroutine)).start()


def _run_in_thread(loop: asyncio.AbstractEventLoop, coroutine: Coroutine[Any, Any, Any]) -> None:
    try:
        loop.run_until_complete(coroutine)
    except Exception as e:
        _report_close_error(loop, e)


def _report_future_error(
    loop: asyncio.AbstractEventLoop, future: asyncio.Future[Any] | concurrent.futures.Future[Any]
) -> None:
    if not future.cancelled():
        _report_close_error(loop, future.exception())


def _report_close_error(loop: asyncio.AbstractEventLoop, error: BaseException | None) -> None:
    if isinstance(error, Exception):
        loop.call_exception_handler({"message": "Error closing a LoopLocal value", "exception": error})
