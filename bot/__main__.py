from bot import dp, qiwi_poller, qiwi_wallet, loop, sim_service, yoomoney_poller, config, bot
from bot import handlers
from bot.events import qiwi_payment

from aiogram import Dispatcher, executor
from aiogram.types import BotCommand, InputFile

from loguru import logger
import asyncio
import random


async def poll_manager():
    logger.info("Start QIWI poller ...")
    await asyncio.sleep(random.randint(10, 60))
    loop.create_task(qiwi_poller.run_polling())

    logger.info("Start YooMoney poller ...")
    await asyncio.sleep(random.randint(10, 60))
    loop.create_task(yoomoney_poller.run_polling())

    await asyncio.sleep(random.randint(10, 60))
    loop.create_task(sim_service.cache_updater())


async def on_bot_startup(dp: Dispatcher):
    # Регистрация /-команд в интерфейсе бота
    commands = [
        BotCommand(command="start", description="Открыть главное меню бота"),
    ]

    logger.info("Register bot commands ...")
    await dp.bot.set_my_commands(commands)

    loop.create_task(poll_manager())

    if not config.get("BOARD_IMAGE_FILE_ID"):
        image_msg = await bot.send_photo(config.ADMIN_ID, InputFile("images/board_image.jpg"))
        file_id = image_msg.photo[-1].file_id
        config.BOARD_IMAGE_FILE_ID = file_id


async def on_bot_shutdown(dp: Dispatcher):
    logger.info("Close sessions ...")
    await qiwi_wallet.close()
    await sim_service.shutdown()
    config.export_to_file("bot/user_data/config.toml")

# Start Telegram bot polling
executor.start_polling(dp, on_startup=on_bot_startup, on_shutdown=on_bot_shutdown)  # , skip_update=True
