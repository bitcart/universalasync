import asyncio

from tests.utils import SampleClass


def sync_cm():
    with SampleClass() as obj:
        return obj


async def async_cm():
    async with SampleClass() as obj:
        return obj


def test_context_manager():
    assert isinstance(sync_cm(), SampleClass)
    assert isinstance(asyncio.run(async_cm()), SampleClass)
