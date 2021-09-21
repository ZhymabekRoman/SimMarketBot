import json
import aiohttp
import asyncio

from bot.utils.json_storager import JSONCacher
from bot.utils.country2flag import countries_flags_dict

from icecream import ic


class OnlineSIM:
    _cache = JSONCacher("bot/user_data/OnlineSIMCacheFile.json")

    def __init__(self, api_key, loop):
        self.__api_key = api_key
        self.session = aiohttp.ClientSession()
        self.loop = loop
        self.lock = asyncio.Lock()

    async def countries_list(self):
        return self._cache["countries_list"]

    async def _countries_list(self):
        # Using alternative API
        url = "http://api-conserver.onlinesim.ru/stubs/handler_api.php"
        params = {"api_key": self.__api_key, "action": "getCountries"}

        async with self.session.get(url=url, params=params) as response:
            result = await response.text()
            parsed = json.loads(result)

        _result = {}
        for country_code, country in parsed.items():
            if country["visible"] == 1 and await self._summary_numbers_count(country_code) != 0:
                _result.update({country_code: f'{countries_flags_dict.get(country_code, "")} {country["rus"]}'})

        async with self.lock:
            self._cache["countries_list"] = _result

        return _result

    async def number_stats(self, country_code: int):
        _cache_key = str({"number_stats": country_code})
        return self._cache[_cache_key]

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
            _cache_key = str({"number_stats": country_code})
            self._cache[_cache_key] = _result

        return _result

    async def summary_numbers_count(self, country_code: int):
        _cache_key = str({"summary_numbers_count": country_code})
        return self._cache[_cache_key]

    async def _summary_numbers_count(self, country_code: int):
        services_list = await self._number_stats(country_code)

        _result = 0

        for service_code, service_info in services_list.items():
            _result += service_info["count"]

        async with self.lock:
            _cache_key = str({"summary_numbers_count": country_code})
            self._cache[_cache_key] = _result

        return _result

    async def getNum(self, service_code: int, country_code: int):
        url = "https://onlinesim.ru/api/getNum.php"
        params = {"apikey": self.__api_key, "country": country_code, "service": service_code}

        async with self.session.get(url=url, params=params) as response:
            result = await response.text()
            parsed = json.loads(result)

        ic(parsed)

        status = parsed.get("response")
        tzid = parsed.get("tzid")

        return status, tzid

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

        ic(parsed)

        if isinstance(parsed, dict):
            if parsed.get("response") == "ERROR_NO_OPERATIONS":
                return None

        # OnlineSim return list, with entered tzid's operation, just for more stability let find operation by tzid manually
        for _service in parsed:
            if _service.get("tzid") == tzid:
                return _service
        else:
            raise

    async def setOperationRevise(self, tzid: int):
        url = "https://onlinesim.ru/api/setOperationRevise.php"
        params = {
            "apikey": self.__api_key,
            "tzid": tzid
        }
        async with self.session.get(url=url, params=params) as response:
            result = await response.text()
            parsed = json.loads(result)

        ic(parsed)

        return parsed

    async def setOperationOk(self, tzid: int):
        url = "https://onlinesim.ru/api/setOperationOk.php"
        params = {
            "apikey": self.__api_key,
            "tzid": tzid
        }
        async with self.session.get(url=url, params=params) as response:
            result = await response.text()
            parsed = json.loads(result)

        ic(parsed)

        return parsed

    async def cache_updater(self, waiting_time: int = 3600):
        while True:
            await asyncio.sleep(waiting_time)
            await self._countries_list()

    async def shutdown(self):
        await self.session.close()
        self._cache.shutdown()
