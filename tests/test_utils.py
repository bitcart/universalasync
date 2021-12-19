import asyncio
import multiprocessing
import threading
import time

from universalasync import get_event_loop, idle

MAXSECONDS = 1


def test_get_event_loop():
    def inner():
        loop = get_event_loop()
        assert isinstance(loop, asyncio.AbstractEventLoop)

    thread = threading.Thread(target=inner)
    thread.start()
    thread.join()
    loop = get_event_loop()
    assert isinstance(loop, asyncio.AbstractEventLoop)
    loop.close()
    loop2 = get_event_loop()
    assert loop is not loop2


def test_idle():
    def inner(called):
        idle()
        called.value = True

    called = multiprocessing.Value("b", False)
    process = multiprocessing.Process(target=inner, args=(called,))
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
