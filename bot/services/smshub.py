# Based on: https://github.com/Viiprogrammer/getSMS/blob/main/index.js


import json
import aiohttp
import asyncio
import random

from bot.utils.json_storager import JSONCacher
from bot.utils.country2flag import Country2Flag
from bot.utils.retry import retry_on_connection_issue

from loguru import logger
from fuzzywuzzy import process, fuzz
from pydantic import BaseModel, validator

from icecream import ic


class SMSHubResponse:
    def __init__(self, text: str):
        self.text = text

    def json(self):
        return json.loads(self.text)


class SMSHubException(Exception):
    errors_list = {
        'BAD_KEY': 'Invalid api key',
        'ERROR_SQL': 'Server database error',
        'BAD_ACTION': 'Bad request data',
        'WRONG_SERVICE': 'Wrong service identifier',
        'BAD_SERVICE': 'Wrong service name',
        'NO_ACTIVATION': 'Activation not found.',
        'NO_BALANCE': 'No balance',
        'NO_NUMBERS': 'No numbers',
        'WRONG_ACTIVATION_ID': 'Wrong activation id',
        'WRONG_EXCEPTION_PHONE': 'Wrong exception phone',
        'NO_BALANCE_FORWARD': 'No balance for forward',
        'NOT_AVAILABLE': 'Multiservice is not available for selected country',
        'BAD_FORWARD': 'Incorrect forward',
        'WRONG_ADDITIONAL_SERVICE': 'Wrong additional service',
        'WRONG_SECURITY': 'WRONG_SECURITY error',
        'REPEAT_ADDITIONAL_SERVICE': 'Repeat additional service error'
    }

    def __init__(self, status_code: str, message = None):
        unknown_status_code_msg = "Unknown error. Error code: {}".format(status_code)
        if message is None:
            self.message = self.errors_list.get(status_code, unknown_status_code_msg)
        else:
            self.message = message

        self.status_code = status_code

    @classmethod
    def check(cls, status_code: str):
        if isinstance(status_code, str):
            if status_code in cls.errors_list:
                return cls(status_code)

    def __str__(self):
        return "{} | {}".format(self.status_code, self.message)


class SMSHub:
    _cache = JSONCacher("bot/user_data/SMSHub.json")

    def __init__(self, api_key: list, loop):
        self.__api_key = api_key
        self.api_url = "https://smshub.org/api.php"
        self.stub_api_url = "https://smshub.org/stubs/handler_api.php"
        self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=40))
        self.loop = loop
        self.lock = asyncio.Lock()

    @property
    def api_key(self):
        return random.choice(self.__api_key)

    @retry_on_connection_issue(2)
    async def request(self, url: str, external_params: dict):
        params = {"api_key": self.api_key}
        params.update(external_params)

        headers = {
            'cookie': 'lang=ru',  # ЫАААААА!? На дворе 2022 год, мать честная! Нахуя блять указывать куки в хэйдере запроса? В хэйдере блять!?
        }

        async with self.session.get(url=url, params=params, headers=headers) as response:
            result = await response.text()

            # Не возможно узнать по статус коду ответа завершилась ли текущая операция ошибкой либо все успешно
            # Приходится в ручную проверять
            exception_check = SMSHubException.check(result)
            if exception_check:
                raise exception_check

        return SMSHubResponse(result)

    async def countries_list(self):
        return self._cache.get("countries_list", [])

    async def _countries_list(self):
        return (await self._get_list_of_countries_and_service())["data"]

    async def _get_list_of_countries_and_service(self):
        """
        Response model:

        {
            "currentCountry": null,
            "currentOperator": null,
            "data": [
                {
                    "id": "0",
                    "name": "\u0420\u043e\u0441\u0441\u0438\u044f",
                    "operators": [
                        "any"
                    ]
                }
            ]
            ,
            "services": {
                    "ab": "Alibaba"
            },
            "status": "success"
        }
        """
        list_of_countries_and_services = (await self.request(self.api_url, {'cat': 'scripts', 'act': 'manageActivations', 'asc': 'getListOfCountriesAndOperators'})).json()
        return list_of_countries_and_services

    async def services_list(self):
        return self._cache.get("services_list", {})

    async def _services_list(self):
        return (await self._get_list_of_countries_and_service())["services"]

    async def numbers_status(self, country_code: str):
        _cache_key = str({"numbers_status": str(country_code)})
        return self._cache.get(_cache_key, {})

    async def _numbers_status(self, country_code: str, operator_code: str):
        """
        Response model:

        {
          "vk": {
            "priceMap": {
              "9.00": 12793,
              "8.99": 8130
            },
            "maxPrice": 9.00,
            "defaultPrice": 9.00,
            "defaultMaxPrice": true,
            "random": true,
            "quantityForMaxPrice": 20923,
            "totalQuantity": 20923,
            "canAuction": false,
            "auctionMap": [],
            "work": true
          }
        }
        """
        numbers_status = (await self.request(self.stub_api_url, {'action': 'getNumbersStatusAndCostHubFree', 'country': country_code, 'operator': operator_code})).json()
        return numbers_status

    async def get_number(self, service_code: str, operator_code: str, country_code: str):
        number_stats = await self.request(self.stub_api_url, {'action': 'getNumber', 'country': country_code, 'service': service_code, 'operator': operator_code}).text
        return number_stats

    async def get_status(self, id: int):
        number_stats = await self.request(self.stub_api_url, {'action': 'getStatus', 'id': id}).text
        number_stats_code, code = number_stats.split(":")
        return number_stats_code, code

    async def cache_updater(self, waiting_time: int = 3600):
        while True:
            await asyncio.sleep(waiting_time)
            self.loop.create_task(self._countries_list())

    """
    async def update_number_count(self, country_code, service_code, new_count: int = 0):
        country_code, service_code = str(country_code), str(service_code)
        _cache_key = str({"number_stats": str(country_code)})
        _result = self._cache[_cache_key][service_code]

        _result.update({"count": new_count})

        self._cache[_cache_key][service_code] = _result
    """

    async def fuzzy_countries_search(self, search_text:str):
        countries_list_ru = {}

        for country in await self._countries_list():
            countries_list_ru.update({country.get("id"): country.get("name", "Unknown")})

        return process.extractBests(search_text, countries_list_ru, scorer=fuzz.WRatio, score_cutoff=70)

    async def fuzzy_services_search(self, country_code: str, operator:str, search_text: str):
        services_list = await self._services_list()
        services_list_ru = {}

        for service_code in (await self._numbers_status(country_code, operator)).keys():
            service_name = services_list.get(service_code)
            services_list_ru.update({service_code: service_name})

        return process.extractBests(search_text, services_list_ru, scorer=fuzz.WRatio, score_cutoff=70)

    async def shutdown(self):
        await self.session.close()
        self._cache.shutdown()
