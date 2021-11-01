import asyncio
import datetime
import pytz
from contextlib import suppress
from loguru import logger

from .client import Client

from bot.events.payment import payment_event_handler
from bot.services import config
from bot.models.refills import RefillSource
from bot.utils.retry import retry_on_connection_issue


class YooMoneyHistoryPoll:
    def __init__(self, loop, bot, client: Client, waiting_time: int = 60):
        self.client = client
        self.waiting_time = waiting_time
        self.bot = bot
        self.loop = loop

    @retry_on_connection_issue()
    async def poll(self, left_date, right_date):
        history = await self.client.operation_history(type="deposition", from_date=left_date, till_date=right_date)

        if not history.operations:
            logger.info("No new transaction found")
            return

        for operation in history.operations:
            await self.process_payment(operation)

    async def run_polling(self):
        while True:
            _left_time = datetime.datetime.now(pytz.timezone('Europe/Moscow'))

            logger.info(f"Going to sleep {self.waiting_time}")
            await asyncio.sleep(self.waiting_time)

            _right_time = datetime.datetime.now(pytz.timezone('Europe/Moscow'))
            logger.info("Checking new payments via YooMoney history API....")
            self.loop.create_task(self.poll(_left_time, _right_time))

    async def process_payment(self, operation):
        if not operation.label or not operation.label.startswith(config.BOT_NAME) or not operation.label.replace(f"{config.BOT_NAME}-", "").isdigit():
            return
        # with suppress(Exception):
        user_id = operation.label.replace(f"{config.BOT_NAME}-", "")
        await payment_event_handler(user_id=user_id, txn_id=operation.operation_id, amount=operation.amount, source=RefillSource.YOOMONEY, extra=operation.json)
