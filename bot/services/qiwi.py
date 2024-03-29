from aioqiwi.wallet import enums
from contextlib import suppress
import datetime
from loguru import logger
import asyncio
import pytz

from bot.events.payment import payment_event_handler
from bot.models.refills import RefillSource
from bot.utils.retry import retry_on_connection_issue
from bot.services import config


class QIWIHistoryPoll:
    # Код основан на https://github.com/uwinx/aioqiwi/blob/e5aa5ddd38369678cb48af7f1791fa3644e06103/aioqiwi/contrib/history_polling.py
    def __init__(self, loop, client, waiting_time, limit, process_old_to_new=True, payment_type="IN"):
        self._client = client
        self.loop = loop
        self.waiting_time = waiting_time
        self.limit_per_request = limit

        self.payment_sources = [
            enums.PaymentSources.CARD,
            enums.PaymentSources.MK,
            enums.PaymentSources.QW_EUR,
            enums.PaymentSources.QW_RUB,
            enums.PaymentSources.QW_USD,
        ]

        if payment_type == "ALL":
            self.payment_type = enums.PaymentTypes.ALL
        elif payment_type == "IN":
            self.payment_type = enums.PaymentTypes.IN
        elif payment_type == "OUT":
            self.payment_type = enums.PaymentTypes.OUT
        else:
            raise ValueError("Not correct payment_type value.")

        self.process_old_to_new = process_old_to_new

    @retry_on_connection_issue()
    async def poll(self, left_date, right_date):
        history = await self._client.history(
            self.limit_per_request,
            operation=self.payment_type,
            sources=self.payment_sources,
            date_range=(left_date, right_date),
        )

        if not history.data:
            # logger.info("No new transaction found")
            return

        if self.process_old_to_new is True:
            history.data.reverse()  # reverse to (older -> newer)

        for payment in history.data:
            try:
                logger.debug(f"Processing {payment.txn_id} from {payment.date}")
                await self.process_payment(payment)
            except StopIteration:  # handle exhausted iterator
                break

    async def run_polling(self):
        if self._client.handler_manager is None:
            raise ValueError("Wallet has to have handler manager")

        while True:
            _left_time = datetime.datetime.now(pytz.timezone('Europe/Moscow'))

            # logger.info(f"Going to sleep {self.waiting_time}")
            await asyncio.sleep(self.waiting_time)

            _right_time = datetime.datetime.now(pytz.timezone('Europe/Moscow'))
            # logger.info("Checking new payments via QIWI history API....")
            self.loop.create_task(self.poll(_left_time, _right_time))

    async def process_payment(self, payment):
        if not payment.comment or not payment.comment.startswith(config.BOT_NAME) or not payment.comment.replace(f"{config.BOT_NAME}-", "").isdigit():
            return
        # with suppress(Exception):
        user_id = payment.comment.replace(f"{config.BOT_NAME}-", "")
        await payment_event_handler(user_id=user_id, txn_id=payment.txn_id, amount=payment.sum.amount, currency=payment.sum.currency, source=RefillSource.QIWI, extra=payment.json())
