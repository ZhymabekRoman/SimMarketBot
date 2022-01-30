from bot import dp, qiwi_poller, qiwi_wallet, loop, sim_service, yoomoney_poller, config, bot
from bot import handlers
from bot.utils.backup import backup_sender

from aiogram import Dispatcher, executor
from aiogram import types

from loguru import logger
import asyncio
import random
import json


async def poll_manager():
    logger.info("Start QIWI poller ...")
    await asyncio.sleep(random.randint(10, 60))
    loop.create_task(qiwi_poller.run_polling())

    logger.info("Start YooMoney poller ...")
    await asyncio.sleep(random.randint(10, 60))
    loop.create_task(yoomoney_poller.run_polling())

    logger.info("Start OnlineSim cache updater service ...")
    await asyncio.sleep(random.randint(10, 60))
    loop.create_task(sim_service.cache_updater())

async def backup_sender_while(user_id: int, waiting_time: int = 3600):
    while True:
        await asyncio.sleep(waiting_time)
        await backup_sender(bot, user_id)

async def on_bot_startup(dp: Dispatcher):
    # Регистрация /-команд в интерфейсе бота
    commands = [
        types.BotCommand(command="start", description="Открыть главное меню бота"),
    ]

    logger.info("Register bot commands ...")
    await dp.bot.set_my_commands(commands)

    loop.create_task(poll_manager())

    loop.create_task(backup_sender_while(config.ADMIN_ID))

    await bot.send_message(chat_id=config.ADMIN_ID, text="Бот включен")


    """
    with open("robaa.txt", "w") as file:
        json.dump(await sim_service._countries_list(), file, sort_keys=True, indent=4)
    with open("hobaa.txt", "w") as file:
        json.dump(await sim_service._numbers_status(0), file, sort_keys=True, indent=4)
    """

async def on_bot_shutdown(dp: Dispatcher):
    logger.info("Close sessions ...")
    await qiwi_wallet.close()
    await sim_service.shutdown()
    await bot.send_message(chat_id=config.ADMIN_ID, text="Бот выключен")
    config.export_to_file("bot/user_data/config.toml")

# Start Telegram bot polling
executor.start_polling(dp, on_startup=on_bot_startup, on_shutdown=on_bot_shutdown)  # , skip_update=True
