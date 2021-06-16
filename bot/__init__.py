import os

assert os.path.isdir("bot/user_data"), "Configuration folder is missing, please initialize it using script init_configuration.py"

import asyncio
import logging
from importlib import resources

from aiogram.contrib.fsm_storage.files import JSONStorage
from aiogram import Bot, Dispatcher

from bot.models import Base, BaseModel
from bot.models.user import User
from bot.models.onlinesim import Onlinesim
from bot.utils.base64 import base64_decode
from bot.user_data import config

import sqlalchemy as sa
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.orm import sessionmaker

from aioqiwi.wallet import Wallet
from bot.services.qiwi import QIWIHistoryPoll
from bot.services.converter import CurrencyConverter
from bot.services.onlinesim import OnlineSIM

# Configure logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(name)s - %(message)s")

# Initalialization API token for work with Telegram Bot
API_TOKEN = base64_decode(config.API_TOKEN)

# Configure FSM Storage
storage = JSONStorage("bot/user_data/FSM_storage.json")

# Initialize bot and dispatcher
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot, storage=storage)

# Initalialization SQLAlchemy connection
with resources.path("bot.user_data", "database.db") as sqlite_filepath:
    engine = sa.create_engine(f'sqlite:///{sqlite_filepath}', echo=False)

session = scoped_session(sessionmaker(bind=engine, autocommit=True))

Base.metadata.drop_all(engine)
Base.metadata.create_all(engine)
BaseModel.set_session(session)

# Initalialization QIWI polling manager
loop = asyncio.get_event_loop()

QIWI_API_TOKEN = base64_decode(config.QIWI_API_TOKEN)

qiwi_wallet = Wallet(api_hash=QIWI_API_TOKEN, loop=loop, phone_number=config.QIWI_WALLET)
qiwi_poller = QIWIHistoryPoll(
    qiwi_wallet,
    waiting_time=60,
    limit=50,
    process_old_to_new=True,
)

currency_converter = CurrencyConverter(base64_decode(config.EXCHANGE_RATE_API_TOKEN))
sim_service = OnlineSIM(base64_decode(config.ONLINE_SIM_API_TOKEN), loop)
