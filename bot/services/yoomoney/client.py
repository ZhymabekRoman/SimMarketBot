import datetime
from .history import History


class Client:
    def __init__(self,
                 token: str = None,
                 base_url: str = None,
                 ):

        if base_url is None:
            self.base_url = "https://yoomoney.ru/api/"

        if token is not None:
            self.token = token

    async def operation_history(self,
                                type: str = None,
                                label: str = None,
                                from_date: datetime.datetime = None,
                                till_date: datetime.datetime = None,
                                start_record: str = None,
                                records: int = None,
                                details: bool = None,
                                ):
        method = "operation-history"
        return await History(base_url=self.base_url,
                             token=self.token,
                             method=method,
                             type=type,
                             label=label,
                             from_date=from_date,
                             till_date=till_date,
                             start_record=start_record,
                             records=records,
                             details=details,
                             ).start()
