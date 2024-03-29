.. universalasync documentation master file, created by
   sphinx-quickstart on Sun Dec 19 21:37:48 2021.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to universalasync's documentation!
==========================================

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   api


A library to help automate the creation of universal python libraries

Overview
========

Have you ever been frustrated that you need to maintain both sync and async versions of your library, even thought their code differs by just async and await?
You might have came up to rewriting your code before release or other unreliable solutions.

This library helps you to focus only on the main async implementation of your library: sync one will be created automatically

Via decorating all your public methods, the wrapped functions automatically detect different conditions and run the functions accordingly.

If user uses your library in async context, minimal overhead is added, it just returns the coroutine right away.

Otherwise the library calls the coroutine via various loop methods, like as if you did it manually.

There should be no issues at all, the only limitation is that signals and async subprocesses are supported only when running in the main thread.

Also note that when run from a different os thread, the library will create a new event loop there and run coroutines.

This means that you might need to adapt your code a bit in case you use some resources bound to a certain event loop (like ``aiohttp.ClientSession``).

You can see an example of how this could be solved `here <https://github.com/bitcart/bitcart-sdk/blob/4a425f80f62a0c90f8c5fa19ccb7e578590dcead/bitcart/providers/jsonrpcrequests.py#L51-L58>`_

Installation
============

``pip install universalasync``

.. _example:

Example of usage
================


.. code-block:: python

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
