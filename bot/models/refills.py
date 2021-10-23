import sqlalchemy as sa
from bot.models import BaseModel
import enum


class RefillSource(enum.Enum):
    QIWI = "QIWI"
    ADMIN = "Administrator"  # Deprecated
    YOOMONEY = "YooMoney"
    REFERRAL = "Реферал"


class Refill(BaseModel):
    __tablename__ = 'refills'

    txn_id = sa.Column(sa.Integer, nullable=False, unique=True, primary_key=True, index=True)
    user_id = sa.Column(sa.Integer, sa.ForeignKey('users.user_id'))
    amount = sa.Column(sa.Float, nullable=False)
    data = sa.Column(sa.JSON, default={}, nullable=False)
    source = sa.Column(sa.Enum(RefillSource))

    payer = sa.orm.relationship("User", backref="refills")
