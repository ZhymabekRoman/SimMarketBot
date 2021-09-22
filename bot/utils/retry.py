from functools import wraps
import asyncio

from aiohttp.client_exceptions import ClientConnectorError


def retry_on_connection_issue(total=50, backoff_factor=0.01):
    def retry_on_connection_issue_inner(method):
        @wraps(method)
        async def wrapper_method(self, *args, **kwargs):
            for retry in range(total):
                backoff_sleep = backoff_factor * (2 ** (retry - 1))
                await asyncio.sleep(backoff_sleep)

                try:
                    return await method(self, *args, **kwargs)
                except ClientConnectorError:
                    continue

        return wrapper_method
    return retry_on_connection_issue_inner
