import os
import json


class JSONCacher(dict):
    """
    JSON file cache implementation
    """
    __slots__ = "cache_storage", "storage_file"

    def __init__(self, storage_file: str):
        self.storage_file = storage_file

        if os.path.isfile(storage_file):
            with open(storage_file, "r") as file:
                self.cache_storage = json.load(file)
        else:
            self.cache_storage = {}

    def __getitem__(self, key):
        return self.cache_storage[key]

    def __setitem__(self, key, value):
        self.cache_storage[key] = value

    def __delitem__(self, key):
        self.cache_storage.pop(key)

    def __iter__(self):
        for key, value in self.cache_storage.items():
            yield key

    def __contains__(self, key):
        return self.cache_storage.get(key, None)

    def get(self, key, default = None):
        return self.cache_storage.get(key, default)

    def shutdown(self):
        with open(self.storage_file, "w") as file:
            json.dump(self.cache_storage, file)

    def __repr__(self):
        return "JSONCacher(storage_file={storage_file}, cache_storage={cache_storage})".format(storage_file=self.storage_file, cache_storage=self.cache_storage)
