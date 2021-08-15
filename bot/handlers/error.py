from aiogram.utils.exceptions import BotBlocked, MessageNotModified
from aiogram import types

from bot import dp

# from icecream import ic

# @dp.errors_handler(exception=BotBlocked)
# async def error_bot_blocked(update: types.Update, exception: BotBlocked):
#     return True

@dp.errors_handler(exception=MessageNotModified)
async def message_not_modified_handler(update: types.Update, exception: BotBlocked):
    return True
