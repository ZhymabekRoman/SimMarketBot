import sqlalchemy as sa
from bot.models import BaseModel
import enum


class SMSHubStatus(enum.Enum):
    waiting = 0
    success = 1
    cancel = 2


class SMSHub(BaseModel):
    __tablename__ = 'sms_hub'

    id = sa.Column(sa.Integer, unique=True, primary_key=True, autoincrement=True)
    task_id = sa.Column(sa.Integer, nullable=False, index=True)
    user_id = sa.Column(sa.Integer, sa.ForeignKey('users.user_id'))
    number = sa.Column(sa.Text)
    price = sa.Column(sa.Float, nullable=False)
    service = sa.Column(sa.Text, nullable=False)
    country = sa.Column(sa.Text, nullable=False)
    operator= sa.Column(sa.Text, nullable=False)
    status = sa.Column(sa.Enum(SMSHubStatus), default=SMSHubStatus.waiting)
    msg = sa.Column(sa.JSON, nullable=False, default=[])

    user = sa.orm.relationship("User")  # , backref="tasks")
