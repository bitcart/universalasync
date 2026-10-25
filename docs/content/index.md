# universalasync

A library to help automate the creation of universal python libraries

## Overview

Have you ever been frustrated that you need to maintain both sync and async versions of your library, even though their code differs by just `async` and `await`?
You might have come up to rewriting your code before release or other unreliable solutions.

This library helps you to focus only on the main async implementation of your library: sync one will be created automatically.

Via decorating all your public methods, the wrapped functions automatically detect different conditions and run the functions accordingly.

If user uses your library in async context, minimal overhead is added, it just returns the coroutine right away.

Otherwise the library calls the coroutine via various loop methods, like as if you did it manually.

There should be no issues at all, the only limitation is that signals and async subprocesses are supported only when running in the main thread.

Also note that when run from a different OS thread, the library will create a new event loop there and run coroutines.

This means that resources bound to a certain event loop (like `aiohttp.ClientSession`) need one instance per event loop.

[`LoopLocal`][universalasync.loop_local.LoopLocal] keeps one value per event loop, and closes each of them on the loop that owns it: when you call `close()`, or when it is garbage collected.

```python
import aiohttp
from universalasync import LoopLocal, wrap


@wrap
class Client:
    def __init__(self):
        self._sessions = LoopLocal(aiohttp.ClientSession.close)

    async def help(self):
        async with self._sessions.get(aiohttp.ClientSession).get("https://example.com") as response:
            return await response.text()

    def close(self):  # await it in async code
        return self._sessions.close()
```

## Installation

/// tab | uv (Recommended)

```bash
uv add universalasync
```

///

/// tab | pip

```bash
pip install universalasync
```

///

## Example of usage

```python
# wrap needed methods one by one
class Client:
    @async_to_sync_wraps
    async def help():
        ...

    @async_to_sync_wraps
    @property
    async def async_property():
        ...

# or wrap whole classes
@wrap
class Client:
    async def help(self):
        ...

    @property
    async def async_property():
        ...

client = Client()

def sync_call():
    client.help()
    client.async_property

async def async_call():
    await client.help()
    await client.async_property

# works in all cases
sync_call()
asyncio.run(async_call())
threading.Thread(target=sync_call).start()
threading.Thread(target=asyncio.run, args=(async_call(),)).start()
```
