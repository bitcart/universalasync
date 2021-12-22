from types import AsyncGeneratorType, GeneratorType

from universalasync import get_event_loop


def test_asyncgen(client):
    assert type(client.async_gen()) == GeneratorType
    assert list(client.async_gen()) == list(range(10))

    async def async_part():
        assert type(client.async_gen()) == AsyncGeneratorType
        assert [i async for i in client.async_gen()] == list(range(10))

    loop = get_event_loop()
    loop.run_until_complete(async_part())
