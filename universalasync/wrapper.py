import asyncio
import functools
import inspect
import types
from collections.abc import AsyncGenerator, Callable, Generator
from typing import Any, TypeVar, cast

from universalasync.utils import get_event_loop


def iter_over_async(agen: AsyncGenerator[Any, Any], run_func: Callable) -> Generator:
    ait = agen.__aiter__()

    async def get_next() -> tuple[bool, Any]:
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


def run_in_loop(coroutine: Any, loop: asyncio.AbstractEventLoop) -> Any:
    if loop.is_running():
        return asyncio.run_coroutine_threadsafe(coroutine, loop).result()
    return loop.run_until_complete(coroutine)


def run_sync_ctx(coroutine: Any, loop: asyncio.AbstractEventLoop) -> Any:
    if inspect.isawaitable(coroutine):
        return run_in_loop(coroutine, loop)

    if inspect.isasyncgen(coroutine):
        return iter_over_async(coroutine, lambda coro: run_in_loop(coro, loop))

    return coroutine


class WrappedDescriptor:
    def __init__(self, descriptor: Any, getter: Callable) -> None:
        self.descriptor = descriptor
        self.getter = getter

    def __get__(self, instance: Any, owner: type | None = None) -> Any:
        if instance is None:
            return self
        return self.getter(instance)

    def __set__(self, instance: Any, value: Any) -> None:
        self.descriptor.__set__(instance, value)

    def __delete__(self, instance: Any) -> None:
        self.descriptor.__delete__(instance)


def async_to_sync_wraps(function: Callable) -> Callable:
    """Wrap an async method/property to universal method.

    This allows to run wrapped methods in both async and sync contexts transparently without any additional code

    When run from another thread, it runs coroutines in new thread's event loop.
    If the current thread's event loop is running in another thread, it runs coroutines there and waits for the result

    See [Example](index.md#example-of-usage) for full example

    Args:
        function (Callable): function/property to wrap

    Returns:
        Callable: modified function
    """
    descriptor = function
    is_property = inspect.isdatadescriptor(function)
    if is_property:
        function = cast(types.MethodDescriptorType, function).__get__

    @functools.wraps(getattr(descriptor, "fget", None) or function)
    def async_to_sync_wrap(*args: Any, **kwargs: Any) -> Any:
        loop = get_event_loop()
        coroutine = function(*args, **kwargs)

        if asyncio._get_running_loop() is loop:
            return coroutine
        return run_sync_ctx(coroutine, loop)

    result: Callable = async_to_sync_wrap
    if isinstance(descriptor, property):
        result = cast(Callable, descriptor.getter(result))
    elif is_property:
        result = cast(Callable, WrappedDescriptor(descriptor, result))
    return result


T = TypeVar("T")


def async_to_sync(source: T) -> T:
    """Convert all public async methods/properties of an object to universal methods.

    See [`async_to_sync_wraps`][universalasync.wrapper.async_to_sync_wraps] for more info

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

        elif name == "__aenter__" and not hasattr(source, "__enter__"):
            source.__enter__ = async_to_sync_wraps(method)  # type: ignore

        elif name == "__aexit__" and not hasattr(source, "__exit__"):
            source.__exit__ = async_to_sync_wraps(method)  # type: ignore

    return source


wrap = async_to_sync
