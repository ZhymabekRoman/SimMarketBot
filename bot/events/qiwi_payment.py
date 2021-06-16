from bot import bot, qiwi_wallet, currency_converter
from bot.user_data import config
from bot.models.user import User
from bot.models.refills import Refill
from aioqiwi.wallet import types as aioqiwi_types


@qiwi_wallet.hm()
async def qiwi_payment_event_handler(payment: aioqiwi_types.PaymentData):

    if Refill.where(txn_id=payment.txn_id).first() is not None:
        return

    if payment.sum.currency != 643:
        amount_rub = float(payment.sum.amount)
    else:
        amount_rub = float(payment.sum.amount)  # TODO: - Convert to RUB (?)

        # TODO: currency converter
        # TODO: Need table with ISO 4217 codes list for currency converting: 643 --> RUB
        # await currency_converter.convert(payment.sum.amount, from_currency)

    message_text = [
        f"Воу-воу! {payment.account} пополнил ваш кошелек на сумму {amount_rub}. Номер транзакции: {payment.txn_id}"
    ]

    if payment.comment is None or not payment.comment.isdigit():
        message_text.append(f"Баланс никому не зачислен, т.к. коментарий не является ID пользователя: [{payment.comment}]")
    elif User.where(user_id=int(payment.comment)).first() is None:
        message_text.append(f"Баланс никому не зачислен, т.к. данного ID пользывателя нету в базе: [{payment.comment}]")
    else:
        user_id = int(payment.comment)

        if payment.status != "SUCCESS":
            message_text.append(f"ID пользыватель {user_id} найден в базе, но во время пополнения произошла ошибка.")
            bot.send_message(chat_id=user_id, text=f"Во время пополнения баланса произошла ошибка. Номер транзакции: {payment.txn_id}. Код ошибки: {payment.error_code}")
        else:
            user = User.where(user_id=int(payment.comment)).first()
            old_balance = user.balance
            user.update(balance=old_balance + amount_rub)

            bot.send_message(chat_id=user_id, text=f"Ваш баланс успешно пополнен на сумму {amount_rub}. Номер транзакции: {payment.txn_id}")
            message_text.append(f"Баланс успешно зачислен ID пользывателю: [{user_id}]")

        Refill.create(user_id=user_id, txn_id=payment.txn_id, amount=amount_rub, data=payment.json())

    await bot.send_message(chat_id=config.ADMIN_ID, text='\n'.join(message_text))
