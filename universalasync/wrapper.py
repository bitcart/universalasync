import asyncio
import functools
import inspect
from typing import Any, AsyncGenerator, Callable, Generator, Tuple

from .utils import get_event_loop


def iter_over_async(ait: AsyncGenerator, run_func: Callable) -> Generator:
    ait = ait.__aiter__()

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


def async_to_sync_wraps(function: Callable, is_property: bool = False) -> Callable:
    @functools.wraps(function)
    def async_to_sync_wrap(*args: Any, **kwargs: Any) -> Any:
        loop = get_event_loop()

        if is_property:
            coroutine = function.__get__(*args, **kwargs)  # type: ignore
        else:
            coroutine = function(*args, **kwargs)

        if loop.is_running():
            return coroutine
        else:
            try:
                return run_sync_ctx(coroutine, loop)
            finally:
                shutdown_tasks(loop)
                loop.run_until_complete(loop.shutdown_asyncgens())

    result = async_to_sync_wrap
    if is_property:
        result = property(result)  # type: ignore
    return result


def shutdown_tasks(loop: asyncio.AbstractEventLoop) -> None:
    to_cancel = asyncio.all_tasks(loop)
    if not to_cancel:
        return
    for task in to_cancel:
        task.cancel()
    loop.run_until_complete(asyncio.gather(*to_cancel, return_exceptions=True))


def async_to_sync(obj: object, name: str, is_property: bool = False) -> None:
    function = getattr(obj, name)

    setattr(obj, name, async_to_sync_wraps(function, is_property=is_property))


def wrap(source: object) -> object:
    for name in dir(source):
        method = getattr(source, name)

        if not name.startswith("_"):
            is_property = inspect.isdatadescriptor(method)
            if inspect.iscoroutinefunction(method) or inspect.isasyncgenfunction(method) or is_property:
                async_to_sync(source, name, is_property=is_property)

    return source
