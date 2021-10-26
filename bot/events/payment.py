from bot.services import config
from bot.models.user import User
from bot.models.refills import Refill, RefillSource

from aiogram.utils.markdown import hlink
from aiogram import Bot, types

from loguru import logger
from contextlib import suppress

async def payment_event_handler(user_id: int, txn_id: int, amount: float, currency: int = 643, source: RefillSource = RefillSource.ADMIN, extra: dict = {}):

    bot = Bot.get_current()

    logger.debug(f"New {source.value} payment!")
    if Refill.where(txn_id=txn_id).first():
        logger.debug("Same payment is found, just ignore...")
        return

    if currency != 643:
        amount_rub = amount  # TODO: - Convert to RUB (?)
        # TODO: currency converter
        # TODO: Need table with ISO 4217 codes list for currency converting: 643 --> RUB
        # await currency_converter.convert(payment.sum.amount, from_currency)
    else:
        amount_rub = amount

    if amount_rub >= 1000 < 2000:
        percent = 5
    elif amount_rub >= 2000:
        percent = 10
    else:
        percent = 0

    amount_rub = (amount_rub * (percent / 100)) + amount_rub

    message_text = [
        f"[{source.value}] Воу-воу! {user_id} пополнил ваш кошелек на сумму {amount_rub}. Номер транзакции: {txn_id}"
    ]

    if User.where(user_id=user_id).first() is None:
        message_text.append(f"Баланс никому не зачислен, т.к. данного ID пользывателя нету в базе: {hlink(title=str(user_id), url=f'tg://user?id={user_id}')}")
    else:
        user = User.where(user_id=user_id).first()
        user.update(balance=user.balance + amount_rub)

        with suppress(Exception):
            await bot.send_message(chat_id=user_id, text=f"[{source.value}] Ваш баланс успешно пополнен на сумму {amount_rub}. Номер транзакции: {txn_id}")

        message_text.append(f"Баланс успешно зачислен ID пользывателю {hlink(title=str(user_id), url=f'tg://user?id={user_id}')}")

        Refill.create(user_id=user_id, txn_id=txn_id, amount=amount_rub, data=extra, source=source)

    with suppress(Exception):
        await bot.send_message(chat_id=config.ADMIN_ID, text='\n'.join(message_text), parse_mode=types.ParseMode.HTML)
