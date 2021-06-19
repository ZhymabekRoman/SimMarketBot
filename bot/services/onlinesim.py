import json
import aiohttp
import datetime
import asyncio
import pytz

# from bot.services.scheduler import scheduler
from bot.events.onlinesim import onlinesim_msg_code_event  # , onlinesim_close_operation
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
            if country["visible"] == 1 and await self.summary_numbers_count(country_code) != 0:
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
            if service["count"] != 0:
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

        ic(parsed)

        status = parsed.get("response")
        tzid = parsed.get("tzid")

        return status, tzid

    async def stateOne(
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

        # url = "https://onlinesim.ru/demo/api/getState.php"
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

        return parsed

    async def run_waiting_code_task(self, tzid: int, service: str, callback=onlinesim_msg_code_event):
        task_stats = await self.stateOne(tzid)

        for _service in task_stats:
            if _service["service"].lower() == service.lower():
                service_stat = _service
                break

        waiting_code_task = self.loop.create_task(self.wait_code(tzid, service_stat["time"] - 10, callback))
        self.tasks[tzid] = waiting_code_task

        return service_stat

    async def wait_code(self, tzid: int, timeout: int, callback, not_end=False):
        __response_msg = None
        __last_code = (tzid, __response_msg, OnlinesimStatus.error)

        end_date = datetime.datetime.now(pytz.timezone('Europe/Moscow')) + datetime.timedelta(seconds=timeout)

        try:
            while True:
                await asyncio.sleep(10)

                if end_date < datetime.datetime.now(pytz.timezone('Europe/Moscow')):
                    if __response_msg is None:
                        __status = OnlinesimStatus.expire
                    else:
                        __status = OnlinesimStatus.success
                    __last_code = (tzid, __response_msg, __status)
                    await callback(__last_code)
                    await self.close(tzid)
                    del self.tasks[tzid]
                    break

                response = await self.stateOne(tzid)
                ic("Make pool")

                if "msg" in response and response["msg"] != __response_msg and response["msg"] is not False:
                    ic("New message found")
                    __response_msg = response["msg"]
                    __last_code = (tzid, __response_msg, OnlinesimStatus.waiting)
                    ic(__response_msg)
                    ic(type(__response_msg))
                    await callback(__last_code)
                    await self.next(tzid)

        except asyncio.CancelledError:
            ic("Close task")
            if __response_msg is None:
                __status = OnlinesimStatus.cancel
            else:
                __status = OnlinesimStatus.success
            __last_code = (tzid, __response_msg, OnlinesimStatus.cancel)
            await callback(__last_code)
            await self.close(tzid)
            del self.tasks[tzid]
            raise
        except Exception:
            await callback(__last_code)
            del self.tasks[tzid]
            await self.close(tzid)
        # finally:
        #     if callback:
        #         await callback(__last_code)

        #     return __last_code

    async def next(self, tzid: int):
        url = "https://onlinesim.ru/api/setOperationRevise"
        params = {
            "apikey": self.__api_key,
            "tzid": tzid
        }
        async with self.session.get(url=url, params=params) as response:
            result = await response.text()
            parsed = json.loads(result)

        ic(parsed)

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

        ic(parsed)

        # if parsed.get("response") == "TRY_AGAIN_LATER":
        #     ic("Schedule task to close")
        #     scheduler.add_job(onlinesim_close_operation, "date", id=tzid, run_date=datetime.datetime.utcnow() + datetime.timedelta(minutes=3), kwargs={"tzid": tzid})

        return parsed

    async def shutdown(self):
        await self.session.close()
