import asyncio
import inspect
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


@wrap
class SampleCallable:
    async def __call__(self, value):
        return value


def test_async_call_is_wrapped():
    assert SampleCallable()(1) == 1

    async def main():
        assert await SampleCallable()(1) == 1

    asyncio.run(main())


def test_sync_call_is_kept():
    @wrap
    class Sample:
        def __call__(self):
            return 1

    assert not hasattr(Sample.__call__, "__wrapped__")
    assert Sample()() == 1


@wrap
class SampleClassMethods:
    @classmethod
    async def create(cls, value):
        return cls, value

    @staticmethod
    async def static(value):
        return value

    @classmethod
    def sync_create(cls):
        return cls

    @staticmethod
    def sync_static():
        return True

    @classmethod
    async def gen(cls):
        yield cls


class SampleClassMethodsChild(SampleClassMethods):
    pass


@pytest.mark.parametrize(
    "owner", [SampleClassMethods, SampleClassMethods(), SampleClassMethodsChild, SampleClassMethodsChild()]
)
def test_classmethods_and_staticmethods_are_wrapped(owner):
    expected = owner if isinstance(owner, type) else type(owner)
    assert owner.create(1) == (expected, 1)
    assert owner.static(1) == 1
    assert owner.sync_create() is expected
    assert owner.sync_static() is True
    assert list(owner.gen()) == [expected]

    async def main():
        assert await owner.create(1) == (expected, 1)
        assert await owner.static(1) == 1
        assert [value async for value in owner.gen()] == [expected]

    asyncio.run(main())


def test_wrapping_classmethods_directly():
    class Sample:
        @async_to_sync_wraps
        @classmethod
        async def create(cls):
            return cls

        @async_to_sync_wraps
        @staticmethod
        async def static():
            return True

    assert Sample.create() is Sample
    assert Sample().create() is Sample
    assert Sample.static() is True
    assert Sample().static() is True


def test_subclass_members_need_own_wrap():
    @wrap
    class Base:
        async def method(self):
            return "base"

    class Unwrapped(Base):
        async def method(self):
            return "child"

    @wrap
    class Wrapped(Base):
        async def method(self):
            return "child"

        @classmethod
        async def create(cls):
            return cls

        async def __call__(self):
            return "called"

    class Inherited(Base):
        pass

    coroutine = Unwrapped().method()
    assert inspect.iscoroutine(coroutine)
    coroutine.close()
    assert Wrapped().method() == "child"
    assert Wrapped.create() is Wrapped
    assert Wrapped()() == "called"
    assert Inherited().method() == "base"


def test_wrapping_instance_keeps_working():
    class Sample:
        @classmethod
        async def create(cls):
            return cls

    sample = wrap(Sample())
    assert sample.create() is Sample


@async_to_sync_wraps
async def current_thread():
    return threading.current_thread()


def test_sync_works_when_loop_is_running_in_other_thread(client):
    with running_in_thread(get_event_loop()):
        assert client.async_method() is True
        assert client.async_property is True
        assert current_thread() is not threading.current_thread()
