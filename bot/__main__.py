from bot import dp, qiwi_poller, qiwi_wallet, loop, sim_service, currency_converter, yoomoney_poller

from bot.events import qiwi_payment
from bot.handlers import admin
from bot.handlers import client
from bot.handlers import error

from aiogram import Dispatcher, executor
from aiogram.types import BotCommand

import logging

logger = logging.getLogger(__name__)


async def on_bot_startup(dp: Dispatcher):
    # Регистрация /-команд в интерфейсе бота
    commands = [
        BotCommand(command="start", description="Открыть главное меню бота"),
    ]

    logger.info("Register bot commands ...")
    await dp.bot.set_my_commands(commands)

    logger.info("Start QIWI poller ...")
    loop.create_task(qiwi_poller.run_polling())
    logger.info("Start YooMoney poller ...")
    loop.create_task(yoomoney_poller.run_polling())


async def on_bot_shutdown(dp: Dispatcher):
    logger.info("Close sessions ...")
    await qiwi_wallet.close()
    await sim_service.shutdown()
    await currency_converter.shutdown()


# Start Telegram bot polling
executor.start_polling(dp, on_startup=on_bot_startup, on_shutdown=on_bot_shutdown)  # , skip_update=True
