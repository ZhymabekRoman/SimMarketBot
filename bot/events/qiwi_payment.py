from bot import bot, qiwi_wallet
from bot.services import config
from bot.models.user import User
from bot.models.refills import Refill, RefillSource

from aioqiwi.wallet import types as aioqiwi_types
from aiogram.utils.markdown import hlink
from aiogram import types

from loguru import logger


@qiwi_wallet.hm()
async def qiwi_payment_event_handler(payment: aioqiwi_types.PaymentData):

    logger.debug("New QIWI payment!")
    if Refill.where(txn_id=payment.txn_id).first():
        logger.debug("Same payment is found, just ignore...")
        return

    if payment.sum.currency == 643:
        amount_rub = float(payment.sum.amount)
    else:
        amount_rub = float(payment.sum.amount)  # TODO: - Convert to RUB (?)

        # TODO: currency converter
        # TODO: Need table with ISO 4217 codes list for currency converting: 643 --> RUB
        # await currency_converter.convert(payment.sum.amount, from_currency)

    if amount_rub >= 1000 < 2000:
        percent = 5
    elif amount_rub >= 2000:
        percent = 10
    else:
        percent = 0

    amount_rub = (amount_rub * (percent / 100)) + amount_rub

    message_text = [
        f"[QIWI] Воу-воу! {payment.account} пополнил ваш кошелек на сумму {amount_rub}. Номер транзакции: {payment.txn_id}"
    ]

    if not payment.comment or not payment.comment.startswith("ActiVision-") or not payment.comment.replace("ActiVision-", "").isdigit():
        return

    user_id = int(payment.comment.replace("ActiVision-", ""))

    if User.where(user_id=user_id).first() is None:
        message_text.append(f"Баланс никому не зачислен, т.к. данного ID пользывателя нету в базе: [{payment.comment.replace('ActiVision-', '')}]")
    else:
        if payment.status != "SUCCESS":
            message_text.append(f"ID пользыватель {hlink(title=str(user_id), url=f'tg://user?id={user_id}')} найден в базе, но во время пополнения произошла ошибка.")
            try:
                await bot.send_message(chat_id=user_id, text=f"Во время пополнения баланса произошла ошибка. Номер транзакции: {payment.txn_id}. Код ошибки: {payment.error_code}")
            except Exception:
                pass
        else:
            user = User.where(user_id=user_id).first()
            old_balance = user.balance
            user.update(balance=old_balance + amount_rub)

            try:
                await bot.send_message(chat_id=user_id, text=f"Ваш баланс успешно пополнен на сумму {amount_rub}. Номер транзакции: {payment.txn_id}")
            except Exception:
                pass
            message_text.append(f"Баланс успешно зачислен ID пользывателю {hlink(title=str(user_id), url=f'tg://user?id={user_id}')}")

        Refill.create(user_id=user_id, txn_id=payment.txn_id, amount=amount_rub, data=payment.json(), source=RefillSource.QIWI)

    await bot.send_message(chat_id=config.ADMIN_ID, text='\n'.join(message_text), parse_mode=types.ParseMode.HTML)
