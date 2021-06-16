from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters import Text
from aiogram.utils.callback_data import CallbackData
from aiogram import types

from bot import dp, sim_service, loop
from bot.models.user import User
from bot.models.onlinesim import Onlinesim, OnlinesimStatus
from bot.user_data import config
from bot.utils.qiwi import generate_qiwi_payment_form_link

from icecream import ic

countries_services_cb = CallbackData("countries_services", "country_code")
service_cb = CallbackData("service", "country_code", "service_code")
buy_number_cb = CallbackData("buy_service_number", "country_code", "service_code", "price")
task_manager_cb = CallbackData("task_manager", "tzid")


class ReciveSMS(StatesGroup):
    waiting_country = State()
    waiting_service = State()


def generate_main_reply_keyboard():
    keyboard_markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard_markup.row("Прием СМС")
    keyboard_markup.row("Баланс", "Все операции СМС")
    return keyboard_markup


# Проверяем на существование текущего пользывателя в БД
# Если не существует тогда регистрируем ID пользывателя в БД (Или можно запросить язык)
@dp.message_handler(lambda msg: User.where(user_id=msg.chat.id).first() is None)
async def new_user_message(msg: types.Message):
    ic("User not found, create ...")
    # TODO: Implement referrals
    # bot_start_arguments = message.get_args()

    # if not bot_start_arguments or not bot_start_arguments.isdigit():
    #     referral = None
    # else:
    #     referral = int(bot_start_arguments)
    User.create(user_id=msg.chat.id)


@dp.message_handler(commands=['start'])
async def main_menu_message(msg: types.Message):
    message_text = [
        f"Привет, {msg.from_user.first_name}!",
        "При помощи этого бота ты можешь принимать сообщения на номера, который я дам, тем самым регистрироваться на разных сайтах и соц.сетях"
    ]
    await msg.reply("\n".join(message_text), reply_markup=generate_main_reply_keyboard())


@dp.message_handler(Text(equals="Прием СМС", ignore_case=True))
async def sms_recieve_country_set_message(msg: types.Message, state: FSMContext):
    countries_list = await sim_service.countries_list()
    keyboard_markup = types.InlineKeyboardMarkup(row_width=3)

    countries_btn_list = []
    for country_code, country_name in countries_list.items():
        summary_numbers = await sim_service.summary_numbers_count(country_code)
        if summary_numbers == 0:
            continue
        country_btn = types.InlineKeyboardButton(f"{country_name} ({summary_numbers})", callback_data=countries_services_cb.new(country_code))
        # country_btn = types.InlineKeyboardButton(country_name, callback_data=countries_services_cb.new(country_code))
        countries_btn_list.append(country_btn)
    keyboard_markup.add(*countries_btn_list)

    await msg.reply("1. Выберете страну, номер телефона которой будет Вам выдан", reply_markup=keyboard_markup)


@dp.callback_query_handler(countries_services_cb.filter())
async def countries_services_message(call: types.CallbackQuery, callback_data: dict):
    country_code = callback_data["country_code"]
    services_list = await sim_service.number_stats(country_code)

    keyboard_markup = types.InlineKeyboardMarkup()
    services_btn_list = []
    for service_code, service in services_list.items():
        service_btn = types.InlineKeyboardButton(f"{service['service']} ({service['count']})", callback_data=service_cb.new(country_code, service_code))
        services_btn_list.append(service_btn)
    keyboard_markup.add(*services_btn_list)

    await call.message.edit_text("2. Веберите сервис, от которого вам необходимо принять СМС", reply_markup=keyboard_markup)


@dp.callback_query_handler(service_cb.filter())
async def service_message(call: types.CallbackQuery, callback_data: dict):
    country_code = callback_data["country_code"]
    service_code = callback_data["service_code"]

    countries_list = await sim_service.countries_list()
    services_list = await sim_service.number_stats(country_code)

    service = services_list.get(service_code)
    country = countries_list.get(country_code)

    message_text = [
        f"Выбранный сервис: {service['service']}",
        f"Выбранная страна: {country}",
        "",
        f"Цена: {service['price']}₽",
        f"В наличии: {service['count']} номеров"
    ]

    keyboard_markup = types.InlineKeyboardMarkup()
    buy_btn = types.InlineKeyboardButton("Купить", callback_data=buy_number_cb.new(country_code, service_code, service['price']))
    back_btn = types.InlineKeyboardButton("Назад", callback_data=countries_services_cb.new(country_code))
    keyboard_markup.add(buy_btn)
    keyboard_markup.add(back_btn)

    await call.message.edit_text("\n".join(message_text), reply_markup=keyboard_markup)


@dp.callback_query_handler(buy_number_cb.filter())
async def buy_service_number_message(call: types.CallbackQuery, callback_data: dict):
    country_code = callback_data["country_code"]
    service_code = callback_data["service_code"]
    service_price = float(callback_data["price"])

    user_balance = User.where(user_id=call.message.chat.id).first().balance
    if user_balance < service_price:
        await call.answer("У вас недостаточно средств для покупки", True)
        return

    status, tzid = await sim_service.buy_number(service_code, country_code)

    if status is not True:
        await call.answer("Извините, что-то пошло не так", True)
        return

    sim_service.run_waiting_code_task(tzid)

    Onlinesim.create(user_id=call.message.chat.id, tzid=tzid, service_code=service_code, country_code=country_code)

    await call.answer()


@dp.message_handler(Text(equals="Все операции СМС", ignore_case=True))
async def all_operations_message(msg: types.Message, messaging_type="answer", task_status: int = OnlinesimStatus.waiting):
    keyboard = types.InlineKeyboardMarkup()
    user_operations = Onlinesim.where(user_id=msg.chat.id, status=task_status).all()
    if not user_operations:
        no_tasks_btn = types.InlineKeyboardButton("👓 Нет заказов", callback_data="tester")
        keyboard.add(no_tasks_btn)
    else:
        for task in user_operations:
            task_btn = types.InlineKeyboardButton(task, callback_data=task_manager_cb.new(task.tzid))
            keyboard.add(task_btn)

    active_tasks_btn = types.InlineKeyboardButton("♻️ активные", callback_data="active_tasks")
    finished_tasks_btn = types.InlineKeyboardButton("✅ выполненные", callback_data="finished_tasks")
    canceled_tasks_btn = types.InlineKeyboardButton("❌ отмененные", callback_data="canceled_tasks")
    expired_tasks_btn = types.InlineKeyboardButton("🕰 Истекшие", callback_data="expired_tasks")
    keyboard.row(active_tasks_btn, finished_tasks_btn, canceled_tasks_btn)
    keyboard.row(expired_tasks_btn)

    if task_status == OnlinesimStatus.waiting:
        task_type_name = "♻️ Активные"
    elif task_status == OnlinesimStatus.success:
        task_type_name = "✅ Выполненные"
    elif task_status == OnlinesimStatus.cancel:
        task_type_name = "❌ Отмененные"
    elif task_status == OnlinesimStatus.expire:
        task_type_name = "🕰 Истекшие"

    message_text = f"{task_type_name} операции ({len(user_operations)}):"

    if messaging_type == "answer":
        await msg.reply(message_text, reply_markup=keyboard)
    elif messaging_type == "edit_message":
        await msg.edit_text(message_text, reply_markup=keyboard)


@dp.callback_query_handler(task_manager_cb.filter())
async def task_manager_message(call: types.CallbackQuery, callback_data: dict):
    tzid = int(callback_data["tzid"])

    task_info = Onlinesim.where(tzid=tzid).first()
    if not task_info:
        await call.answer("Извините, что-то пошло не так", True)
        return

    message_text = [
        f"ID опреации: {task_info.tzid}",
        "Номер телефона: ",
        "Страна: ",
        "Сервис: ",
        "Цена: ",
        "Стату операции: "
    ]

    await call.message.edit_text('\n'.join(message_text))
    await call.answer()

@dp.message_handler(Text(equals="Баланс", ignore_case=True))
async def balance_message(msg: types.Message, msg_type="answer"):
    user_balance = User.where(user_id=msg.chat.id).first().balance

    keyboard = types.InlineKeyboardMarkup()
    # refill_history_btn = types.InlineKeyboardButton("История пополнения", callback_data="reffil_history")
    refill_balance_btn = types.InlineKeyboardButton("Пополнить баланс", callback_data="refill_balance")
    # keyboard.add(refill_history_btn)
    keyboard.add(refill_balance_btn)
    message_text = [
        f"💲 Ваш баланс: **{user_balance} ₽**",
        f"🏷 Ваш id: `{msg.chat.id}`",
        "",
        # "Проверить рефералов можно по команде: /referrals"
    ]
    if msg_type == "answer":
        await msg.reply('\n'.join(message_text), reply_markup=keyboard, parse_mode=types.ParseMode.MARKDOWN)
    elif msg_type == "edit":
        await msg.edit_text('\n'.join(message_text), reply_markup=keyboard, parse_mode=types.ParseMode.MARKDOWN)


@dp.callback_query_handler(text="refill_history")
async def refill_history_message(call: types.CallbackQuery):
    # TODO: Implement
    keyboard = types.InlineKeyboardMarkup()
    back_btn = types.InlineKeyboardButton("Назад", callback_data="balance_btn")
    keyboard.add(back_btn)
    await call.message.edit_text("История пополнения баланса", reply_markup=keyboard)


@dp.callback_query_handler(text='refill_balance')
async def refill_balance_message(call: types.CallbackQuery):
    keyboard = types.InlineKeyboardMarkup()
    qiwi_btn = types.InlineKeyboardButton("Киви", callback_data="refill_balance_via_qiwi")
    keyboard.add(qiwi_btn)
    message_text = [
        "Выберите один из способов пополнения",
        f"Если они вам по какой-то причине не подходят, то вы можете написать админу: {config.ADMIN_USERNAME}"
    ]
    await call.message.edit_text('\n'.join(message_text), reply_markup=keyboard)
    await call.answer()


@dp.callback_query_handler(text='refill_balance_via_qiwi')
async def refill_balance_via_qiwi_message(call: types.CallbackQuery):
    qiwi_payment_link = generate_qiwi_payment_form_link("99", config.QIWI_WALLET, 750.0, call.message.chat.id, 643, ["account", "comment"], 0)

    keyboard = types.InlineKeyboardMarkup()
    payement_qiwi_btn = types.InlineKeyboardButton("Перейти к оплате", qiwi_payment_link)
    back_btn = types.InlineKeyboardButton("Назад", callback_data="refill_balance")
    keyboard.add(payement_qiwi_btn)
    keyboard.add(back_btn)
    message_text = [
        "💲 Пополнение баланса через киви 💲",
        "",
        "💥 Для пополнения баланса переведите нужную сумму на",
        f"👝 Qiwi кошелек: `{config.QIWI_WALLET}`",
        "❗️ В комментарии платежа ОБЯЗАТЕЛЬНО укажите:",
        f'`{call.message.chat.id}`',
        "Деньги зачисляться автоматически в течении 2 минут",
        "Вы получите уведомление в боте"
    ]
    await call.message.edit_text('\n'.join(message_text), parse_mode=types.ParseMode.MARKDOWN, reply_markup=keyboard)
    await call.answer()



@dp.message_handler(Text(equals="Партнёрская программа", ignore_case=True))
@dp.message_handler(commands=["referrals"])
async def check_referrals(msg: types.Message):
    # TODO: Implement
    # referrals = db.get_referrals(message.chat.id)
    bot_username = (await msg.bot.me).username
    bot_link = f"https://t.me/{bot_username}?start={msg.chat.id}"
    message_text = [
        "👥 Партнёрская программа 👥",
        "➖➖➖➖➖➖➖➖➖➖",
        f"Количество ваших рефералы: {len(referrals)}",
        "",
        "🔗 Ваша партнёрская ссылка:",
        bot_link
    ]

    await msg.answer('\n'.join(message_text))


@dp.callback_query_handler()
async def callback_handler(call: types.CallbackQuery):
    answer_data = call.data
    if answer_data == "balance_btn":
        await balance_message(call.message, "edit")
        await call.answer()
    elif answer_data == 'active_tasks':
        await all_operations_message(call.message, "edit_message", OnlinesimStatus.waiting)
        await call.answer()
    elif answer_data == 'finished_tasks':
        await all_operations_message(call.message, "edit_message", OnlinesimStatus.success)
        await call.answer()
    elif answer_data == 'canceled_tasks':
        await all_operations_message(call.message, "edit_message", OnlinesimStatus.cancel)
        await call.answer()
    elif answer_data == 'expired_tasks':
        await all_operations_message(call.message, "edit_message", OnlinesimStatus.expire)
        await call.answer()
    else:
        await call.answer("Функция не реализована", True)
