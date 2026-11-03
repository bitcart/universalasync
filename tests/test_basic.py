import asyncio
import threading
import types
import weakref

import pytest

from tests.utils import SampleClass, running_in_thread
from universalasync import async_to_sync_wraps, get_event_loop, wrap


def test_sync_works(client):
    assert client.async_method() is True
    assert client.async_method() is True  # ensure there are no loop mismatch error


def test_sync_works_with_properties(client):
    assert client.async_property is True  # property: special case


def test_sync_properties_are_kept(client):
    assert client.sync_property is True
    client.value = 1
    assert client.value == 1


def test_properties_keep_metadata():
    @wrap
    class Sample:
        @property
        async def value(self):
            """Value docs"""
            return True

    assert Sample.value.__doc__ == "Value docs"
    assert Sample.value.fget.__name__ == "value"
    assert Sample().value is True


class SettableDescriptor:
    def __set_name__(self, owner, name):
        self.name = f"_{name}"

    def __get__(self, instance, owner=None):
        if instance is None:
            return self
        return getattr(instance, self.name)

    def __set__(self, instance, value):
        setattr(instance, self.name, value)

    def __delete__(self, instance):
        delattr(instance, self.name)


@wrap
class SampleSlots:
    __slots__ = ("value",)

    def __init__(self):
        self.value = 0


@wrap
class SampleDescriptors:
    value = SettableDescriptor()

    def __init__(self):
        self.value = 0


@pytest.mark.parametrize(
    ("cls", "descriptor_type"), [(SampleSlots, types.MemberDescriptorType), (SampleDescriptors, SettableDescriptor)]
)
def test_data_descriptors_are_kept(cls, descriptor_type):
    assert type(cls.value) is descriptor_type
    obj = cls()
    assert obj.value == 0
    obj.value = 1
    assert obj.value == 1
    del obj.value
    assert not hasattr(obj, "value")


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


@async_to_sync_wraps
async def current_thread():
    return threading.current_thread()


def test_sync_works_when_loop_is_running_in_other_thread(client):
    with running_in_thread(get_event_loop()):
        assert client.async_method() is True
        assert client.async_property is True
        assert current_thread() is not threading.current_thread()
