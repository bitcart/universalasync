import asyncio
from collections.abc import Callable, Coroutine
from typing import Any

from universalasync import async_to_sync_wraps


async def async_func() -> None:
    pass


@async_to_sync_wraps
async def wrapped_async_func() -> None:
    pass


def run_coroutine(coroutine: Coroutine) -> Any:
    try:
        coroutine.send(None)
    except StopIteration as e:
        return e.value
    raise RuntimeError("coroutine was expected to finish without suspending")


def benchmark_in_running_loop(benchmark: Any, function: Callable) -> None:
    async def main() -> None:
        benchmark(function)

    asyncio.run(main())


def test_sync_manual_run_until_complete(benchmark: Any) -> None:
    benchmark.group = "sync context"
    loop = asyncio.new_event_loop()
    try:
        benchmark(lambda: loop.run_until_complete(async_func()))
    finally:
        loop.close()


def test_sync_wrapped(benchmark: Any) -> None:
    benchmark.group = "sync context"
    benchmark(wrapped_async_func)


def test_sync_asyncio_run(benchmark: Any) -> None:
    benchmark.group = "sync context"
    benchmark(lambda: asyncio.run(async_func()))


def test_async_plain(benchmark: Any) -> None:
    benchmark.group = "async context"
    benchmark_in_running_loop(benchmark, lambda: run_coroutine(async_func()))


def test_async_wrapped(benchmark: Any) -> None:
    benchmark.group = "async context"
    benchmark_in_running_loop(benchmark, lambda: run_coroutine(wrapped_async_func()))
