from datetime import datetime


class Operation:
    def __init__(self,
                 operation_id: str = None,
                 status: str = None,
                 datetime: datetime = None,
                 title: str = None,
                 pattern_id: str = None,
                 direction: str = None,
                 amount: float = None,
                 label: str = None,
                 type: str = None,
                 json: dict = {}
                 ):
        self.operation_id = operation_id
        self.status = status
        self.datetime = datetime
        self.title = title
        self.pattern_id = pattern_id
        self.direction = direction
        self.amount = amount
        self.label = label
        self.type = type
        self.json = json
