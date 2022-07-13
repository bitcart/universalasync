import asyncio
import functools
import inspect
import sys
import types
from typing import Any, AsyncGenerator, Callable, Generator, Tuple, cast

from .utils import get_event_loop


def iter_over_async(agen: AsyncGenerator, run_func: Callable) -> Generator:
    ait = agen.__aiter__()

    async def get_next() -> Tuple[bool, Any]:
        try:
            obj = await ait.__anext__()
            return False, obj
        except StopAsyncIteration:
            return True, None

    while True:
        done, obj = run_func(get_next())
        if done:
            break
        yield obj


def run_sync_ctx(coroutine: Any, loop: asyncio.AbstractEventLoop) -> Any:
    if inspect.isawaitable(coroutine):
        return loop.run_until_complete(coroutine)

    if inspect.isasyncgen(coroutine):
        return iter_over_async(coroutine, lambda coro: loop.run_until_complete(coro))


def async_to_sync_wraps(function: Callable) -> Callable:
    """Wrap an async method/property to universal method.

    This allows to run wrapped methods in both async and sync contexts transparently without any additional code

    When run from another thread, it runs coroutines in new thread's event loop

    See :ref:`Example <example>` for full example

    Args:
        function (Callable): function/property to wrap

    Returns:
        Callable: modified function
    """
    is_property = inspect.isdatadescriptor(function)
    if is_property:
        function = cast(types.MethodDescriptorType, function).__get__

    @functools.wraps(function)
    def async_to_sync_wrap(*args: Any, **kwargs: Any) -> Any:
        loop = get_event_loop()
        coroutine = function(*args, **kwargs)

        if loop.is_running():
            return coroutine
        else:
            try:
                return run_sync_ctx(coroutine, loop)
            finally:
                shutdown_tasks(loop)
                loop.run_until_complete(loop.shutdown_asyncgens())
                if sys.version_info >= (3, 9):  # pragma: no cover
                    loop.run_until_complete(loop.shutdown_default_executor())

    result = async_to_sync_wrap
    if is_property:
        result = cast(Callable, property(cast(Callable, result)))
    return result


def shutdown_tasks(loop: asyncio.AbstractEventLoop) -> None:
    to_cancel = asyncio.all_tasks(loop)
    if not to_cancel:
        return
    for task in to_cancel:
        task.cancel()
    loop.run_until_complete(asyncio.gather(*to_cancel, return_exceptions=True))


def wrap(source: object) -> object:
    """Convert all public async methods/properties of an object to universal methods.

    See :func:`async_to_sync_wraps` for more info

    Args:
        source (object): object to convert

    Returns:
        object: converted object. Note that parameter passed is being modified anyway
    """
    for name in dir(source):
        method = getattr(source, name)

        if not name.startswith("_"):
            if inspect.iscoroutinefunction(method) or inspect.isasyncgenfunction(method) or inspect.isdatadescriptor(method):
                function = getattr(source, name)
                setattr(source, name, async_to_sync_wraps(function))

    return source
