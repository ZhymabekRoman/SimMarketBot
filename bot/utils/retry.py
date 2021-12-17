from functools import wraps
import asyncio

from aiohttp.client_exceptions import ClientConnectorError

# See also: https://github.com/litl/backoff

def retry_on_connection_issue(total=5, backoff_factor=0.01):
    def retry_on_connection_issue_inner(method):
        @wraps(method)
        async def wrapper_method(self, *args, **kwargs):
            current_exception = None
            for retry in range(total):
                backoff_sleep = backoff_factor * (2 ** (retry - 1))
                await asyncio.sleep(backoff_sleep)

                try:
                    return await method(self, *args, **kwargs)
                except (ClientConnectorError, asyncio.exceptions.TimeoutError) as e:
                    current_exception = e
                    continue

            else:
                if current_exception:
                    raise current_exception

                raise Exception("Strange error!")

        return wrapper_method
    return retry_on_connection_issue_inner
