from bot import dp, qiwi_poller, qiwi_wallet, loop, sim_service, yoomoney_poller, config, bot, smshub
from bot import handlers
from bot.utils.backup import backup_sender
from bot.models.onlinesim import Onlinesim

from aiogram import Dispatcher, executor
from aiogram import types

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

    for task in Onlinesim.all():
        country_list = await sim_service.countries_list()
        country_info = country_list.get(task.country_code)
        if not country_info:
            # pass
            print(f"Unknown country code: {task.country_code=}")
        else:
            task.update(country_code=country_info)

        print(f"Country list: {country_list.get('7')}")

        services_list = await sim_service.number_stats(7)
        service_info = services_list.get(task.service_code, {})
        service = service_info.get('service')
        if not service:
            print(f"Unknown service code: {task.service_code}")
        else:
            task.update(service_code=service)

    # print(await smshub._countries_list())

async def on_bot_shutdown(dp: Dispatcher):
    logger.info("Close sessions ...")
    await qiwi_wallet.close()
    await sim_service.shutdown()
    config.export_to_file("bot/user_data/config.toml")

# Start Telegram bot polling
executor.start_polling(dp, on_startup=on_bot_startup, on_shutdown=on_bot_shutdown)  # , skip_update=True
