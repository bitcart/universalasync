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
