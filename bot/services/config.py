import os

from bot.utils.config import TomlConfig

config = TomlConfig.parse_from_file(os.path.join("bot", "user_data", "config.toml"))
