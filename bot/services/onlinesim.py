import json
import aiohttp
import datetime
import asyncio
import pytz

from bot.events.onlinesim import onlinesim_msg_code_event
from bot.models.onlinesim import OnlinesimStatus
from bot.utils.lru_cacher import LRUDictCache

from icecream import ic


class OnlineSIM:
    _cache = LRUDictCache()

    def __init__(self, api_key, loop):
        self.__api_key = api_key
        self.session = aiohttp.ClientSession()
        self.tasks = {}
        self.loop = loop

    async def countries_list(self):
        url = "http://api-conserver.onlinesim.ru/stubs/handler_api.php"
        params = {"api_key": self.__api_key, "action": "getCountries"}

        if "countries_list" in self._cache:
            parsed = self._cache["countries_list"]
        else:
            async with self.session.get(url=url, params=params) as response:
                result = await response.text()
                parsed = json.loads(result)

            self._cache["countries_list"] = parsed

        _result = {}
        for country_code, country in parsed.items():
            if country["visible"] == 1:
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

            self._cache[_cache_key] = parsed

        _result = {}
        for _, service in parsed["services"].items():
            _result.update({service["slug"]: service})

        return _result

    async def summary_numbers_count(self, country_code: int):
        services_list = await self.number_stats(country_code)

        _result = 0

        for service_code, service_info in services_list.items():
            _result += service_info["count"]

        return _result

    async def buy_number(self, service_code: int, country_code: int):
        url = "https://onlinesim.ru/api/getNum.php"
        # url = "https://onlinesim.ru/demo/api/getNum.php"
        params = {"apikey": self.__api_key, "country": country_code, "service": service_code}

        async with self.session.get(url=url, params=params) as response:
            result = await response.text()
            parsed = json.loads(result)

        status = bool(parsed.get("response") == 1)
        tzid = parsed.get("tzid")

        return status, tzid

    """
    async def number_state(self, tzid: int):
        # url = "https://onlinesim.ru/api/getState.php"
        url = "https://onlinesim.ru/demo/api/getState.php"
        params = {"apikey": self.__api_key, "tzid": tzid, "message_to_code": 0}

        async with self.session.get(url=url, params=params) as response:
            result = await response.text()
            parsed = json.loads(result)

        # status = bool(parsed.get("response") == 1)
        # id = parsed.get("tzid")

        return parsed
    """

    async def stateOne(
        self,
        tzid: int,
        message_to_code: int = 1,
        msg_list: bool = 1,
        clean: bool = 1,
        repeat: bool = 0,
    ):
        type = "index"
        if repeat:
            type = "repeat"

        url = "https://onlinesim.ru/demo/api/getState.php"
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

        return parsed

    async def run_waiting_code_task(self, tzid: int, timeout=14, callback=onlinesim_msg_code_event):
        waiting_code_task = self.loop.create_task(self.wait_code(tzid, timeout, callback))

        self.tasks[tzid] = waiting_code_task

    async def wait_code(
        self, tzid: int, timeout=14, callback=None, not_end=False, full_message=False
    ):
        __last_code = (tzid, None, OnlinesimStatus.error)
        _response_type = 1
        if full_message:
            _response_type = 0

        end_date = datetime.datetime.now(pytz.timezone('Europe/Moscow')) + datetime.timedelta(minutes=timeout)

        try:
            while True:
                await asyncio.sleep(timeout)
                if end_date < datetime.datetime.now(pytz.timezone('Europe/Moscow')):
                    __last_code = (tzid, None, OnlinesimStatus.expire)
                    await self.close(tzid)
                    break
                response = await self.stateOne(tzid, _response_type, 1)
                if "msg" in response and not not_end and response["msg"] != __last_code and response["msg"] is not False:
                    __last_code = (tzid, response["msg"], OnlinesimStatus.success)
                    await self.close(tzid)
                    break
                elif "msg" in response and not_end and response["msg"] != __last_code and response["msg"] is not False:
                    __last_code = (tzid, response["msg"], OnlinesimStatus.success)
                    await self.next(tzid)
                    break
        except asyncio.CancelledError:
            __last_code = (tzid, None, OnlinesimStatus.cancel)
            await self.close(tzid)
        finally:
            if callback:
                await callback(__last_code)

            return __last_code

    async def next(self, tzid: int):
        url = "https://onlinesim.ru/api/setOperationRevise"
        params = {
            "apikey": self.__api_key,
            "tzid": tzid
        }
        async with self.session.get(url=url, params=params) as response:
            result = await response.text()
            parsed = json.loads(result)

        return parsed

    async def close(self, tzid: int):
        url = "https://onlinesim.ru/api/setOperationOk"
        params = {
            "apikey": self.__api_key,
            "tzid": tzid
        }
        async with self.session.get(url=url, params=params) as response:
            result = await response.text()
            parsed = json.loads(result)

        return parsed

    async def shutdown(self):
        await self.session.close()
