import os

assert os.path.isdir(os.path.join("bot", "user_data")), "Configuration folder is missing, please initialize it using script init_configuration.py"

import asyncio
import logging
from loguru import logger
from importlib import resources

from aiogram.contrib.fsm_storage.files import JSONStorage
from aiogram import Bot, Dispatcher

from bot.models import Base, BaseModel
from bot.models.user import User
from bot.models.onlinesim import Onlinesim
from bot.models.refills import Refill

from bot.utils.base64 import base64_decode
from bot.utils import exit_register

import sqlalchemy as sa
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.orm import sessionmaker

from aioqiwi.wallet import Wallet

from bot.services import config
from bot.services.qiwi import QIWIHistoryPoll
from bot.services.onlinesim import OnlineSIM
from bot.services.smshub import SMSHub
from bot.services.yoomoney import Client, YooMoneyHistoryPoll

# Configure logging
logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(name)s - %(message)s")
logging.getLogger('aiogram').setLevel(logging.WARNING)

# Configure loguru
logger.add("logs/all_log_{time}.log", diagnose=False)  # enqueue=True,
logger.add("logs/error_log_{time}.log", diagnose=False, level="ERROR")

# Initalialization API token for work with Telegram Bot API
API_TOKEN = base64_decode(config.API_TOKEN)

# Configure FSM Storage
storage = JSONStorage(os.path.join("bot", "user_data", "FSM_storage.json"))

# Initialize bot and dispatcher
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot, storage=storage)
Bot.set_current(dp.bot)

# Initalialization SQLAlchemy connection
with resources.path("bot.user_data", "database.db") as sqlite_filepath:
    engine = sa.create_engine(f'sqlite:///{sqlite_filepath}', echo=False)

session = scoped_session(sessionmaker(bind=engine, autocommit=True))

# Base.metadata.drop_all(engine)
Base.metadata.create_all(engine)
BaseModel.set_session(session)

# Initalialization QIWI polling manager
loop = asyncio.get_event_loop()

qiwi_wallet = Wallet(api_hash=config.QIWI_API_TOKEN, loop=loop, phone_number=config.QIWI_WALLET)
qiwi_poller = QIWIHistoryPoll(
    loop,
    qiwi_wallet,
    waiting_time=60,
    limit=50,
    process_old_to_new=True,
)

yoomoney_client = Client(config.YOOMONEY_TOKEN)
yoomoney_poller = YooMoneyHistoryPoll(loop, bot, yoomoney_client)

if not config.get("SMS_HUB_API_TOKEN"):
    smshub_token = input("Enter SMSHub API token: ")
    config.SMS_HUB_API_TOKEN = smshub_token

sim_service = SMSHub(config.SMS_HUB_API_TOKEN, loop)
