#!/usr/bin/env sh

if [ ! -d "bot/user_data" ]; then
  python3 init_configurations.py
fi

python3 -m bot
