from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.dispatcher import FSMContext
from aiogram.utils.callback_data import CallbackData
from aiogram.utils.deep_linking import get_start_link
from aiogram.utils.markdown import hlink
from aiogram import types
from aiogram.utils import exceptions

from bot import bot, dp, sim_service
from bot.models.user import User
from bot.models.refills import Refill, RefillSource
from bot.models.onlinesim import Onlinesim, OnlinesimStatus
from bot.services import config
from bot.utils.qiwi import generate_qiwi_payment_form_link
from bot.utils.yoomoney import generate_yoomoney_payment_form_link
from bot.utils.timedelta import readable_timedelta
from bot.utils.sms_code import mark_sms_code
from bot.utils.utils import is_digit
from bot.utils.referral import reward_referrals
from bot.utils.country2flag import Country2Flag

import pytz
import datetime
import math
import asyncio
from loguru import logger
from requests.models import PreparedRequest
from contextlib import suppress

countries_cb = CallbackData("countries", "page")
country_services_cb = CallbackData("country_services", "page", "country_code", "operator")
country_operator_cb = CallbackData("country_operator", "country_code")
service_cb = CallbackData("service", "country_code", "operator", "service_code")
buy_number_cb = CallbackData("buy_service_number", "country_code", "service_code", "operator", "price")
task_manager_cb = CallbackData("task_manager", "tzid")
cancel_task_cb = CallbackData("cancel_task", "tzid")
paymemt_method_cb = CallbackData("paymemt_method", "amount")
refill_balance_via_cb = CallbackData("refill_via", "amount", "method")
countries_page_navigation_cb = CallbackData("countries_page_navigation", "pages")
services_page_navigation_cb = CallbackData("services_page_navigation", "country_code", "pages")
service_search_cb = CallbackData("service_search", "country_code", "operator")
all_operation_cb = CallbackData("all_operation", "page", "status")

LOW_ELEMENTS_ON_PAGE = 9
MAX_ELEMENTS_ON_PAGE = 15

country2flag = Country2Flag()

class PaymentMethod(StatesGroup):
    waiting_amount = State()
    waiting_method = State()


class Search(StatesGroup):
    waiting_service_search_text = State()
    waiting_country_search_text = State()


@dp.callback_query_handler(text="main")
async def main_menu_btn_message(call: types.CallbackQuery):
    with suppress(exceptions.MessageNotModified):
        await main_menu_message(call.message, "edit")
    await call.answer()


@dp.message_handler(commands=['start'])
async def main_menu_message(msg: types.Message, msg_type="answer"):
    if not User.where(user_id=msg.chat.id).first():
        bot_start_arguments = msg.get_args()
        reffer = None

        if bot_start_arguments and bot_start_arguments.isdigit():
            reffer = int(bot_start_arguments)

        User.create(user_id=msg.chat.id, reffer_id=reffer)

        if reffer and User.where(user_id=reffer).first():
            await bot.send_message(chat_id=reffer, text=f"По вашей реф. ссылке зарегистрировался {hlink(title=str(msg.chat.id), url=f'tg://user?id={msg.chat.id}')}!", parse_mode=types.ParseMode.HTML)
            await reward_referrals(User.where(user_id=msg.chat.id).first())

    keyboard = types.InlineKeyboardMarkup()
    sms_recieve_country_btn = types.InlineKeyboardButton("📲 Купить номер", callback_data=countries_cb.new(1))
    all_sms_operations_btn = types.InlineKeyboardButton("📫 Все СМС операции", callback_data=all_operation_cb.new(1, OnlinesimStatus.waiting.value))
    partners_btn = types.InlineKeyboardButton("👥 Партнёрская программа", callback_data="partners")
    balance_btn = types.InlineKeyboardButton("💳 Баланс", callback_data="balance")
    information_btn = types.InlineKeyboardButton("ℹ️ Информация", callback_data="information")
    keyboard.row(sms_recieve_country_btn, balance_btn)
    keyboard.row(all_sms_operations_btn, partners_btn)
    keyboard.row(information_btn)

    message_text = [
        f"Привет, {msg.chat.full_name}!",
        "При помощи этого бота ты можешь принимать сообщения на номера, который я дам, тем самым регистрироваться на разных сайтах и соц.сетях"
    ]
    if msg_type == "answer":
        await msg.answer_photo(config.BOARD_IMAGE_FILE_ID, caption='\n'.join(message_text), reply_markup=keyboard)
    elif msg_type == "edit":
        await msg.edit_caption("\n".join(message_text), reply_markup=keyboard)


@dp.callback_query_handler(countries_page_navigation_cb.filter())
async def countries_page_navigation__message(call: types.CallbackQuery, callback_data: dict):
    pages = int(callback_data["pages"])

    keyboard_markup = types.InlineKeyboardMarkup(row_width=5)
    for page in range(pages):
        page_btn = types.InlineKeyboardButton(page + 1, callback_data=countries_cb.new(page + 1))
        keyboard_markup.insert(page_btn)

    back_btn = types.InlineKeyboardButton("Назад", callback_data=countries_cb.new(1))
    keyboard_markup.add(back_btn)

    await call.message.edit_caption("📖 Пожалуйста, выберите страницу", reply_markup=keyboard_markup)
    await call.answer()


@dp.callback_query_handler(text="country_search")
async def country_search_message(call: types.CallbackQuery, state: FSMContext):
    keyboard_markup = types.InlineKeyboardMarkup()
    back_btn = types.InlineKeyboardButton("Назад", callback_data=countries_cb.new(1))
    keyboard_markup.add(back_btn)

    await call.message.edit_caption("🔍 Введите название страны для поиска в оригинальном названии без транслита. Например: Россия", reply_markup=keyboard_markup)
    await Search.waiting_country_search_text.set()
    await call.answer()


@dp.message_handler(state=Search.waiting_country_search_text)
async def country_search_result_message(msg: types.Message, state: FSMContext):
    search_text = msg.text

    search_results = await sim_service.fuzzy_countries_search(search_text)

    keyboard_markup = types.InlineKeyboardMarkup()

    for search_result in search_results[:15]:
        result_btn = types.InlineKeyboardButton(f"{country2flag.get(search_result[0])} {search_result[0]} ({search_result[1]}%)", callback_data=country_operator_cb.new(country_code=search_result[2]))
        keyboard_markup.add(result_btn)

    back_btn = types.InlineKeyboardButton("Назад", callback_data=countries_cb.new(page=1))
    keyboard_markup.add(back_btn)

    await msg.answer_photo(config.BOARD_IMAGE_FILE_ID, caption=f"🔍 Результаты поиска ({len(search_results)}):", reply_markup=keyboard_markup)

    await state.finish()


@dp.callback_query_handler(countries_cb.filter(), state="*")
async def sms_recieve_country_set_message(call: types.CallbackQuery, state: FSMContext, callback_data: dict):
    await state.finish()

    page = int(callback_data["page"])
    countries_list = await sim_service._countries_list()
    if countries_list:
        pages_number = math.ceil(float(len(countries_list)) / float(MAX_ELEMENTS_ON_PAGE))
    else:
        pages_number = 1
    page_index = page - 1
    page_index_start_position = page_index * MAX_ELEMENTS_ON_PAGE
    page_index_end_position = page_index_start_position + MAX_ELEMENTS_ON_PAGE

    keyboard_markup = types.InlineKeyboardMarkup(row_width=3)
    for country in countries_list[page_index_start_position : page_index_end_position]:
        # summary_numbers = await sim_service.summary_numbers_count(country_code)
        # country_btn = types.InlineKeyboardButton(f"{country.get('name', 'Unknown')} ({summary_numbers})", callback_data=country_operator_cb.new(country.get('id')))
        country_flag = country2flag.get(country.get("name"))
        country_btn = types.InlineKeyboardButton(f"{country_flag} {country.get('name', 'Unknown')}", callback_data=country_operator_cb.new(country.get('id')))
        keyboard_markup.insert(country_btn)

    search_btn = types.InlineKeyboardButton("🔍 Поиск", callback_data="country_search")
    keyboard_markup.add(search_btn)

    plagination_keyboard_list = []

    if page > 1:
        previous_page_btn = types.InlineKeyboardButton("⬅️", callback_data=countries_cb.new(page - 1))
        plagination_keyboard_list.append(previous_page_btn)

    pages_number_btn = types.InlineKeyboardButton(f"📖 Страница: {page} из {pages_number}", callback_data=countries_page_navigation_cb.new(pages_number))
    plagination_keyboard_list.append(pages_number_btn)

    if page < pages_number:
        next_page_btn = types.InlineKeyboardButton("➡️", callback_data=countries_cb.new(page + 1))
        plagination_keyboard_list.append(next_page_btn)

    keyboard_markup.row(*plagination_keyboard_list)

    back_btn = types.InlineKeyboardButton("Назад", callback_data="main")
    keyboard_markup.add(back_btn)

    await call.message.edit_caption("1. Выберете страну, номер телефона которой будет Вам выдан", reply_markup=keyboard_markup)
    await call.answer()


@dp.callback_query_handler(country_operator_cb.filter(), state='*')
async def country_operator_message(call: types.CallbackQuery, callback_data: dict, state: FSMContext):
    country_code = callback_data["country_code"]
    countries_list = await sim_service._countries_list()

    for _country in countries_list:
        if country_code == _country.get("id"):
            country = _country
            break
    else:
        await call.answer("Извините, что-то пошло не так. Код ошибки: x847392", True)
        return

    country_operators_list = country.get("operators")

    if len(country_operators_list) == 1 and "any" in country_operators_list:
        await country_services_message(call, {"page": 1, "country_code": country_code, "operator": "any"}, state)
        return

    keyboard_markup = types.InlineKeyboardMarkup()
    all_operators_btn = types.InlineKeyboardButton("Все", callback_data=country_services_cb.new(page=1, country_code=country_code, operator="any"))
    keyboard_markup.insert(all_operators_btn)
    for operator in country_operators_list:
        if operator == "any":
            continue
        operator_btn = types.InlineKeyboardButton(operator.capitalize(), callback_data=country_services_cb.new(page=1, country_code=country_code, operator=operator))
        keyboard_markup.insert(operator_btn)

    back_btn = types.InlineKeyboardButton("Назад", callback_data=countries_cb.new(1))
    keyboard_markup.add(back_btn)

    message_text = [
            f"🌍 Выбранная страна: {country2flag.get(country.get('name'))} {country.get('name', 'Unknown')}",
            "",
            "2. Веберите оператора номера",
    ]

    await call.message.edit_caption("\n".join(message_text), reply_markup=keyboard_markup)
    await call.answer()


@dp.callback_query_handler(country_services_cb.filter(), state='*')
async def country_services_message(call: types.CallbackQuery, callback_data: dict, state: FSMContext):
    await state.finish()

    page = int(callback_data["page"])
    page_index = page - 1
    page_index_start_position = page_index * MAX_ELEMENTS_ON_PAGE
    page_index_end_position = page_index_start_position + MAX_ELEMENTS_ON_PAGE

    country_code = callback_data["country_code"]
    operator = callback_data["operator"]
    services_list = await sim_service._numbers_status(country_code, operator)
    if services_list:
        pages_number = math.ceil(float(len(services_list)) / float(MAX_ELEMENTS_ON_PAGE))
    else:
        pages_number = 1

    countries_list = await sim_service._countries_list()
    services_list_names = await sim_service._services_list()

    for _country in countries_list:
        if country_code == _country.get("id"):
            country = _country
            break
    else:
        await call.answer("Извините, что-то пошло не так. Код ошибки: x847392", True)
        return

    country_operators_list = country.get("operators")

    keyboard_markup = types.InlineKeyboardMarkup()
    for service_code, service in list(services_list.items())[page_index_start_position : page_index_end_position]:
        service_name = services_list_names.get(service_code, "Unknown")
        # service_btn = types.InlineKeyboardButton(f"{service_name} ({service['quantityForMaxPrice']})", callback_data=service_cb.new(country_code, operator, service_code))
        service_btn = types.InlineKeyboardButton(f"{service_name}", callback_data=service_cb.new(country_code, operator, service_code))
        keyboard_markup.insert(service_btn)

    search_btn = types.InlineKeyboardButton("🔍 Поиск", callback_data=service_search_cb.new(country_code, operator))
    keyboard_markup.add(search_btn)

    plagination_keyboard_list = []

    if page > 1:
        previous_page_btn = types.InlineKeyboardButton("⬅️", callback_data=country_services_cb.new(page - 1, country_code, operator))
        plagination_keyboard_list.append(previous_page_btn)

    pages_number_btn = types.InlineKeyboardButton(f"📖 Страница: {page} из {pages_number}", callback_data=services_page_navigation_cb.new(country_code, pages_number))
    plagination_keyboard_list.append(pages_number_btn)

    if page < pages_number:
        next_page_btn = types.InlineKeyboardButton("➡️", callback_data=country_services_cb.new(page + 1, country_code, operator))
        plagination_keyboard_list.append(next_page_btn)

    keyboard_markup.row(*plagination_keyboard_list)

    if len(country_operators_list) == 1 and "any" in country_operators_list:
        back_btn = types.InlineKeyboardButton("Назад", callback_data=countries_cb.new(1))
    else:
        back_btn = types.InlineKeyboardButton("Назад", callback_data=country_operator_cb.new(country_code))

    keyboard_markup.add(back_btn)

    message_text = [
            f"🌍 Выбранная страна: {country2flag.get(country.get('name'))} {country.get('name', 'Unknown')}",
            f"📱 Выбранный оператор: {operator.capitalize() if operator != 'any' else 'Все'}",
            "",
            "3. Веберите сервис, от которого вам необходимо принять СМС"
    ]

    await call.message.edit_caption("\n".join(message_text), reply_markup=keyboard_markup)
    await call.answer()


@dp.callback_query_handler(services_page_navigation_cb.filter())
async def services_page_navigation_message(call: types.CallbackQuery, callback_data: dict):
    pages = int(callback_data["pages"])
    country_code = callback_data["country_code"]

    keyboard_markup = types.InlineKeyboardMarkup(row_width=5)
    for page in range(pages):
        page_btn = types.InlineKeyboardButton(page + 1, callback_data=country_services_cb.new(page + 1, country_code))
        keyboard_markup.insert(page_btn)

    back_btn = types.InlineKeyboardButton("Назад", callback_data=country_services_cb.new(1, country_code))
    keyboard_markup.add(back_btn)

    await call.message.edit_caption("📖 Пожалуйста, выберите страницу", reply_markup=keyboard_markup)
    await call.answer()


@dp.callback_query_handler(service_search_cb.filter())
async def service_search_message(call: types.CallbackQuery, callback_data: dict, state: FSMContext):
    country_code = int(callback_data["country_code"])
    operator = callback_data["operator"]

    keyboard_markup = types.InlineKeyboardMarkup()
    back_btn = types.InlineKeyboardButton("Назад", callback_data=country_services_cb.new(1, country_code, operator))
    keyboard_markup.add(back_btn)

    await call.message.edit_caption("🔍 Введите название сервиса для поиска в оригинальном названии без транслита. Например: telegram", reply_markup=keyboard_markup)
    await Search.waiting_service_search_text.set()
    await state.update_data({"country_code": country_code, "operator": operator})
    await call.answer()


@dp.message_handler(state=Search.waiting_service_search_text)
async def service_search_result_message(msg: types.Message, state: FSMContext):
    search_text = msg.text

    user_data = await state.get_data()
    country_code = user_data["country_code"]
    operator = user_data["operator"]

    search_results = await sim_service.fuzzy_services_search(country_code, operator, search_text)

    keyboard_markup = types.InlineKeyboardMarkup()

    for search_result in search_results[:15]:
        result_btn = types.InlineKeyboardButton(f"{search_result[0]} ({search_result[1]}%)", callback_data=service_cb.new(country_code, operator, search_result[2]))
        keyboard_markup.add(result_btn)

    back_btn = types.InlineKeyboardButton("Назад", callback_data=country_services_cb.new(1, country_code, operator=operator))
    keyboard_markup.add(back_btn)

    await msg.answer_photo(config.BOARD_IMAGE_FILE_ID, caption=f"🔍 Результаты поиска ({len(search_results)}):", reply_markup=keyboard_markup)

    await state.finish()


@dp.callback_query_handler(service_cb.filter())
async def service_message(call: types.CallbackQuery, callback_data: dict):
    country_code = callback_data["country_code"]
    service_code = callback_data["service_code"]
    operator = callback_data["operator"]

    countries_list = await sim_service._countries_list()
    services_list_names = await sim_service._services_list()

    for _country in countries_list:
        if country_code == _country.get("id"):
            country = _country
            break
    else:
        await call.answer("Извините, что-то пошло не так. Код ошибки: x847392", True)
        return

    country_operators_list = country.get("operators")
    services_list = await sim_service._numbers_status(country_code, operator)
    service = services_list.get(service_code)
    price = (service.get("defaultPrice") * (config.COMMISSION_AMOUNT / 100)) + service['defaultPrice']

    message_text = [
        f"▫️ Выбранный сервис: {services_list_names.get(service_code)}",
        f"▫️ Выбранный оператор: {operator.capitalize() if operator != 'any' else 'Все'}",
        f"▫️ Выбранная страна: {country2flag.get(country.get('name'))} {country.get('name', 'Unknown')}",
        "",
        f"▫️ Цена: {price}₽",
        # f"▫️ В наличии: {service.get('count')} номеров"
    ]

    keyboard_markup = types.InlineKeyboardMarkup()
    buy_btn = types.InlineKeyboardButton("Купить", callback_data=buy_number_cb.new(country_code, service_code, operator, price))
    back_btn = types.InlineKeyboardButton("Назад", callback_data=country_services_cb.new(1, country_code, operator))
    keyboard_markup.add(buy_btn)
    keyboard_markup.add(back_btn)

    await call.message.edit_caption("\n".join(message_text), reply_markup=keyboard_markup)
    await call.answer()


@dp.callback_query_handler(buy_number_cb.filter())
async def buy_service_number_message(call: types.CallbackQuery, callback_data: dict):
    country_code = callback_data["country_code"]
    service_code = callback_data["service_code"]
    operator = callback_data["operator"]
    price = float(callback_data["price"])

    user = User.where(user_id=call.message.chat.id).first()
    user_balance = user.balance

    if user_balance < service_price:
        await call.answer("У вас недостаточно средств для покупки", True)
        return

    try:
        status = await sim_service.get_number(service_code, operator, country_code)
    except Exception:
        await call.answer("Неизвестная ошибка во время покупки номеров", True)
        raise

    if status == "NO_NUMBERS":
        await call.answer("Упс, оказывается номера уже закончились", True)
        # TODO
        # await sim_service.update_number_count(country_code, service_code)
        # await service_message(call, callback_data)
        return
    elif status in ["NO_BALANCE"]:
        await call.answer("Извините, что-то пошло не так", True)
        await bot.send_message(chat_id=config.ADMIN_ID, text="ТРЕВОГА! У ВАС ЗАКОНЧИЛСЯ БАЛАНС В SMSHub! СРОЧНО ПОПОЛНИТЕ!!!")
        return
    elif len(status.split(":")) != 3:
        await call.answer("Извините, что-то пошло не так", True)
        return

    _, id, number = status.split(":")

    countries_list = await sim_service._countries_list()
    services_list_names = await sim_service._services_list()

    for _country in countries_list:
        if country_code == _country.get("id"):
            country = _country
            break
    else:
        await call.answer("Извините, что-то пошло не так. Код ошибки: x847392", True)
        return

    country = f"{country2flag.get(country.get('name'))} {country.get('name', 'Unknown')}"
    service = f"{services_list_names.get(service_code)}"
    operator = f"{operator.capitalize() if operator != 'any' else 'Все'}"

    SMSHub.create(user_id=call.message.chat.id, task_id=id, service=service, operator=operator, country=country, price=price, number=number)
    user.update(balance=user_balance - price)

    await call.answer("Номер успешно заказан!")
    await task_manager_message(call, {"task_id": id})


@dp.callback_query_handler(all_operation_cb.filter())
async def all_operations_message(call: types.CallbackQuery, callback_data: dict):
    page = int(callback_data["page"])
    page_index = page - 1
    page_index_start_position = page_index * LOW_ELEMENTS_ON_PAGE
    page_index_end_position = page_index_start_position + LOW_ELEMENTS_ON_PAGE

    task_status = OnlinesimStatus(int(callback_data["status"]))

    user_operations = Onlinesim.where(user_id=call.message.chat.id, status=task_status).all()
    user_operations.reverse()

    if user_operations:
        pages_number = math.ceil(float(len(user_operations)) / float(LOW_ELEMENTS_ON_PAGE))
    else:
        pages_number = 1

    keyboard = types.InlineKeyboardMarkup()
    active = Onlinesim.where(user_id=call.message.chat.id, status=OnlinesimStatus.waiting).all()
    finish = Onlinesim.where(user_id=call.message.chat.id, status=OnlinesimStatus.success).all()
    cancel = Onlinesim.where(user_id=call.message.chat.id, status=OnlinesimStatus.cancel).all()

    if not user_operations:
        no_tasks_btn = types.InlineKeyboardButton("👓 Нет заказов", callback_data="tester")
        keyboard.add(no_tasks_btn)
    else:
        for task in user_operations[page_index_start_position : page_index_end_position]:
            task_btn = types.InlineKeyboardButton(f"№{task.id} | {task.service_code} | {task.country_code}", callback_data=task_manager_cb.new(task.tzid))
            keyboard.add(task_btn)

    active_tasks_btn = types.InlineKeyboardButton(f"♻️ активные ({len(active)})", callback_data=all_operation_cb.new(1, OnlinesimStatus.waiting.value))
    finished_tasks_btn = types.InlineKeyboardButton(f"✅ выполненные ({len(finish)})", callback_data=all_operation_cb.new(1, OnlinesimStatus.success.value))
    canceled_tasks_btn = types.InlineKeyboardButton(f"❌ отмененные ({len(cancel)})", callback_data=all_operation_cb.new(1, OnlinesimStatus.cancel.value))
    keyboard.row(active_tasks_btn, finished_tasks_btn, canceled_tasks_btn)

    if task_status == OnlinesimStatus.waiting:
        task_type_name = "♻️ Активные"
    elif task_status == OnlinesimStatus.success:
        task_type_name = "✅ Выполненные"
    elif task_status == OnlinesimStatus.cancel:
        task_type_name = "❌ Отмененные"

    plagination_keyboard_list = []

    if page > 1:
        previous_page_btn = types.InlineKeyboardButton("⬅️", callback_data=all_operation_cb.new(page - 1, task_status.value))
        plagination_keyboard_list.append(previous_page_btn)

    pages_number_btn = types.InlineKeyboardButton(f"Страница: {page} из {pages_number}", callback_data="rrr")
    plagination_keyboard_list.append(pages_number_btn)

    if page < pages_number:
        next_page_btn = types.InlineKeyboardButton("➡️", callback_data=all_operation_cb.new(page + 1, task_status.value))
        plagination_keyboard_list.append(next_page_btn)

    keyboard.row(*plagination_keyboard_list)

    back_btn = types.InlineKeyboardButton("Назад", callback_data="main")
    keyboard.add(back_btn)

    message_text = f"{task_type_name} операции ({len(user_operations)}):"

    with suppress(exceptions.MessageNotModified):
        await call.message.edit_caption(message_text, reply_markup=keyboard)

    await call.answer()


@dp.callback_query_handler(task_manager_cb.filter())
async def task_manager_message(call: types.CallbackQuery, callback_data: dict):
    tzid = int(callback_data["tzid"])

    task_info = Onlinesim.where(tzid=tzid).first()

    if not task_info:
        await call.answer("Извините, но данный заказ я не нашел в базе данных", True)
        return

    try:
        if task_info.status == OnlinesimStatus.waiting:
            task = await sim_service.getState(tzid)
        else:
            task = None
    except asyncio.exceptions.TimeoutError:
        await call.answer("Не удалось связаться с сервером поставщика SIM карт, попробуйте чуть позже", True)
        await bot.send_message(chat_id=config.ADMIN_ID, text="Сервера OnlineSim не отвечают на запрос покупки номера")
        return

    if task:
        msg_raw = task.msg
        time = task.time
        number = task.number
        service_response = task.response
    else:
        msg_raw = task_info.msg
        time = 0
        number = task_info.number
        service_response = None  # !!!???

    country = task_info.country_code
    service = task_info.service_code

    if msg_raw is None:
        logger.error("msg_raw is None, using workaround")
        msg_raw = []

    if task_info.status == OnlinesimStatus.waiting:
        status = "Активно"
    elif task_info.status == OnlinesimStatus.success:
        status = "Успешно"
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
    black_btn = types.InlineKeyboardButton("Назад", callback_data=all_operation_cb.new(1, OnlinesimStatus.waiting.value))
    keyboard.add(black_btn)

    expirity = readable_timedelta(datetime.timedelta(seconds=time))
    msg = '\n'.join(mark_sms_code(msg_raw))

    message_text = [
        f"▫️ ID опреации: {task_info.id}",
        f"▫️ Номер телефона: {number}",
        f"▫️ Страна: {country}",
        f"▫️ Сервис: {service}",
        f"▫️ Цена: {task_info.price}₽",
        f"▫️ Время покупки: {task_info.created_at.astimezone(pytz.timezone('Europe/Moscow'))} (Московское время)",
        f"▫️ Длительность действия номера: {expirity}",
        f"▫️ Статуc: {status}",
        f"▫️ Сообщения ({len(msg_raw)}):",
        f"{msg}"
    ]

    with suppress(exceptions.MessageNotModified):
        await call.message.edit_caption('\n'.join(message_text), reply_markup=keyboard, parse_mode=types.ParseMode.HTML)

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

    if task:
        msg = task.msg
        service_response = task.response
    else:
        msg = task_info.msg
        service_response = None

    if not msg:
        user = User.where(user_id=call.message.chat.id).first()
        user.update(balance=user.balance + task_info.price)

    if service_response in ["TZ_OVER_OK", "TZ_NUM_ANSWER"]:
        _task_status = OnlinesimStatus.success
    elif service_response == "TZ_NUM_WAIT":
        _task_status = OnlinesimStatus.cancel
    else:
        logger.error(f"Unknown task status: {service_response}")
        if msg:
            _task_status = OnlinesimStatus.success
        else:
            _task_status = OnlinesimStatus.cancel

    task_info.update(msg=msg, status=_task_status)

    close_task_info = await sim_service.setOperationOk(tzid)
    await task_manager_message(call, callback_data)


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
            refill_btn = types.InlineKeyboardButton(f"{refill.source.name} | {refill.amount}", callback_data="refill_manager")
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

    if not is_digit(amount):
        keyboard = types.InlineKeyboardMarkup()
        back_btn = types.InlineKeyboardButton("Назад", callback_data="balance")
        keyboard.add(back_btn)
        await msg.answer_photo(config.BOARD_IMAGE_FILE_ID, caption="Баланс пользывателя должен быть в цифрах", reply_markup=keyboard)
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
        f"Если они вам по какой-то причине не подходят, то вы можете написать админу: @{config.ADMIN_USERNAME}"
    ]
    if msg_type == "edit":
        await msg.edit_caption('\n'.join(message_text), reply_markup=keyboard)
    elif msg_type == "answer":
        await msg.answer_photo(config.BOARD_IMAGE_FILE_ID, caption='\n'.join(message_text), reply_markup=keyboard)

    await PaymentMethod.waiting_method.set()


@dp.callback_query_handler(refill_balance_via_cb.filter(method=["qiwi"]), state=PaymentMethod.waiting_method)
async def refill_balance_via_qiwi_message(call: types.CallbackQuery, callback_data: dict, state: FSMContext):
    amount = callback_data.get("amount", 700)

    qiwi_payment_comment = f"{config.BOT_NAME}-{call.message.chat.id}"
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
    amount = callback_data.get("amount", 700)

    yoomoney_payment_label = f"{config.BOT_NAME}-{call.message.chat.id}"
    yoomoney_payment_link = generate_yoomoney_payment_form_link(config.YOOMONEY_RECEIVER, f"Пополнение баланс бота {config.BOT_NAME}", yoomoney_payment_label, amount)

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

    bot_link = await get_start_link(call.message.chat.id)

    _frwd_telegram_url = "https://t.me/share/url"
    _frwd_telegram_params = {"url": bot_link, "text": f"{config.BOT_NAME} - сервис для приёма SMS сообщений"}
    _frwd_telegram_req = PreparedRequest()
    _frwd_telegram_req.prepare_url(_frwd_telegram_url, _frwd_telegram_params)
    forward_url = _frwd_telegram_req.url

    keyboard = types.InlineKeyboardMarkup()
    forward_link_btn = types.InlineKeyboardButton("🔗 Поделиться ссылкой", forward_url)
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
    tech_support_btn = types.InlineKeyboardButton("👨‍💻 Техподдержка / Администратор", f"https://t.me/{config.ADMIN_USERNAME}")
    news_btn = types.InlineKeyboardButton("📢 Новости", "https://t.me/ActiVisioNews")
    back_btn = types.InlineKeyboardButton("Назад", callback_data="main")
    keyboard.add(tech_support_btn)
    keyboard.add(news_btn)
    keyboard.add(back_btn)
    message_text = [
        f"{config.BOT_NAME} - уникальный сервис для приёма SMS сообщений",
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
    else:
        logger.error(f"Unknown callback data: {answer_data}")
        await call.answer("Функция не реализована", True)
