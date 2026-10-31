import asyncio
import multiprocessing
import threading
import time

import pytest

from universalasync import async_to_sync_wraps, get_event_loop, idle

MAXSECONDS = 1


def check_in_thread():
    loop = get_event_loop()
    assert isinstance(loop, asyncio.AbstractEventLoop)


def test_get_event_loop():
    thread = threading.Thread(target=check_in_thread)
    thread.start()
    thread.join()
    loop = get_event_loop()
    assert isinstance(loop, asyncio.AbstractEventLoop)
    loop.close()
    loop2 = get_event_loop()
    assert loop is not loop2


def idle_checker(called):
    idle()
    called.value = True


def test_idle():
    called = multiprocessing.Value("b", False)
    process = multiprocessing.Process(target=idle_checker, args=(called,))
    process.start()
    total = 0
    while not called.value:
        time.sleep(0.1)
        total += 0.1
        if total >= MAXSECONDS:
            break
    process.terminate()
    process.join()
    assert called.value


@async_to_sync_wraps
async def run_in_executor():
    return await asyncio.get_running_loop().run_in_executor(None, int, "1")


def check_forked_child(parent_loop, result):
    result.value = get_event_loop() is not parent_loop and run_in_executor() == 1


@pytest.mark.skipif("fork" not in multiprocessing.get_all_start_methods(), reason="fork is not available")
def test_forked_child_gets_new_event_loop():
    parent_loop = get_event_loop()
    result = multiprocessing.Value("b", False)
    process = multiprocessing.get_context("fork").Process(target=check_forked_child, args=(parent_loop, result))
    process.start()
    process.join(MAXSECONDS)
    process.kill()
    process.join()
    assert result.value
