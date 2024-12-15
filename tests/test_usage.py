import asyncio
import multiprocessing
import os
import signal
import time
import types
from threading import Thread

import pytest

from tests.utils import SampleClass
from universalasync import idle

MAXSECONDS = 5


# single threaded
# synchronous main thread style
def sync_(client, called):
    sync_work(client, called)


# multi threaded
# synchronous main thread + synchronous thread style
def sync_sync(client, called):
    t = Thread(target=sync_work, args=(client, called), daemon=True)
    t.start()
    idle()
    t.join()


# multi threaded
# synchronous main thread + asynchronous thread style
def sync_async(client, called):
    t = Thread(target=asyncio.run, args=(async_work(client, called),), daemon=True)
    t.start()
    idle()
    t.join()


# single threaded
# asynchronous main thread style
async def async_(client, called):
    await async_work(client, called)


# multi threaded
# asynchronous main thread + synchronous thread style
async def async_sync(client, called):
    t = Thread(target=sync_work, args=(client, called), daemon=True)
    t.start()
    await idle()
    t.join()


# multi threaded
# asynchronous main thread + asynchronous thread style
async def async_async(client, called):
    t = Thread(target=asyncio.run, args=(async_work(client, called),), daemon=True)
    t.start()
    await idle()
    t.join()


def sync_work(client, called):
    client.sync_method()
    called.value = client.async_method() is True and isinstance(client.async_gen(), types.GeneratorType)


async def async_work(client, called):
    client.sync_method()
    called.value = await client.async_method() is True and isinstance(client.async_gen(), types.AsyncGeneratorType)


def run_in_process(func, called):
    obj = SampleClass()
    result = globals()[func](obj, called)
    if func.startswith("async_"):
        result = asyncio.run(result)
    return result


@pytest.mark.parametrize(
    "func",
    [
        "sync_",
        "sync_sync",
        "sync_async",
        "async_",
        "async_sync",
        "async_async",
    ],
)
def test_async_to_sync_usage(func):
    called = multiprocessing.Value("b", False)

    process = multiprocessing.Process(target=run_in_process, args=(func, called))
    process.start()
    total = 0
    while not called.value:
        time.sleep(0.1)
        total += 0.1
        if total >= MAXSECONDS:
            break
    os.kill(process.pid, signal.SIGINT)
    process.join()
    assert called.value
