import os
import asyncio
import base64


def base64_encode(message: str) -> str:
    """Зашифровывает строку в base64"""
    message_bytes = message.encode('ascii')
    base64_bytes = base64.b64encode(message_bytes)
    base64_message = base64_bytes.decode('ascii')
    return base64_message


CONFIG_DIR = os.path.join("bot", "user_data")


async def main():
    print("Добро пожаловать! Вас приветствует мастер по конфигурации Телеграм бота 'Sim Market Bot'!")

    # Создаём папку где будут храниться конфигурационные данные
    os.makedirs(CONFIG_DIR)

    with open(os.path.join(CONFIG_DIR, "database.db"), "w") as file:
        pass

    with open(os.path.join(CONFIG_DIR, "__init__.py"), "w") as file:
        pass

    bot_api_token = input("Пожалуйста ведите Bot API токен Телеграм бота: ")

    tech_admin_user_id = int(input("Введите Telegram user id главного администратора: "))

    qiwi_wallet = input("Введите номер кошелька, куда вы хотите получать деньги, в формате +7xxxxxxxxxx (например - +79001234567): ")
    qiwi_api_token = input("Введите QIWI API токен. Токен вы можете получить по адресу https://qiwi.com/api : ")

    onlinesim_api_token = input("Введите Online SIM API токен: Токен вы можете получить по адресу https://onlinesim.ru/v2/pages/profile : ")

    commission_amount = float(input("Введите процент комисси на цены (for example - 100): "))

    admin_username = input("Введите юзернем админа, который будет отвечать за мониторингом пополнение баланса, с знаком @ (например - @example): ")

    yoomoney_receiver = input("Введите YooMoney адрес кошелька куда вы хотите получать деньги: ")
    yoomoney_token = input("Введите YooMoney токен (ТОКЕН!): ")

    with open(os.path.join(CONFIG_DIR, "config.py"), "w") as file:
        file.write("# Declare Telegram Bot API token\n")
        file.write(f"API_TOKEN = '{base64_encode(bot_api_token)}'\n")
        file.write("# Declare main admin user id\n")
        file.write(f"ADMIN_ID = {tech_admin_user_id}\n")
        file.write("# Declare QIWI wallet telephone number\n")
        file.write(f"QIWI_WALLET = '{qiwi_wallet}'\n")
        file.write("# Declare QIWI API token\n")
        file.write(f"QIWI_API_TOKEN = '{base64_encode(qiwi_api_token)}'\n")
        file.write("# Declare commission amount\n")
        file.write(f"COMMISSION_AMOUNT = {commission_amount}\n")
        file.write("# Declare Online SIM service API tolen\n")
        file.write(f"ONLINE_SIM_API_TOKEN = '{base64_encode(onlinesim_api_token)}'")
        file.write("# Declare Admin username with @\n")
        file.write(f"ADMIN_USERNAME = '{admin_username}'\n")
        file.write("# Declare YooMoney wallet\n")
        file.write(f"YOOMONEY_RECEIVER = '{yoomoney_receiver}'\n")
        file.write("# Declare YooMoney token\n")
        file.write(f"YOOMONEY_TOKEN = '{yoomoney_token}'")

    print("Готово!")


if __name__ == "__main__":
    if os.path.isdir(CONFIG_DIR):
        print("Конфигурационные данные о боте уже заполнены. Бот готов к работе")
    else:
        asyncio.run(main())
