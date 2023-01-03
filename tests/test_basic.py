import asyncio
import weakref

import pytest

from tests.utils import SampleClass
from universalasync import get_event_loop


def test_sync_works(client):
    assert client.async_method() is True
    assert client.async_method() is True  # ensure there are no loop mismatch error


def test_sync_works_with_properties(client):
    assert client.async_property is True  # property: special case


def test_proper_sync_cleanup(client):
    loop = get_event_loop()
    with pytest.raises(KeyboardInterrupt):
        client.async_interrupt()
    assert not loop.is_running()
    assert not asyncio.all_tasks(loop)


def test_proper_cleanup():
    client = SampleClass()
    client_ref = weakref.ref(client)

    async def func(client):
        await client.async_method()

    asyncio.run(func(client))
    del client
    assert client_ref() is None


def sync_cm():
    with SampleClass() as obj:
        return obj


async def async_cm():
    async with SampleClass() as obj:
        return obj


def check_context_manager(obj):
    assert isinstance(obj, SampleClass)
    assert not obj._session.is_running()


def test_context_manager():
    check_context_manager(sync_cm())
    check_context_manager(asyncio.run(async_cm()))
