from aioqiwi.wallet import enums

import datetime
import logging
import asyncio
import pytz

logger = logging.getLogger("qiwi_poller")


class QIWIHistoryPoll:
    # Код основан на https://github.com/uwinx/aioqiwi/blob/e5aa5ddd38369678cb48af7f1791fa3644e06103/aioqiwi/contrib/history_polling.py
    def __init__(self, client, waiting_time, limit, process_old_to_new=True, payment_type="IN"):
        self._client = client

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

    async def poll(self, left_date, right_date):
        history = await self._client.history(
            self.limit_per_request,
            operation=self.payment_type,
            sources=self.payment_sources,
            date_range=(left_date, right_date),
        )

        if not history.data:
            logger.debug("No new transaction found")
            return

        if self.process_old_to_new is True:
            history.data.reverse()  # reverse to (older -> newer)

        for payment in history.data:
            try:
                logger.debug(f"Processing {payment.txn_id} from {payment.date}")
                await self._client.handler_manager.process_event(payment)
            except StopIteration:  # handle exhausted iterator
                break

    async def run_polling(self):
        if self._client.handler_manager is None:
            raise ValueError("Wallet has to have handler manager")

        while True:
            # try:
                _left_time = datetime.datetime.now(pytz.timezone('Europe/Moscow'))

                logger.debug(f"Going to sleep {self.waiting_time}")
                await asyncio.sleep(self.waiting_time)

                _right_time = datetime.datetime.now(pytz.timezone('Europe/Moscow'))
                logger.debug("Checking new payments via QIWI history API....")
                await self.poll(_left_time, _right_time)

            # except Exception:
            #     pass
