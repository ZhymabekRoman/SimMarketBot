import json
import aiohttp
import asyncio

from bot.utils.json_storager import JSONCacher
from bot.utils.country2flag import Country2Flag
from bot.utils.retry import retry_on_connection_issue

from loguru import logger
from fuzzywuzzy import process, fuzz
from pydantic import BaseModel, validator


class getStateModel(BaseModel):
    country: int
    form: str
    number: str
    response: str
    service: str
    sum: int
    time: int
    tzid: int
    msg: list = []

    @validator("msg", pre=True, always=True)
    def set_msg(cls, msg_raw):
        msg_list = []
        for msg in msg_raw:
            received_msg = msg.get("msg", "")
            msg_list.append(received_msg)
        return msg_list


class SMSHub:
    _cache = JSONCacher("bot/user_data/SMSHub.json")

    def __init__(self, api_key, loop):
        self.__api_key = api_key
        self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5))
        self.loop = loop
        self.lock = asyncio.Lock()

    async def countries_list(self):
        return self._cache["countries_list"]

    @retry_on_connection_issue()
    async def _countries_list(self):
        # Using alternative API
        url = "https://smshub.org/stubs/handler_api.php"
        params = {"api_key": self.__api_key, "action": "getPrices"}

        async with self.session.get(url=url, params=params) as response:
            result = await response.text()
            parsed = json.loads(result)

        # _result = {}
        # for country_code, country in parsed.items():
        #     if country["visible"] == 1 and await self._summary_numbers_count(country_code) != 0:
        #         _result.update({country_code: f'{Country2Flag().get(country_code)} {country["rus"]}'})

        async with self.lock:
            self._cache["countries_list"] = parsed

        # return _result
        return parsed

    async def number_stats(self, country_code: int):
        _cache_key = str({"number_stats": str(country_code)})
        return self._cache[_cache_key]

    @retry_on_connection_issue()
    async def _number_stats(self, country_code: int):
        url = "https://onlinesim.ru/api/getNumbersStats.php"
        params = {"apikey": self.__api_key, "country": country_code}

        async with self.session.get(url=url, params=params) as response:
            result = await response.text()
            parsed = json.loads(result)

        _result = {}
        if not isinstance(parsed["services"], list):  # Workaround for OnlineSim's bug
            for _, service in parsed["services"].items():
                if service["count"] != 0:
                    _result.update({service["slug"]: service})

        async with self.lock:
            _cache_key = str({"number_stats": str(country_code)})
            self._cache[_cache_key] = _result

        return _result

    async def summary_numbers_count(self, country_code: int):
        _cache_key = str({"summary_numbers_count": str(country_code)})
        return self._cache[_cache_key]

    @retry_on_connection_issue()
    async def _summary_numbers_count(self, country_code: int):
        services_list = await self._number_stats(country_code)

        _result = 0

        for service_code, service_info in services_list.items():
            _result += service_info["count"]

        async with self.lock:
            _cache_key = str({"summary_numbers_count": str(country_code)})
            self._cache[_cache_key] = _result

        return _result

    @retry_on_connection_issue()
    async def getNum(self, service_code: int, country_code: int):
        url = "https://onlinesim.ru/api/getNum.php"
        params = {"apikey": self.__api_key, "country": country_code, "service": service_code}

        async with self.session.get(url=url, params=params) as response:
            result = await response.text()
            parsed = json.loads(result)

        logger.debug(parsed)

        status = parsed.get("response")
        tzid = parsed.get("tzid")

        return status, tzid

    @retry_on_connection_issue()
    async def getState(
        self,
        tzid: int,
        message_to_code: int = 0,
        msg_list: bool = 1,
        clean: bool = 0,
        repeat: bool = 0,
    ):
        type = "index"
        if repeat:
            type = "repeat"

        url = "https://onlinesim.ru/api/getState.php"
        params = {
            "apikey": self.__api_key,
            "tzid": tzid,
            "message_to_code": message_to_code,
            "msg_list": msg_list,
            "clean": clean,
            "type": type,
        }
        async with self.session.get(url=url, params=params) as response:
            result = await response.text()
            parsed = json.loads(result)

        logger.debug(parsed)

        if isinstance(parsed, dict):
            if parsed.get("response") == "ERROR_NO_OPERATIONS":
                return None

        # OnlineSim return list, with entered tzid's operation, just for more stability let find operation by tzid manually
        for _service in parsed:
            if _service.get("tzid") == tzid:
                return getStateModel(**_service)
        else:
            raise

    @retry_on_connection_issue()
    async def setOperationRevise(self, tzid: int):
        url = "https://onlinesim.ru/api/setOperationRevise.php"
        params = {
            "apikey": self.__api_key,
            "tzid": tzid
        }
        async with self.session.get(url=url, params=params) as response:
            result = await response.text()
            parsed = json.loads(result)

        logger.debug(parsed)

        return parsed

    @retry_on_connection_issue()
    async def setOperationOk(self, tzid: int) -> getStateModel:
        url = "https://onlinesim.ru/api/setOperationOk.php"
        params = {
            "apikey": self.__api_key,
            "tzid": tzid
        }
        async with self.session.get(url=url, params=params) as response:
            result = await response.text()
            parsed = json.loads(result)

        logger.debug(parsed)

        return parsed

    async def cache_updater(self, waiting_time: int = 3600):
        while True:
            await asyncio.sleep(waiting_time)
            self.loop.create_task(self._countries_list())

    async def update_number_count(self, country_code, service_code, new_count: int = 0):
        country_code, service_code = str(country_code), str(service_code)
        _cache_key = str({"number_stats": str(country_code)})
        _result = self._cache[_cache_key][service_code]

        _result.update({"count": new_count})

        self._cache[_cache_key][service_code] = _result

    async def fuzzy_countries_search(self, search_text):
        countries_list_ru = await self.countries_list()
        return process.extractBests(search_text, countries_list_ru, scorer=fuzz.WRatio, score_cutoff=70)

    async def fuzzy_services_search(self, country_code, search_text):
        services_list_ru = {}

        for service_code, service in (await self.number_stats(country_code)).items():
            services_list_ru.update({service_code: service["service"]})

        return process.extractBests(search_text, services_list_ru, scorer=fuzz.WRatio, score_cutoff=70)

    async def shutdown(self):
        await self.session.close()
        self._cache.shutdown()
