import inspect
import multiprocessing
import os
import signal
import time
from threading import Thread

import pytest

from tests.utils import SampleClass
from universalasync import get_event_loop, idle

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
    t = Thread(target=run, args=(async_work(client, called),), daemon=True)
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
    t = Thread(target=run, args=(async_work(client, called),), daemon=True)
    t.start()
    await idle()
    t.join()


def run(coro):
    loop = get_event_loop()
    try:
        loop.run_until_complete(coro)
    finally:
        loop.close()


def sync_work(client, called):
    client.sync_method()
    called.value = client.async_method() is True


async def async_work(client, called):
    client.sync_method()
    called.value = await client.async_method() is True


base_src = inspect.getsource(run) + "\n" + inspect.getsource(sync_work) + "\n" + inspect.getsource(async_work)


# NOTE: we use exec here because there is no easy way to test completely different execution models in one test run
# this way we achieve isolation


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
    src = inspect.getsource(globals()[func])
    call_code = f"{func}(obj, called)"
    if func.startswith("async_"):
        call_code = f"run({call_code})"
    full_src = f"{base_src}\n{src}\nobj = SampleClass()\n{call_code}"
    called = multiprocessing.Value("b", False)
    global_vars = {
        "SampleClass": SampleClass,
        "Thread": Thread,
        "idle": idle,
        "get_event_loop": get_event_loop,
        "called": called,
    }

    def inner():
        exec(full_src, global_vars)

    process = multiprocessing.Process(target=inner)
    process.start()
    total = 0
    while not global_vars["called"].value:
        time.sleep(0.1)
        total += 0.1
        if total >= MAXSECONDS:
            break
    os.kill(process.pid, signal.SIGINT)
    process.join()
    assert global_vars["called"].value
