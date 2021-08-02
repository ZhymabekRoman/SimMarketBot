import sqlalchemy as sa
from bot.models import BaseModel
import enum


class OnlinesimStatus(enum.Enum):
    waiting = 0  # TZ_NUM_WAIT
    success = 1  # TZ_OVER_OK
    cancel = 2  # Cancelled by user without msg
    expire = 3  # TZ_OVER_EMPTY
    # error = 4


class Onlinesim(BaseModel):
    __tablename__ = 'onlinesim'

    id = sa.Column(sa.Integer, unique=True, primary_key=True, autoincrement=True)
    tzid = sa.Column(sa.Integer, nullable=False, index=True)
    user_id = sa.Column(sa.Integer, sa.ForeignKey('users.user_id'))
    # credited = sa.Column(sa.Boolean)
    number = sa.Column(sa.Text)
    price = sa.Column(sa.Float, nullable=False)
    # end_date = sa.Column(sa.DateTime(timezone=True))
    service_code = sa.Column(sa.Text, nullable=False)
    country_code = sa.Column(sa.Text, nullable=False)
    status = sa.Column(sa.Enum(OnlinesimStatus), default=OnlinesimStatus.waiting)
    msg = sa.Column(sa.JSON, default={"msg": []})

    user = sa.orm.relationship("User", backref="tasks")
