from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.dispatcher import FSMContext
from aiogram.utils.callback_data import CallbackData
from aiogram.utils.markdown import hlink
from aiogram import types

from bot import bot, dp, sim_service
from bot.models.user import User
from bot.models.refills import Refill, RefillSource
from bot.models.onlinesim import Onlinesim, OnlinesimStatus
from bot.user_data import config
from bot.utils.qiwi import generate_qiwi_payment_form_link
from bot.utils.yoomoney import generate_yoomoney_payment_form_link
from bot.utils.timedelta import readable_timedelta
from bot.utils.sms_code import mark_sms_code

import os
import pytz
import datetime
import math
from requests.models import PreparedRequest

from icecream import ic

countries_cb = CallbackData("countries", "page")
country_services_cb = CallbackData("country_services", "page", "country_code")
service_cb = CallbackData("service", "country_code", "service_code")
buy_number_cb = CallbackData("buy_service_number", "country_code", "service_code", "price")
task_manager_cb = CallbackData("task_manager", "tzid")
cancel_task_cb = CallbackData("cancel_task", "tzid")
paymemt_method_cb = CallbackData("paymemt_method", "amount")
refill_balance_via_cb = CallbackData("refill_via", "amount", "method")
countries_page_navigation_cb = CallbackData("countries_page_navigation", "pages")
services_page_navigation_cb = CallbackData("services_page_navigation", "country_code" "pages")


class ReciveSMS(StatesGroup):
    waiting_country = State()
    waiting_service = State()


class PaymentMethod(StatesGroup):
    waiting_amount = State()
    waiting_method = State()


@dp.callback_query_handler(text="main")
async def main_menu_btn_message(call: types.CallbackQuery):
    await main_menu_message(call.message, "edit")
    await call.answer()


@dp.message_handler(commands=['start'])
async def main_menu_message(msg: types.Message, msg_type="answer"):
    if not User.where(user_id=msg.chat.id).first():
        bot_start_arguments = msg.get_args()
        reffer = None

        if bot_start_arguments and bot_start_arguments.isdigit():
            reffer = int(bot_start_arguments)

        if reffer and User.where(user_id=reffer).first():
            await bot.send_message(chat_id=reffer, text=f"По вашей реф. ссылке зарегистрировался {hlink(title=str(msg.chat.id), url=f'tg://user?id={msg.chat.id}')}!", parse_mode=types.ParseMode.HTML)

        User.create(user_id=msg.chat.id, reffer_id=reffer)

    keyboard = types.InlineKeyboardMarkup()
    sms_recieve_country_btn = types.InlineKeyboardButton("📲 Купить номер", callback_data=countries_cb.new(1))
    all_sms_operations_btn = types.InlineKeyboardButton("📫 Все СМС операции", callback_data="all_operations")
    partners_btn = types.InlineKeyboardButton("👥 Партнёрская программа", callback_data="partners")
    balance_btn = types.InlineKeyboardButton("💳 Баланс", callback_data="balance")
    information_btn = types.InlineKeyboardButton("ℹ️ Информация", callback_data="information")
    keyboard.row(sms_recieve_country_btn, balance_btn)
    keyboard.row(all_sms_operations_btn, partners_btn)
    keyboard.row(information_btn)

    message_text = [
        f"Привет, {msg.from_user.first_name}!",
        "При помощи этого бота ты можешь принимать сообщения на номера, который я дам, тем самым регистрироваться на разных сайтах и соц.сетях"
    ]
    if msg_type == "answer":
        await msg.answer_photo(types.InputFile(os.path.join("bot", "images", "main.jpg")), caption='\n'.join(message_text), reply_markup=keyboard)
    elif msg_type == "edit":
        await msg.edit_caption("\n".join(message_text), reply_markup=keyboard)


@dp.callback_query_handler(countries_page_navigation_cb.filter())
async def countries_page_navigation__message(call: types.CallbackQuery, callback_data: dict):
    pages = int(callback_data["pages"])

    keyboard_markup = types.InlineKeyboardMarkup(row_width=5)
    for page in range(pages):
        page_btn = types.InlineKeyboardButton(page + 1, callback_data=countries_cb.new(page + 1))
        keyboard_markup.insert(page_btn)
    await call.message.edit_caption("📖 Пожалуйста, выберите страницу", reply_markup=keyboard_markup)
    await call.answer()


@dp.callback_query_handler(countries_cb.filter())
async def sms_recieve_country_set_message(call: types.CallbackQuery, state: FSMContext, callback_data: dict):
    page = int(callback_data["page"])
    countries_list = await sim_service.countries_list()
    pages_number = math.ceil(float(len(countries_list)) / float(15))

    keyboard_markup = types.InlineKeyboardMarkup(row_width=3)
    for country_code, country_name in list(countries_list.items())[(page - 1) * 15: ((page - 1) * 15) + 15]:
        summary_numbers = await sim_service.summary_numbers_count(country_code)
        country_btn = types.InlineKeyboardButton(f"{country_name} ({summary_numbers})", callback_data=country_services_cb.new(1, country_code))
        keyboard_markup.insert(country_btn)

    plagination_keyboard_list = []

    if page > 1:
        previous_page_btn = types.InlineKeyboardButton("⬅️", callback_data=countries_cb.new(page - 1))
        plagination_keyboard_list.append(previous_page_btn)

    pages_number_btn = types.InlineKeyboardButton(f"Страница: {page} из {pages_number}", callback_data=countries_page_navigation_cb.new(pages_number))
    plagination_keyboard_list.append(pages_number_btn)

    if page < pages_number:
        next_page_btn = types.InlineKeyboardButton("➡️", callback_data=countries_cb.new(page + 1))
        plagination_keyboard_list.append(next_page_btn)

    keyboard_markup.row(*plagination_keyboard_list)

    back_btn = types.InlineKeyboardButton("Назад", callback_data="main")
    keyboard_markup.add(back_btn)

    await call.message.edit_caption("1. Выберете страну, номер телефона которой будет Вам выдан", reply_markup=keyboard_markup)
    await call.answer()


@dp.callback_query_handler(country_services_cb.filter())
async def country_services_message(call: types.CallbackQuery, callback_data: dict):
    page = int(callback_data["page"])
    country_code = callback_data["country_code"]
    services_list = await sim_service.number_stats(country_code)
    pages_number = math.ceil(float(len(services_list)) / float(15))

    countries_list = await sim_service.countries_list()
    country = countries_list.get(country_code)

    keyboard_markup = types.InlineKeyboardMarkup()
    for service_code, service in list(services_list.items())[(page - 1) * 15: ((page - 1) * 15) + 15]:
        service_btn = types.InlineKeyboardButton(f"{service['service']} ({service['count']})", callback_data=service_cb.new(country_code, service_code))
        keyboard_markup.insert(service_btn)

    plagination_keyboard_list = []

    if page > 1:
        previous_page_btn = types.InlineKeyboardButton("⬅️", callback_data=country_services_cb.new(page - 1, country_code))
        plagination_keyboard_list.append(previous_page_btn)

    pages_number_btn = types.InlineKeyboardButton(f"Страница: {page} из {pages_number}", callback_data=plagination_pages_cb.new("services", pages_number))
    plagination_keyboard_list.append(pages_number_btn)

    if page < pages_number:
        next_page_btn = types.InlineKeyboardButton("➡️", callback_data=country_services_cb.new(page + 1, country_code))
        plagination_keyboard_list.append(next_page_btn)

    keyboard_markup.row(*plagination_keyboard_list)

    back_btn = types.InlineKeyboardButton("Назад", callback_data=countries_cb.new(1))
    keyboard_markup.add(back_btn)

    await call.message.edit_caption(f"🌍 Выбранная страна: {country}\n2. Веберите сервис, от которого вам необходимо принять СМС", reply_markup=keyboard_markup)
    await call.answer()


@dp.callback_query_handler(service_cb.filter())
async def service_message(call: types.CallbackQuery, callback_data: dict):
    country_code = callback_data["country_code"]
    service_code = callback_data["service_code"]

    countries_list = await sim_service.countries_list()
    services_list = await sim_service.number_stats(country_code)

    service = services_list.get(service_code)
    country = countries_list.get(country_code)
    price = (service['price'] * (config.COMMISSION_AMOUNT / 100)) + service['price']

    message_text = [
        f"▫️ Выбранный сервис: {service.get('service')}",
        f"▫️ Выбранная страна: {country}",
        "",
        f"▫️ Цена: {price}₽",
        f"▫️ В наличии: {service.get('count')} номеров"
    ]

    keyboard_markup = types.InlineKeyboardMarkup()
    buy_btn = types.InlineKeyboardButton("Купить", callback_data=buy_number_cb.new(country_code, service_code, price))
    back_btn = types.InlineKeyboardButton("Назад", callback_data=country_services_cb.new(1, country_code))
    keyboard_markup.add(buy_btn)
    keyboard_markup.add(back_btn)

    await call.message.edit_caption("\n".join(message_text), reply_markup=keyboard_markup)
    await call.answer()


@dp.callback_query_handler(buy_number_cb.filter())
async def buy_service_number_message(call: types.CallbackQuery, callback_data: dict):
    country_code = callback_data["country_code"]
    service_code = callback_data["service_code"]
    service_price = float(callback_data["price"])

    user = User.where(user_id=call.message.chat.id).first()
    user_balance = user.balance

    if user_balance < service_price:
        await call.answer("У вас недостаточно средств для покупки", True)
        return

    status, tzid = await sim_service.getNum(service_code, country_code)

    if status == "NO_NUMBER":
        await call.answer("Упс, оказывается номера уже закончились", True)
        return
    elif status in ["WARNING_LOW_BALANCE"]:
        await call.answer("Извините, что-то пошло не так", True)
        await bot.send_message(chat_id=config.ADMIN_ID, text="ТРЕВОГА! У ВАС ПОЧТИ ЗАКОНЧИЛСЯ БАЛАНС В СЕРВИСЕ OnlineSim! СРОЧНО ПОПОЛНИТЕ!!!")
        return
    elif status != 1:
        await call.answer("Извините, что-то пошло не так", True)
        return

    try:
        service_status = await sim_service.getState(tzid)
    except Exception:
        await call.answer("Извините, что-то пошло не так", True)
        return
        raise

    Onlinesim.create(user_id=call.message.chat.id, tzid=tzid, service_code=service_code, country_code=country_code, price=service_price, number=service_status.get('number'))
    user.update(balance=user_balance - service_price)
    if user.reffer_id is not None:
        _referral_amount = 0.25
        Refill.create(user_id=user.reffer_id, source=RefillSource.REFERRAL, amount=_referral_amount)
        user.reffer.update(balance=user.reffer.balance + _referral_amount)

    await call.answer("Номер успешно заказан!")
    await task_manager_message(call, {"tzid": tzid})


@dp.callback_query_handler(text="all_operations")
async def all_operations_message(call: types.CallbackQuery, task_status: int = OnlinesimStatus.waiting):
    keyboard = types.InlineKeyboardMarkup()
    user_operations = Onlinesim.where(user_id=call.message.chat.id, status=task_status).all()
    active = Onlinesim.where(user_id=call.message.chat.id, status=OnlinesimStatus.waiting).all()
    finish = Onlinesim.where(user_id=call.message.chat.id, status=OnlinesimStatus.success).all()
    cancel = Onlinesim.where(user_id=call.message.chat.id, status=OnlinesimStatus.cancel).all()
    expire = Onlinesim.where(user_id=call.message.chat.id, status=OnlinesimStatus.expire).all()
    if not user_operations:
        no_tasks_btn = types.InlineKeyboardButton("👓 Нет заказов", callback_data="tester")
        keyboard.add(no_tasks_btn)
    else:
        for task in user_operations:
            countries_list = await sim_service.countries_list()
            services_list = await sim_service.number_stats(task.country_code)

            service = services_list.get(task.service_code)
            country = countries_list.get(task.country_code)

            task_btn = types.InlineKeyboardButton(f"{task.id} | {service['service']} | {country}", callback_data=task_manager_cb.new(task.tzid))
            keyboard.add(task_btn)

    active_tasks_btn = types.InlineKeyboardButton(f"♻️ активные ({len(active)})", callback_data="active_tasks")
    finished_tasks_btn = types.InlineKeyboardButton(f"✅ выполненные ({len(finish)})", callback_data="finished_tasks")
    canceled_tasks_btn = types.InlineKeyboardButton(f"❌ отмененные ({len(cancel)})", callback_data="canceled_tasks")
    expired_tasks_btn = types.InlineKeyboardButton(f"🕰 истекшие  ({len(expire)})", callback_data="expired_tasks")
    back_btn = types.InlineKeyboardButton("Назад", callback_data="main")
    keyboard.row(active_tasks_btn, finished_tasks_btn)
    keyboard.row(canceled_tasks_btn, expired_tasks_btn)
    keyboard.add(back_btn)

    if task_status == OnlinesimStatus.waiting:
        task_type_name = "♻️ Активные"
    elif task_status == OnlinesimStatus.success:
        task_type_name = "✅ Выполненные"
    elif task_status == OnlinesimStatus.cancel:
        task_type_name = "❌ Отмененные"
    elif task_status == OnlinesimStatus.expire:
        task_type_name = "🕰 Истекшие"

    message_text = f"{task_type_name} операции ({len(user_operations)}):"

    await call.message.edit_caption(message_text, reply_markup=keyboard)
    await call.answer()


@dp.callback_query_handler(task_manager_cb.filter())
async def task_manager_message(call: types.CallbackQuery, callback_data: dict):
    tzid = int(callback_data["tzid"])

    task = await sim_service.getState(tzid)
    task_info = Onlinesim.where(tzid=tzid).first()

    if not task_info:
        await call.answer("Извините, что-то пошло не так", True)
        return

    if task:
        msg_raw = []

        for _msg in task.get("msg", []):
            __received_msg = _msg.get("msg", "")
            msg_raw.append(__received_msg)

        time = task.get("time", 0)
        number = task.get('number')
        service_response = task.get("response")
    else:
        msg_raw = task_info.msg
        time = 0
        number = task_info.number
        service_response = None

    countries_list = await sim_service.countries_list()
    services_list = await sim_service.number_stats(task_info.country_code)

    service = services_list.get(task_info.service_code)
    country = countries_list.get(task_info.country_code)

    if task_info.status == OnlinesimStatus.waiting:
        status = "Активно"
    elif task_info.status == OnlinesimStatus.success:
        status = "Успешно"
    elif task_info.status == OnlinesimStatus.expire:
        status = "Истекло время ожидании"
    elif task_info.status == OnlinesimStatus.cancel:
        status = "Отменена"

    keyboard = types.InlineKeyboardMarkup()
    if task_info.status == OnlinesimStatus.waiting:
        if msg_raw:
            cancel_task_btn = types.InlineKeyboardButton("✅ Завершить операцию", callback_data=cancel_task_cb.new(tzid))
        else:
            cancel_task_btn = types.InlineKeyboardButton("📛 Отменить операцию", callback_data=cancel_task_cb.new(tzid))
        keyboard.add(cancel_task_btn)
        update_btn = types.InlineKeyboardButton("♻️ Обновить", callback_data=task_manager_cb.new(tzid))
        keyboard.add(update_btn)
    black_btn = types.InlineKeyboardButton("Назад", callback_data="active_tasks")
    keyboard.add(black_btn)

    expirity = readable_timedelta(datetime.timedelta(seconds=time))
    msg = '\n'.join(mark_sms_code(msg_raw))

    message_text = [
        f"▫️ ID опреации: {task_info.id}",
        f"▫️ Номер телефона: {number}",
        f"▫️ Страна: {country}",
        f"▫️ Сервис: {service.get('service')}",
        f"▫️ Цена: {task_info.price}₽",
        f"▫️ Время покупки: {task_info.created_at.astimezone(pytz.timezone('Europe/Moscow'))} (Московское время)",
        f"▫️ Длительность действия номера: {expirity}",
        f"▫️ Статуc: {status}",
        f"▫️ Сообщения ({len(msg_raw)}):",
        f"{msg}"
    ]

    try:
        await call.message.edit_caption('\n'.join(message_text), reply_markup=keyboard, parse_mode=types.ParseMode.HTML)
    except Exception:
        pass

    await call.answer()

    if task:
        task_info.update(msg=msg_raw)
        if service_response in ["TZ_OVER_EMPTY", "TZ_OVER_OK"]:
            await cancel_task_message(call, callback_data)
        else:
            await sim_service.setOperationRevise(tzid)
    else:
        if task_info.status == OnlinesimStatus.waiting:
            await cancel_task_message(call, callback_data)


@dp.callback_query_handler(cancel_task_cb.filter())
async def cancel_task_message(call: types.CallbackQuery, callback_data: dict):
    tzid = int(callback_data["tzid"])

    task = await sim_service.getState(tzid)
    task_info = Onlinesim.where(tzid=tzid).first()

    # if close_task_info.get("response") != "1":
    #     await call.answer("Извините, операцию нельзя завершить сейчас, попробуйте чуть позже", True)
    #     return

    if task:
        msg_raw = task.get("msg", [])
        service_response = task.get("response")
    else:
        msg_raw = task_info.msg
        service_response = None

    msg_raw = []

    if not msg:
        user = User.where(user_id=call.message.chat.id).first()
        user.update(balance=user.balance + task_info.price)
    else:
        for _msg in msg:
            __received_msg = _msg.get("msg", "")
            msg_raw.append(__received_msg)

    if service_response in ["TZ_OVER_OK", "TZ_NUM_ANSWER"]:
        _task_status = OnlinesimStatus.success
    elif service_response == "TZ_NUM_WAIT":
        _task_status = OnlinesimStatus.cancel
    elif service_response == "TZ_OVER_EMPTY":
        _task_status = OnlinesimStatus.expire
    else:
        ic(f"Unknown task status: {service_response}")
        _task_status = OnlinesimStatus.cancel

    task_info.update(msg=msg_raw, status=_task_status)

    close_task_info = await sim_service.setOperationOk(tzid)
    await task_manager_message(call, callback_data)
    # await call.answer("Задача успешно отменена")


@dp.callback_query_handler(text="balance", state='*')
async def balance_message(call: types.CallbackQuery, state: FSMContext):
    await state.finish()

    user_balance = User.where(user_id=call.message.chat.id).first().balance

    keyboard = types.InlineKeyboardMarkup()
    refill_history_btn = types.InlineKeyboardButton("История пополнения", callback_data="refill_history")
    refill_balance_btn = types.InlineKeyboardButton("Пополнить баланс", callback_data="refill_balance")
    back_btn = types.InlineKeyboardButton("Назад", callback_data="main")
    keyboard.add(refill_history_btn)
    keyboard.add(refill_balance_btn)
    keyboard.add(back_btn)
    message_text = [
        f"💲 Ваш баланс: **{user_balance} ₽**",
        f"🏷 Ваш id: `{call.message.chat.id}`",
        ""
    ]
    await call.message.edit_caption('\n'.join(message_text), reply_markup=keyboard, parse_mode=types.ParseMode.MARKDOWN)
    await call.answer()


@dp.callback_query_handler(text="refill_history")
async def refill_history_message(call: types.CallbackQuery):
    user = User.where(user_id=call.message.chat.id).first()
    user_refills = user.refills

    keyboard = types.InlineKeyboardMarkup()
    if not user_refills:
        no_refills_btn = types.InlineKeyboardButton("Вы не сделали ни одного пополнение баланса", callback_data="refill_balance")
        keyboard.add(no_refills_btn)
    else:
        for refill in user_refills:
            refill_btn = types.InlineKeyboardButton(f"{refill.source.name} | +{refill.amount}", callback_data="refill_manager")
            keyboard.add(refill_btn)
    back_btn = types.InlineKeyboardButton("Назад", callback_data="balance")
    keyboard.add(back_btn)
    message_text = [
        "История пополнения баланса",
        f"Общее количество пополнении: {len(user_refills)}"
    ]
    await call.message.edit_caption('\n'.join(message_text), reply_markup=keyboard)
    await call.answer()


@dp.callback_query_handler(text='refill_balance', state='*')
async def refill_balance_message(call: types.CallbackQuery):
    keyboard = types.InlineKeyboardMarkup(row_width=3)
    amounts_list = [50, 100, 250, 500, 1000, 5000]
    amount_btn_list = []

    for amount in amounts_list:
        amount_btn = types.InlineKeyboardButton(amount, callback_data=paymemt_method_cb.new(amount))
        amount_btn_list.append(amount_btn)

    message_text = [
        "Вы можете пополнить сумму ниже через кнопку, либо введите желаемую сумму:",
        "",
        "Пример: 100",
        "",
        "P.S.: Сейчас действует акция - При пополнении баланса бота от 1000 рублей +5% бонус. От 2000 рублей и более +10% Налетай пока не поздно!"
    ]

    back_btn = types.InlineKeyboardButton("Назад", callback_data="balance")
    keyboard.add(*amount_btn_list)
    keyboard.add(back_btn)
    await call.message.edit_caption('\n'.join(message_text), reply_markup=keyboard)
    await call.answer()
    await PaymentMethod.waiting_amount.set()


@dp.callback_query_handler(paymemt_method_cb.filter(), state=PaymentMethod.waiting_amount)
async def refill_balance_amount_callback(call: types.CallbackQuery, callback_data: dict, state: FSMContext):
    amount = callback_data.get("amount", 700)

    await state.update_data({"amount": amount})

    await refill_balance_method_message(call.message, state, "edit")
    await call.answer()


@dp.message_handler(state=PaymentMethod.waiting_amount, content_types=types.ContentTypes.TEXT)
async def refill_balance_amount_message(msg: types.Message, state: FSMContext):
    amount = msg.text

    if not amount.isdigit():
        keyboard = types.InlineKeyboardMarkup()
        back_btn = types.InlineKeyboardButton("Назад", callback_data="balance")
        keyboard.add(back_btn)
        await msg.answer_photo(types.InputFile(os.path.join("bot", "images", "main.jpg")), caption="Баланс пользывателя должен быть в цифрах", reply_markup=keyboard)
        return

    await state.update_data({"amount": amount})

    await refill_balance_method_message(msg, state, "answer")


@dp.message_handler(state=PaymentMethod.waiting_method, content_types=types.ContentTypes.TEXT)
async def refill_balance_method_message(msg: types.Message, state: FSMContext, msg_type: str = "answer"):
    user_data = await state.get_data()
    amount = user_data.get("amount", 700)

    keyboard = types.InlineKeyboardMarkup()
    qiwi_btn = types.InlineKeyboardButton("QIWI", callback_data=refill_balance_via_cb.new(amount=amount, method="qiwi"))
    yoomoney_btn = types.InlineKeyboardButton("YooMoney", callback_data=refill_balance_via_cb.new(amount=amount, method="yoomoney"))
    back_btn = types.InlineKeyboardButton("Назад", callback_data="refill_balance")
    keyboard.add(qiwi_btn)
    keyboard.add(yoomoney_btn)
    keyboard.add(back_btn)
    message_text = [
        f"Текущая сумма пополнения: {amount}",
        "",
        "Выберите один из способов пополнения",
        f"Если они вам по какой-то причине не подходят, то вы можете написать админу: {config.ADMIN_USERNAME}"
    ]
    if msg_type == "edit":
        await msg.edit_caption('\n'.join(message_text), reply_markup=keyboard)
    elif msg_type == "answer":
        await msg.answer_photo(types.InputFile(os.path.join("bot", "images", "main.jpg")), caption='\n'.join(message_text), reply_markup=keyboard)

    await PaymentMethod.waiting_method.set()


@dp.callback_query_handler(refill_balance_via_cb.filter(method=["qiwi"]), state=PaymentMethod.waiting_method)
async def refill_balance_via_qiwi_message(call: types.CallbackQuery, callback_data: dict, state: FSMContext):
    amount = int(callback_data.get("amount", 700))

    qiwi_payment_comment = f"ActiVision-{call.message.chat.id}"
    qiwi_payment_link = generate_qiwi_payment_form_link("99", config.QIWI_WALLET, amount, qiwi_payment_comment, 643, ["account", "comment"], 0)

    keyboard = types.InlineKeyboardMarkup()
    payement_qiwi_btn = types.InlineKeyboardButton("Перейти к оплате", qiwi_payment_link)
    back_btn = types.InlineKeyboardButton("Назад", callback_data="refill_balance")
    keyboard.add(payement_qiwi_btn)
    keyboard.add(back_btn)
    message_text = [
        "💲 Пополнение баланса через QIWI 💲",
        "",
        "▫️ Для пополнения баланса переведите нужную сумму на",
        f"▫️ Qiwi кошелек: `{config.QIWI_WALLET}`",
        "❗️ В комментарии платежа ОБЯЗАТЕЛЬНО укажите:",
        f'`{qiwi_payment_comment}`',
        "▫️ Деньги зачисляться автоматически в течении 1 минут",
        "▫️ Вы получите уведомление в боте"
    ]
    await call.message.edit_caption('\n'.join(message_text), parse_mode=types.ParseMode.MARKDOWN, reply_markup=keyboard)
    await call.answer()

    await state.finish()


@dp.callback_query_handler(refill_balance_via_cb.filter(method=["yoomoney"]), state=PaymentMethod.waiting_method)
async def refill_balance_via_yoomoney_message(call: types.CallbackQuery, callback_data: dict, state: FSMContext):
    amount = int(callback_data.get("amount", 700))

    yoomoney_payment_label = f"ActiVision-{call.message.chat.id}"
    yoomoney_payment_link = generate_yoomoney_payment_form_link(config.YOOMONEY_RECEIVER, "Пополнение баланс бота ActiVision", yoomoney_payment_label, amount)

    keyboard = types.InlineKeyboardMarkup()
    payement_yoomoney_btn = types.InlineKeyboardButton("Перейти к оплате", yoomoney_payment_link)
    back_btn = types.InlineKeyboardButton("Назад", callback_data="refill_balance")
    keyboard.add(payement_yoomoney_btn)
    keyboard.add(back_btn)
    message_text = [
        "💲 Пополнение баланса через YooMoney 💲",
        "",
        "▫️ Деньги зачисляться автоматически в течении 1 минут",
        "▫️ Вы получите уведомление в боте"
    ]
    await call.message.edit_caption('\n'.join(message_text), parse_mode=types.ParseMode.MARKDOWN, reply_markup=keyboard)
    await call.answer()

    await state.finish()


@dp.callback_query_handler(text="partners")
async def check_referrals(call: types.CallbackQuery):
    referrals = User.where(user_id=call.message.chat.id).first().refferals
    referrals_refils = Refill.where(user_id=call.message.chat.id, source=RefillSource.REFERRAL).all()

    referrals_balance = 0.0
    for referral in referrals_refils:
        referrals_balance += referral.amount

    bot_username = (await call.bot.me).username
    bot_link = f"https://t.me/{bot_username}?start={call.message.chat.id}"
    _frwd_telegram_url = "https://t.me/share/url"
    _frwd_telegram_params = {"url": bot_link, "text": "ActiVision - сервис для приёма SMS сообщений"}
    _frwd_telegram_req = PreparedRequest()
    _frwd_telegram_req.prepare_url(_frwd_telegram_url, _frwd_telegram_params)
    forward_url = _frwd_telegram_req.url

    keyboard = types.InlineKeyboardMarkup()
    forward_link_btn = types.InlineKeyboardButton("Поделиться ссылкой", forward_url)
    back_btn = types.InlineKeyboardButton("Назад", callback_data="main")
    keyboard.add(forward_link_btn)
    keyboard.add(back_btn)
    message_text = [
        "👥 Партнёрская программа 👥",
        "➖➖➖➖➖➖➖➖➖➖",
        "▫️ В нашем боте действует одноуровневая партнёрская программа с оплатой за каждый купленный рефералом номер. В будущем планируем добавить до 3 уровней партнерской программы",
        "",
        f"▫️ 1 уровень - 0.25₽ за номер: {len(referrals)} партнёров принесли {referrals_balance}₽",
        "",
        "🔗 Ваша партнёрская ссылка:",
        bot_link
    ]

    await call.message.edit_caption('\n'.join(message_text), reply_markup=keyboard)
    await call.answer()


@dp.callback_query_handler(text="information")
async def information_message(call: types.CallbackQuery):
    keyboard = types.InlineKeyboardMarkup()
    tech_support_btn = types.InlineKeyboardButton("👨‍💻 Техподдержка / Администратор", "https://t.me/SanjarDS")
    news_btn = types.InlineKeyboardButton("📢 Новости", "https://t.me/ActiVisioNews")
    back_btn = types.InlineKeyboardButton("Назад", callback_data="main")
    keyboard.add(tech_support_btn)
    keyboard.add(news_btn)
    keyboard.add(back_btn)
    message_text = [
        "ActiVision - уникальный сервис для приёма SMS сообщений",
        "",
        "Наши преимущества:",
        "✔️ Низкие цены",
        "✔️ Полная автоматизация",
        "✔️ Быстрота и удобство",
        "✔️ Разнообразие сервисов и стран",
        "✔️ Партнёрская программа",
        "✔️ Постоянные обновления",
        "✔️ Отзывчивая поддержка"
    ]
    await call.message.edit_caption('\n'.join(message_text), reply_markup=keyboard)
    await call.answer()


@dp.callback_query_handler()
async def callback_handler(call: types.CallbackQuery):
    answer_data = call.data
    if answer_data == "balance_btn":
        await balance_message(call.message, "edit")
        await call.answer()
    elif answer_data == 'active_tasks':
        await all_operations_message(call, OnlinesimStatus.waiting)
        await call.answer()
    elif answer_data == 'finished_tasks':
        await all_operations_message(call, OnlinesimStatus.success)
        await call.answer()
    elif answer_data == 'canceled_tasks':
        await all_operations_message(call, OnlinesimStatus.cancel)
        await call.answer()
    elif answer_data == 'expired_tasks':
        await all_operations_message(call, OnlinesimStatus.expire)
        await call.answer()
    else:
        await call.answer("Функция не реализована", True)
