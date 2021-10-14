import toml


class TomlConfig:
    ignore_attr = {"dict"}
    def __init__(self, dictionary: dict):
        self.dict = dictionary

    @classmethod
    def parse_from_file(cls, config_file_name: str):
        config = toml.load(config_file_name)
        return cls(config)

    @classmethod
    def parse_from_string(cls, toml_string: str):
        config = toml.loads(toml_string)
        return cls(config)

    def __getattr__(self, name):
        if name in self.ignore_attr:
            return self.__dict__[name]
        elif name in self.dict:
            return self.dict[name]
        else:
            raise AttributeError(f"No such attribute: {name}")

    def __setattr__(self, name, value):
        if name in self.ignore_attr:
            self.__dict__[name] = value
        else:
            self.dict[name] = value

    def __delattr__(self, name):
        if name in self.dict:
            del self.dict[name]
        else:
            raise AttributeError(f"No such attribute: {name}")

    def __getitem__(self, key):
        return getattr(self, key)

    def __setitem__(self, key, value):
        setattr(self, key, value)

    def __delitem__(self, key):
        delattr(self, key)

    def __iter__(self):
        yield from self.dict

    def __contains__(self, key):
        return self.dict.get(key)

    def get(self, key):
        return self.dict.get(key)

    def __repr__(self):
        return str(self.dict)

    def export_to_string(self):
        return toml.dumps(self.dict)

    def export_to_file(self, config_file_name: str):
        with open(config_file_name, "w") as config_file:
            toml.dump(self.dict, config_file)
