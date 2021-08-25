import asyncio
import datetime
import logging
import pytz

from .client import Client

from aiogram import types
from aiogram.utils.markdown import hlink

from bot.user_data import config
from bot.models.user import User
from bot.models.refills import Refill, RefillSource

logger = logging.getLogger("yoomoney-poller")


class YooMoneyHistoryPoll:
    def __init__(self, loop, bot, client: Client, waiting_time: int = 60):
        self.client = client
        self.waiting_time = waiting_time
        self.bot = bot
        self.loop = loop

    async def poll(self, left_date, right_date):
        history = await self.client.operation_history(from_date=left_date, till_date=right_date)

        if not history.operations:
            logger.debug("No new transaction found")
            return

        for operation in history.operations:
            if Refill.where(txn_id=operation.operation_id).first():
                continue

            amount_rub = operation.amount

            message_text = [
                f"[YooMoney] Воу-воу! кто-то пополнил ваш кошелек на сумму {amount_rub}. Номер транзакции: {operation.operation_id}"
            ]

            if not operation.label or not operation.label.startswith("ActiVision-") or not operation.label.replace("ActiVision-", "").isdigit():
                continue

            user_id = int(operation.label.replace("ActiVision-", ""))

            if User.where(user_id=user_id).first() is None:
                message_text.append(f"Баланс никому не зачислен, т.к. данного ID пользывателя нету в базе: [{operation.label.replace('ActiVision-', '')}]")
            else:
                user = User.where(user_id=user_id).first()
                old_balance = user.balance
                user.update(balance=old_balance + amount_rub)

                try:
                    await self.bot.send_message(chat_id=user_id, text=f"Ваш баланс успешно пополнен на сумму {amount_rub}. Номер транзакции: {operation.operation_id}")
                except Exception:
                    pass
                message_text.append(f"Баланс успешно зачислен ID пользывателю {hlink(title=str(user_id), url=f'tg://user?id={user_id}')}")

                Refill.create(user_id=user_id, txn_id=operation.operation_id, amount=amount_rub, data={}, source=RefillSource.YOOMONEY)

            await self.bot.send_message(chat_id=config.ADMIN_ID, text='\n'.join(message_text), parse_mode=types.ParseMode.HTML)

    async def run_polling(self):
        while True:
            _left_time = datetime.datetime.now(pytz.timezone('Europe/Moscow'))

            logger.debug(f"Going to sleep {self.waiting_time}")
            await asyncio.sleep(self.waiting_time)

            _right_time = datetime.datetime.now(pytz.timezone('Europe/Moscow'))
            logger.debug("Checking new payments via YooMoney history API....")
            self.loop.create_task(self.poll(_left_time, _right_time))
