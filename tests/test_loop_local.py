import asyncio
import contextlib
import gc
import sys
import threading
import weakref

import pytest

from universalasync import LoopLocal, get_event_loop


class LoopBoundResource:
    def __init__(self, loop=None):
        self.loop = loop or asyncio.get_running_loop()
        self.closed_on = None

    async def close(self):
        self.closed_on = asyncio.get_running_loop()
        if not self.loop.is_closed():
            await self.loop.create_task(asyncio.sleep(0))


async def close_resource(resource):
    await resource.close()


@pytest.fixture
def loops():
    loops = [asyncio.new_event_loop() for _ in range(2)]
    yield loops
    for loop in loops:
        loop.close()


async def get_resource(holder):
    return holder.get(LoopBoundResource)


def get_on(loop, holder):
    return loop.run_until_complete(get_resource(holder))


async def close_from_loop(holder):
    await holder.close()


async def wait_until(predicate):
    for _ in range(500):
        if predicate():
            return
        await asyncio.sleep(0.01)
    raise AssertionError("condition was not met")


async def wait_closed(resource):
    await wait_until(lambda: resource.closed_on is not None)


def test_one_value_per_loop(loops):
    holder = LoopLocal(close_resource)
    first = get_on(loops[0], holder)
    assert get_on(loops[0], holder) is first
    second = get_on(loops[1], holder)
    assert second is not first
    assert second.loop is loops[1]


def test_sync_close_closes_values_on_their_idle_loops(loops):
    holder = LoopLocal(close_resource)
    resources = [get_on(loop, holder) for loop in loops]
    holder.close()
    assert [resource.closed_on for resource in resources] == loops


def test_async_close_awaits_current_loop_value():
    holder = LoopLocal(close_resource)

    async def main():
        resource = holder.get(LoopBoundResource)
        await holder.close()
        assert resource.closed_on is asyncio.get_running_loop()

    asyncio.run(main())


def test_async_close_waits_for_values_on_idle_loops(loops):
    holder = LoopLocal(close_resource)
    resource = get_on(loops[0], holder)
    loops[1].run_until_complete(close_from_loop(holder))
    assert resource.closed_on is loops[0]


@contextlib.contextmanager
def running_in_thread(loop):
    thread = threading.Thread(target=loop.run_forever)
    thread.start()
    try:
        yield
    finally:
        loop.call_soon_threadsafe(loop.stop)
        thread.join()


def test_sync_close_value_on_loop_running_in_other_thread(loops):
    holder = LoopLocal(close_resource)
    with running_in_thread(loops[0]):
        resource = asyncio.run_coroutine_threadsafe(get_resource(holder), loops[0]).result(timeout=5)
        holder.close()
        asyncio.run_coroutine_threadsafe(wait_closed(resource), loops[0]).result(timeout=5)
    assert resource.closed_on is loops[0]


def test_async_close_waits_for_value_on_loop_running_in_other_thread(loops):
    holder = LoopLocal(close_resource)
    with running_in_thread(loops[0]):
        resource = asyncio.run_coroutine_threadsafe(get_resource(holder), loops[0]).result(timeout=5)
        loops[1].run_until_complete(close_from_loop(holder))
        assert resource.closed_on is loops[0]


def test_sync_close_value_on_closed_loop(loops):
    holder = LoopLocal(close_resource)
    resource = get_on(loops[0], holder)
    loops[0].close()
    holder.close()
    assert resource.closed_on is not None
    assert resource.closed_on is not loops[0]


def test_async_close_value_on_closed_loop(loops):
    holder = LoopLocal(close_resource)
    resource = get_on(loops[0], holder)
    loops[0].close()
    loops[1].run_until_complete(close_from_loop(holder))
    assert resource.closed_on is loops[1]


def test_garbage_collection_closes_values(loops):
    holder = LoopLocal(close_resource)
    resource = get_on(loops[0], holder)
    del holder
    gc.collect()
    assert resource.closed_on is loops[0]


def test_values_created_after_close_are_still_closed(loops):
    holder = LoopLocal(close_resource)
    get_on(loops[0], holder)
    holder.close()
    resource = get_on(loops[0], holder)
    assert resource.closed_on is None
    del holder
    gc.collect()
    assert resource.closed_on is loops[0]


def test_holder_does_not_keep_owner_alive(loops):
    class Owner:
        def __init__(self):
            self.values = LoopLocal(close_resource)

        def create(self):
            return LoopBoundResource()

    async def get(owner):
        return owner.values.get(owner.create)

    owner = Owner()
    resource = loops[0].run_until_complete(get(owner))
    owner_ref = weakref.ref(owner)
    del owner
    assert owner_ref() is None
    assert resource.closed_on is loops[0]


def collect_inside(loop, holders, predicate):
    async def collect():
        holders.clear()
        await wait_until(predicate)

    loop.run_until_complete(collect())


def test_garbage_collection_inside_other_loop_closes_values_on_idle_loops(loops):
    holders = [LoopLocal(close_resource)]
    resource = get_on(loops[0], holders[0])
    collect_inside(loops[1], holders, lambda: resource.closed_on is not None)
    assert resource.closed_on is loops[0]


def test_garbage_collection_inside_other_loop_closes_values_on_closed_loops(loops):
    holders = [LoopLocal(close_resource)]
    resource = get_on(loops[0], holders[0])
    loops[0].close()
    collect_inside(loops[1], holders, lambda: resource.closed_on is not None)
    assert resource.closed_on is loops[1]


async def failing_close(resource):
    raise ValueError("close failed")


def test_async_close_raises_close_errors(loops):
    holder = LoopLocal(failing_close)
    get_on(loops[0], holder)
    with pytest.raises(ValueError, match="close failed"):
        loops[1].run_until_complete(close_from_loop(holder))


def close_failing_on(failing_loop):
    async def close(resource):
        if resource.loop is failing_loop:
            raise ValueError("close failed")
        await resource.close()

    return close


def holder_failing_on(loops):
    holder = LoopLocal(close_failing_on(loops[1]))
    healthy = get_on(loops[0], holder)
    get_on(loops[1], holder)
    return holder, healthy


def test_sync_close_closes_every_value_when_one_fails(loops):
    holder, healthy = holder_failing_on(loops)
    with pytest.raises(ValueError, match="close failed"):
        holder.close()
    assert healthy.closed_on is loops[0]


def test_garbage_collection_closes_every_value_when_one_fails(loops, monkeypatch):
    errors = []
    monkeypatch.setattr(sys, "unraisablehook", lambda unraisable: errors.append(unraisable.exc_value))
    holder, healthy = holder_failing_on(loops)
    del holder
    gc.collect()
    assert healthy.closed_on is loops[0]
    assert isinstance(errors[0], ValueError)


async def slow_close(resource):
    await asyncio.sleep(0.05)
    await resource.close()


def test_async_close_waits_for_all_values_when_one_fails(loops):
    async def close(resource):
        if resource.loop is loops[0]:
            raise ValueError("close failed")
        await slow_close(resource)

    holder = LoopLocal(close)
    get_on(loops[0], holder)
    slow = get_on(loops[1], holder)
    with pytest.raises(ValueError, match="close failed"):
        loops[1].run_until_complete(close_from_loop(holder))
    assert slow.closed_on is loops[1]


def test_cancelled_async_close_still_closes_values(loops):
    holder = LoopLocal(slow_close)
    resource = get_on(loops[1], holder)

    async def cancel_close():
        task = asyncio.ensure_future(holder.close())
        await asyncio.sleep(0.01)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        await wait_closed(resource)

    loops[1].run_until_complete(cancel_close())
    assert resource.closed_on is loops[1]


def test_cancelled_value_close_is_not_raised():
    async def cancelled_close(resource):
        raise asyncio.CancelledError

    holder = LoopLocal(cancelled_close)

    async def main():
        holder.get(LoopBoundResource)
        await holder.close()

    asyncio.run(main())


def test_errors_after_cancelled_async_close_are_reported(loops):
    errors = []
    loops[1].set_exception_handler(lambda loop, context: errors.append(context["exception"]))

    async def slow_failing_close(resource):
        await asyncio.sleep(0.05)
        raise ValueError("close failed")

    holder = LoopLocal(slow_failing_close)
    get_on(loops[1], holder)

    async def cancel_close():
        task = asyncio.ensure_future(holder.close())
        await asyncio.sleep(0.01)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        await wait_until(lambda: errors)

    loops[1].run_until_complete(cancel_close())
    assert isinstance(errors[0], ValueError)


def test_values_of_closed_loops_are_closed_when_a_value_is_created(loops):
    holder = LoopLocal(close_resource)
    stale = get_on(loops[0], holder)
    loops[0].close()
    current = get_on(loops[1], holder)
    assert stale.closed_on is loops[1]
    assert list(holder._values.values()) == [current]


def test_errors_closing_values_of_closed_loops_are_reported(loops):
    errors = []
    loops[1].set_exception_handler(lambda loop, context: errors.append(context["exception"]))
    holder = LoopLocal(close_failing_on(loops[0]))
    get_on(loops[0], holder)
    loops[0].close()
    get_on(loops[1], holder)
    loops[1].run_until_complete(wait_until(lambda: errors))
    assert isinstance(errors[0], ValueError)


def test_errors_closing_values_of_closed_loops_are_reported_from_sync_code(loops):
    errors = []
    current_loop = get_event_loop()
    current_loop.set_exception_handler(lambda loop, context: errors.append(context["exception"]))
    try:
        holder = LoopLocal(close_failing_on(loops[0]))
        get_on(loops[0], holder)
        loops[0].close()
        holder.get(lambda: LoopBoundResource(current_loop))
        assert isinstance(errors[0], ValueError)
    finally:
        current_loop.set_exception_handler(None)


def test_garbage_collection_inside_other_loop_reports_errors_on_closed_loops(loops):
    errors = []
    loops[1].set_exception_handler(lambda loop, context: errors.append(context["exception"]))
    holders = [LoopLocal(failing_close)]
    get_on(loops[0], holders[0])
    loops[0].close()
    collect_inside(loops[1], holders, lambda: errors)
    assert isinstance(errors[0], ValueError)


def test_background_close_errors_are_reported_to_the_owner_loop(loops):
    errors = []
    loops[0].set_exception_handler(lambda loop, context: errors.append(context["exception"]))
    holders = [LoopLocal(failing_close)]
    get_on(loops[0], holders[0])
    collect_inside(loops[1], holders, lambda: errors)
    assert isinstance(errors[0], ValueError)


def test_close_errors_on_loop_running_in_other_thread_are_reported(loops):
    errors = []
    loops[0].set_exception_handler(lambda loop, context: errors.append(context["exception"]))
    holder = LoopLocal(failing_close)
    with running_in_thread(loops[0]):
        asyncio.run_coroutine_threadsafe(get_resource(holder), loops[0]).result(timeout=5)
        holder.close()
        asyncio.run_coroutine_threadsafe(wait_until(lambda: errors), loops[0]).result(timeout=5)
    assert isinstance(errors[0], ValueError)


def run_in_threads(target, count=16):
    barrier = threading.Barrier(count, timeout=5)
    errors = []

    def run():
        try:
            target(barrier)
        except Exception as e:
            errors.append(e)
            barrier.abort()

    threads = [threading.Thread(target=run) for _ in range(count)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert errors == []


def test_concurrent_gets_close_each_stale_value_once():
    created = []
    closed = []

    async def close(value):
        closed.append(value)

    def create():
        value = object()
        created.append(value)
        return value

    holder = LoopLocal(close)

    def use(barrier):
        for _ in range(100):
            holder.get(create)
            get_event_loop().close()
            barrier.wait()
            holder.get(create)
        get_event_loop().close()

    run_in_threads(use)
    holder.close()
    assert len(closed) == len({id(value) for value in closed}) == len(created)


def test_concurrent_closes_close_each_value_once():
    closed = []

    async def close(value):
        closed.append(value)

    holder = LoopLocal(close)

    def close_all(barrier):
        barrier.wait()
        holder.close()

    loops = [asyncio.new_event_loop() for _ in range(32)]
    try:
        for _ in range(20):
            closed.clear()
            values = [loop.run_until_complete(get_resource(holder)) for loop in loops]
            run_in_threads(close_all)
            assert sorted(map(id, closed)) == sorted(map(id, values))
    finally:
        for loop in loops:
            loop.close()
