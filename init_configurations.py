import os
import asyncio
from aiogram.types import InputFile
from aiogram import Bot
import base64

from config import TomlConfig


def base64_encode(message: str) -> str:
    """Зашифровывает строку в base64"""
    message_bytes = message.encode('ascii')
    base64_bytes = base64.b64encode(message_bytes)
    base64_message = base64_bytes.decode('ascii')
    return base64_message

CONFIG_DIR = os.path.join("bot", "user_data")

async def get_image_board_file_id(bot_api_token: str, tech_admin_user_id: int) -> str:
    bot = Bot(token=bot_api_token)

    image_msg = await bot.send_photo(tech_admin_user_id, InputFile("images/board_image.jpg"))
    file_id = image_msg.photo[-1].file_id

    await bot.close()

    return file_id


async def main():
    print("Добро пожаловать! Вас приветствует мастер по конфигурации Телеграм бота 'Sim Market Bot'!")

    bot_name = input("Введите название бота: ")

    bot_api_token = input("Пожалуйста ведите Bot API токен Телеграм бота: ")

    tech_admin_user_id = int(input("Введите Telegram user id главного администратора: "))

    board_image_file_id = await get_image_board_file_id(bot_api_token, tech_admin_user_id)

    qiwi_wallet = input("Введите номер кошелька, куда вы хотите получать деньги, в формате +7xxxxxxxxxx (например - +79001234567): ")
    qiwi_api_token = input("Введите QIWI API токен. Токен вы можете получить по адресу https://qiwi.com/api : ")

    onlinesim_api_token = input("Введите Online SIM API токен: Токен вы можете получить по адресу https://onlinesim.ru/v2/pages/profile : ")

    commission_amount = float(input("Введите процент комисси на цены. Например - 100: "))

    admin_username = input("Введите юзернем админа, который будет отвечать за мониторингом пополнение баланса, с знаком @ (например - @example): ")

    yoomoney_receiver = input("Введите YooMoney адрес кошелька куда вы хотите получать деньги: ")
    yoomoney_token = input("Введите YooMoney токен (ТОКЕН!): ")

    # Создаём папку где будут храниться конфигурационные данные
    os.makedirs(CONFIG_DIR)

    with open(os.path.join(CONFIG_DIR, "database.db"), "w") as file:
        pass

    config = TomlConfig({})

    config.BOT_NAME = bot_name
    config.API_TOKEN = base64_encode(bot_api_token)
    config.ADMIN_ID = tech_admin_user_id
    config.BOARD_IMAGE_FILE_ID = board_image_file_id
    config.QIWI_WALLET = qiwi_wallet
    config.QIWI_API_TOKEN = base64_encode(qiwi_api_token)
    config.COMMISSION_AMOUNT = commission_amount
    config.ONLINE_SIM_API_TOKEN = base64_encode(onlinesim_api_token)
    config.ADMIN_USERNAME = admin_username
    config.YOOMONEY_RECEIVER = yoomoney_receiver
    config.YOOMONEY_TOKEN = yoomoney_token

    config.export_to_file(os.path.join(CONFIG_DIR, "config.toml"))

    print("Готово!")


if __name__ == "__main__":
    if os.path.isdir(CONFIG_DIR):
        print("Конфигурационные данные о боте уже заполнены. Бот готов к работе")
    else:
        asyncio.run(main())
