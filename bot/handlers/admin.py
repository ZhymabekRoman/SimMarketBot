from aiogram import types
from aiogram.utils.exceptions import BotBlocked, RetryAfter
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.dispatcher import FSMContext

from bot import dp
from bot.user_data import config
from bot.models.user import User
from bot.models.refills import Refill, RefillSource
from bot.utils.make_tarfile import aiomake_tarfile

import os
import asyncio
from random import randint
from datetime import datetime


class SendMailing(StatesGroup):
    waiting_message_to_mailing = State()

class ChangeBalance(StatesGroup):
    waiting_user_id = State()
    waiting_new_balance = State()


async def generate_back_keyboard():
    keyboard = types.InlineKeyboardMarkup()
    back_btn = types.InlineKeyboardButton("Назад", callback_data="admin_panel")
    keyboard.add(back_btn)
    return keyboard


@dp.callback_query_handler(text="admin_panel", state='*')
async def admin_panel_btn_message(call: types.CallbackQuery, state: FSMContext):
    await state.finish()
    await admin_panel_message(call.message, "edit")
    await call.answer()


@dp.message_handler(lambda message: True if message.chat.id == config.ADMIN_ID and message.text == "/admin" else False)
async def admin_panel_message(message: types.Message, msg_type="answer"):

    keyboard = types.InlineKeyboardMarkup()
    mailing_btn = types.InlineKeyboardButton("Сделать рассылку 📧", callback_data="make_mailing")
    change_user_balance_btn = types.InlineKeyboardButton("Изменить баланс юзера", callback_data="change_user_balance")
    make_backup_btn = types.InlineKeyboardButton("Сделать резервную копию данных", callback_data="make_backup")
    keyboard.add(mailing_btn)
    keyboard.add(change_user_balance_btn)
    keyboard.add(make_backup_btn)

    users = User.all()

    _all_balance = 0
    for _user in users:
        _all_balance += _user.balance

    message_text = [
        "Админ панель",
        f"Общее количество пользователей: {len(users)}",
        f"Общии баланс в боте: {_all_balance}"
    ]
    if msg_type == "answer":
        await message.answer('\n'.join(message_text), reply_markup=keyboard)
    elif msg_type == "edit":
        await message.edit_text('\n'.join(message_text), reply_markup=keyboard)


@dp.callback_query_handler(text='make_backup')
async def make_backup_message(call: types.CallbackQuery):
    await call.answer("Процесс резервного копирования начат, ожидайте ...", True)
    now = datetime.now()
    date_time_str = now.strftime("%Y-%m-%d %H:%M:%S")
    created_tarfile = await aiomake_tarfile(f"ActiVision_backup_{date_time_str}", "bot/user_data/")
    await call.bot.send_document(call.from_user.id, types.InputFile(created_tarfile))
    os.remove(created_tarfile)


@dp.callback_query_handler(text='change_user_balance', state='*')
async def change_user_balance_message(call: types.CallbackQuery):
    await call.message.edit_text("Отправьте ID юзера: ", reply_markup=await generate_back_keyboard())
    await ChangeBalance.waiting_user_id.set()
    await call.answer()


@dp.message_handler(state=ChangeBalance.waiting_user_id, content_types=types.ContentTypes.TEXT)
async def change_user_balance_step1_message(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.reply("ID пользывателя должен быть в цифрах", reply_markup=await generate_back_keyboard())
        return

    async with state.proxy() as user_data:
        user_data['user_id'] = int(message.text)

    user = User.where(user_id=user_data["user_id"]).first()

    if not user:
        await message.reply("Такого пользывателя нету, попробуйте еще раз", reply_markup=await generate_back_keyboard())
        return

    await message.reply(f"Отлично, а теперь введите пожалуйста новую сумму баланса. В данное время баланс пользывателя: {user.balance}", reply_markup=await generate_back_keyboard())
    await ChangeBalance.waiting_new_balance.set()


@dp.message_handler(state=ChangeBalance.waiting_new_balance, content_types=types.ContentTypes.TEXT)
async def change_user_balance_step2_message(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.reply("Баланс пользывателя должен быть в цифрах", reply_markup=await generate_back_keyboard())
        return

    user_data = await state.get_data()

    user = User.where(user_id=user_data["user_id"]).first()
    old_balance = float(user.balance)
    new_balance = float(message.text)
    user.update(balance=new_balance)

    old_new_balance_distance = new_balance - old_balance
    Refill.create(user_id=user_data["user_id"], txn_id=randint(100, 100000), source=RefillSource.ADMIN, amount=old_new_balance_distance)

    await state.finish()
    await message.reply("Баланс успешно изменен!", reply_markup=await generate_back_keyboard())


@dp.callback_query_handler(text='make_mailing', state='*')
async def make_mailing_message(call: types.CallbackQuery):
    await call.message.edit_text("Отправьте мне сообщение которое вы хотите разослать всем пользывателям:", reply_markup=await generate_back_keyboard())
    await SendMailing.waiting_message_to_mailing.set()
    await call.answer()


@dp.message_handler(state=SendMailing.waiting_message_to_mailing, content_types=types.ContentTypes.ANY)
async def send_mailing_message(message: types.Message, state: FSMContext):
    async with state.proxy() as user_data:
        user_data['message_to_mailing'] = message

    await message.send_copy(message.chat.id)

    keyboard = types.InlineKeyboardMarkup()
    confirm_to_mailing_message = types.InlineKeyboardButton("Да, все отлично отправить всем!", callback_data="confirm_mailing")
    back_btn = types.InlineKeyboardButton("Попробовать еще раз", callback_data="make_mailing")
    keyboard.add(confirm_to_mailing_message)
    keyboard.add(back_btn)
    await message.answer("Это предварительный просмотр сообщении. Вы действительно хотите это разослать всем пользывателям?", reply_markup=keyboard)


@dp.callback_query_handler(text="confirm_mailing", state=SendMailing.waiting_message_to_mailing)
async def mailing_message(call: types.CallbackQuery, state: FSMContext):

    async with state.proxy() as user_data:
        message_to_mailing = user_data["message_to_mailing"]

    await call.answer()
    await state.finish()

    users = User.all()
    mailing_delay_sec = 1

    admin_mailing_info = [
        "Рассылка начата!",
        "",
        f"Задержка между отправкой рассылки после каждого пользователя: {mailing_delay_sec} секунд",
        f"Общее количество пользывателей: {len(users)}",
        f"Время начала рассылки: {datetime.utcnow()}",
        "Количество успешно отправленных рассылок: {0}",
        "Количество не отправленных рассылок: {1}",
        "Количество юзеров, заблокировавших бота: {2}"
    ]

    success_mailing_num = 0
    unsuccess_mailing_num = 0
    bot_blocked_users_num = 0

    for user in users:
        try:
            await message_to_mailing.send_copy(user.user_id)
        except BotBlocked:
            bot_blocked_users_num += 1
        except RetryAfter as ex:
            await asyncio.sleep(ex.timeout * 1.5)
        except Exception as ex:
            await call.bot.send_message(chat_id=call.message.chat.id, text=f"Во время отправки рассылки словил исключение: {ex}")
            unsuccess_mailing_num += 1
        else:
            success_mailing_num += 1
        finally:
            await call.message.edit_text('\n'.join(admin_mailing_info).format(success_mailing_num, unsuccess_mailing_num, bot_blocked_users_num))
            await asyncio.sleep(mailing_delay_sec)

    admin_mailing_info[0] = "Рассылка окончена!"
    await call.message.edit_text('\n'.join(admin_mailing_info).format(success_mailing_num, unsuccess_mailing_num, bot_blocked_users_num), reply_markup=await generate_back_keyboard())
