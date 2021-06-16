from datetime import datetime, timedelta
from collections import OrderedDict

from icecream import ic


class LRUDictCache(OrderedDict):

    def __init__(self, maxsize=1024, lifetime=3600, *args, **kwds):
        self.maxsize = maxsize
        self.lifetime = timedelta(seconds=lifetime)
        super().__init__(*args, **kwds)

    def __getitem__(self, key):
        ic("__getitem__ is called!")
        value, expiration = super().__getitem__(key)

        if datetime.utcnow() >= expiration:
            super().__delitem__(key)
            raise KeyError()

        self.move_to_end(key)
        return value

    def __setitem__(self, key, value):
        ic("__setitem__ is called!")
        if key in self:
            self.move_to_end(key)
        expiration = datetime.utcnow() + self.lifetime
        super().__setitem__(key, (value, expiration))
        if len(self) > self.maxsize:
            oldest = next(iter(self))
            del self[oldest]

    def __contains__(self, key):
        try:
            result = self.__getitem__(key)
        except Exception:
            return None
        else:
            return result

    def clear(self):
        super().clear()
