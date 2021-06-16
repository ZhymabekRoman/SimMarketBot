# coding: utf-8
import aiohttp
import logging
import time

logger = logging.getLogger("currency_converter")

# TODO: Implement timed LRU cache


class CurrencyConverter:
    _cache = {}

    def __init__(self, api_key: str):
        self.__api_key = api_key
        self.session = aiohttp.ClientSession()

    async def convert(self, amount: float, from_currency: str, to_currency: str = 'RUB') -> float:
        amount = float(amount)

        if from_currency == to_currency:
            return amount

        url = f"https://v6.exchangerate-api.com/v6/{self.__api_key}/pair/{from_currency}/{to_currency}"

        _cache_key = f"{from_currency}-{to_currency}"

        if _cache_key in self._cache:
            logger.debug("Using cached value")

            rate = self._cache[_cache_key]["rate"]
            # time = self._cache[_cache_key]["time"]
        else:
            async with self.session.get(url=url) as response:
                parsed = await response.json()
                rate = parsed["conversion_rate"]

            self._cache[_cache_key] = {"rate": rate, "time": time.time()}

        conversion = rate * amount

        logger.debug("1", from_currency, "=", to_currency, rate)
        logger.debug(amount, from_currency, "=", to_currency, conversion)

        return conversion

    async def shutdown(self):
        await self.session.close()
