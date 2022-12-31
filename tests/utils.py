from universalasync import get_event_loop, wrap


class SampleSession:
    def __init__(self):
        self.running = True

    async def close(self):
        self.running = False

    def is_running(self):
        return self.running


@wrap
class SampleClass:
    def __init__(self):
        self._session = SampleSession()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        await self._close()

    def sync_method(self):
        return True

    async def async_method(self):
        return True

    @property
    def sync_property(self):
        return True

    @property
    async def async_property(self):
        return True

    async def async_gen(self):
        for i in range(10):
            yield i

    async def async_interrupt(self):
        raise KeyboardInterrupt()

    async def _close(self):
        if self._session is not None:
            await self._session.close()

    def __del__(self):
        loop = get_event_loop()
        if loop.is_running():
            loop.create_task(self._close())
        else:
            loop.run_until_complete(self._close())
