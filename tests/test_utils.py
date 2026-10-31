import asyncio
import multiprocessing
import signal
import socket
import threading

import pytest

from universalasync import async_to_sync_wraps, get_event_loop, idle
from universalasync.utils import _reset_event_loop_after_fork

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


def test_idle_stops_on_signal():
    handlers = {s: signal.getsignal(s) for s in (signal.SIGINT, signal.SIGTERM, signal.SIGABRT)}
    loop = get_event_loop()
    loop.call_later(0.1, signal.raise_signal, signal.SIGTERM)
    timeout = loop.call_later(5, loop.stop)
    try:
        idle()
    finally:
        timeout.cancel()
        for s, handler in handlers.items():
            signal.signal(s, handler)


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


def test_reset_event_loop_after_fork():
    loop = get_event_loop()
    reader, writer = socket.socketpair()
    writer.setblocking(False)
    signal.set_wakeup_fd(writer.fileno())
    try:
        _reset_event_loop_after_fork()
        assert signal.set_wakeup_fd(-1) == -1
        assert get_event_loop() is not loop
    finally:
        signal.set_wakeup_fd(-1)
        reader.close()
        writer.close()
        loop.close()
