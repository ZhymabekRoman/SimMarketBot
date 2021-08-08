import json
import aiohttp
import asyncio

from bot.utils.lru_cacher import LRUDictCache

from icecream import ic
import traceback


class OnlineSIM:
    _cache = LRUDictCache()

    def __init__(self, api_key, loop):
        self.__api_key = api_key
        self.session = aiohttp.ClientSession()
        self.loop = loop
        self.lock = asyncio.Lock()

    async def countries_list(self):
        url = "http://api-conserver.onlinesim.ru/stubs/handler_api.php"
        params = {"api_key": self.__api_key, "action": "getCountries"}

        if "countries_list" in self._cache:
            parsed = self._cache["countries_list"]
        else:
            async with self.session.get(url=url, params=params) as response:
                result = await response.text()
                parsed = json.loads(result)
            async with self.lock:
                self._cache["countries_list"] = parsed

        _result = {}
        for country_code, country in parsed.items():
            if country["visible"] == 1:   # and await self.summary_numbers_count(country_code) != 0:
                _result.update({country_code: country["rus"]})
        return _result

    async def number_stats(self, country_code: int):
        url = "https://onlinesim.ru/api/getNumbersStats.php"
        params = {"apikey": self.__api_key, "country": country_code}

        _cache_key = str({"number_stats": country_code})
        if _cache_key in self._cache:
            parsed = self._cache[_cache_key]
        else:
            async with self.session.get(url=url, params=params) as response:
                result = await response.text()
                parsed = json.loads(result)
            async with self.lock:
                self._cache[_cache_key] = parsed

        _result = {}
        try:
            for _, service in parsed["services"].items():
                if service["count"] != 0:
                    _result.update({service["slug"]: service})
        except Exception:
            ic("Exception was interrupted in number_stats function")
            traceback.print_exc()
            ic(country_code)
            ic(parsed)

        return _result

    async def summary_numbers_count(self, country_code: int):
        services_list = await self.number_stats(country_code)

        _result = 0

        for service_code, service_info in services_list.items():
            _result += service_info["count"]

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

    async def shutdown(self):
        await self.session.close()
