import os

from bot.utils.config import TomlConfig


if os.path.isfile(os.path.join("bot", "user_data", "config.py")):
    # Convert old py config format to new toml format
    from bot.user_data import config as old_config

    new_config_dict = {}
    for attr in dir(old_config):
        if attr.startswith("__"):
            continue
        new_config_dict.update({attr: getattr(old_config, attr)})

    new_config = TomlConfig(new_config_dict)
    new_config.export_to_file(os.path.join("bot", "user_data", "config.toml"))
    del new_config
    os.remove(os.path.join("bot", "user_data", "config.py"))

config = TomlConfig.parse_from_file(os.path.join("bot", "user_data", "config.toml"))
