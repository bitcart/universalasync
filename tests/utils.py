from universalasync import wrap


@wrap
class SampleClass:
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
